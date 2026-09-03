"""Compara configuraciones de recuperación sobre el corpus real y saca una tabla.

Se ejecuta a mano, no en pytest: mide calidad, no comportamiento, y un número de
calidad que puede tumbar un build es un build que se acaba ignorando.

    EVAL_CORPUS=data/eval-corpus uv run python -m evals.retrieval

Las variantes de FTS se calculan en el SQL del propio harness, así que una
ejecución nunca deja el esquema de la aplicación en estado experimental.
"""

import argparse
import json
import os
import statistics
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

import psycopg
from psycopg import sql

ADMIN_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql://doction:doction@localhost:55432/postgres"
)
QUERIES = Path(__file__).parent / "queries.json"
RESULTS_DIR = Path(__file__).parent / "results"

# Las cuatro variantes de palabra clave. `english` es lo que corre hoy; las otras
# tres son contrafactuales — el stemmer que va dentro de la configuración final se
# decide con esta tabla, no antes (design.md, Open Questions).
FTS_CONFIGS = {
    "fts-english": "english",
    "fts-spanish": "spanish",
    "fts-unaccent-en": "eval_unaccent_en",
    "fts-unaccent-es": "eval_unaccent_es",
}


def _create_database() -> str:
    name = f"doction_eval_{uuid.uuid4().hex[:12]}"
    with psycopg.connect(ADMIN_URL, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    return ADMIN_URL.rsplit("/", 1)[0] + "/" + name


def _drop_database(url: str) -> None:
    name = url.rsplit("/", 1)[1]
    with psycopg.connect(ADMIN_URL, autocommit=True) as admin:
        admin.execute(
            sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name))
        )


def _install_unaccent_configs(conn) -> None:
    """Configuraciones de búsqueda que pliegan acentos antes de aplicar el stemmer.

    `unaccent()` suelto no sirve aquí: es STABLE, no IMMUTABLE, así que Postgres lo
    rechaza en una columna generada. Encadenado dentro de una configuración sí vale.
    """
    conn.execute("CREATE EXTENSION IF NOT EXISTS unaccent")
    for name, base, stemmer in (
        ("eval_unaccent_en", "english", "english_stem"),
        ("eval_unaccent_es", "spanish", "spanish_stem"),
    ):
        exists = conn.execute("SELECT 1 FROM pg_ts_config WHERE cfgname = %s", (name,)).fetchone()
        if exists:
            continue
        conn.execute(
            sql.SQL("CREATE TEXT SEARCH CONFIGURATION {} ( COPY = {} )").format(
                sql.Identifier(name), sql.Identifier(base)
            )
        )
        conn.execute(
            sql.SQL(
                "ALTER TEXT SEARCH CONFIGURATION {} ALTER MAPPING FOR "
                "hword, hword_part, word WITH unaccent, {}"
            ).format(sql.Identifier(name), sql.Identifier(stemmer))
        )


def _fts_search(db, workspace_id: int, query: str, config: str, limit: int = 20) -> list[str]:
    match = db._fts_query(query)
    if not match:
        return []
    vector = "to_tsvector(%(cfg)s, coalesce(p.title, '') || ' ' || coalesce(p.content, ''))"
    with db.connect() as conn:
        rows = conn.execute(
            f"""
            SELECT p.slug
            FROM pages p
            WHERE {vector} @@ to_tsquery(%(cfg)s, %(q)s)
              AND p.workspace_id = %(ws)s AND p.deleted_at IS NULL
            ORDER BY ts_rank({vector}, to_tsquery(%(cfg)s, %(q)s)) DESC
            LIMIT %(lim)s
            """,
            {"cfg": config, "q": match, "ws": workspace_id, "lim": limit},
        ).fetchall()
    return [r["slug"] for r in rows]


def _rank_of(slugs: list[str], expected: list[str]) -> int:
    """Posición (1-based) del primer acierto, o 0 si no aparece."""
    for i, slug in enumerate(slugs, start=1):
        if slug in expected:
            return i
    return 0


def _score(runs: list[tuple[int, float, int]]) -> dict:
    """runs = [(rank, elapsed_ms, n_results)] → métricas de la configuración."""
    ranks = [r for r, _, _ in runs]
    times = sorted(t for _, t, _ in runs)
    return {
        "recall@1": sum(1 for r in ranks if r == 1) / len(ranks),
        "mrr": sum(1 / r if r else 0.0 for r in ranks) / len(ranks),
        "zero_results": sum(1 for _, _, n in runs if n == 0) / len(runs),
        "misses": sum(1 for r in ranks if r == 0),
        "p50_ms": statistics.median(times),
        "p95_ms": times[min(len(times) - 1, int(round(0.95 * (len(times) - 1))))],
    }


def _sweep(embeddings, workspace_id: int, queries: list[dict]) -> None:
    """Barre los umbrales: cada uno decide algo distinto, así que se mira su curva.

    `SEARCH_MIN_SCORE` no ordena, esconde — su métrica es cuánto recall cuesta el
    piso, no el MRR global. `KEYWORD_BOOST` sí es de orden.
    """
    print("\n" + "─" * 45)
    print("SEARCH_MIN_SCORE (modo semantic)")
    print(f"{'floor':>7}{'MRR':>8}{'recall@1':>10}{'zero':>8}{'miss':>7}")
    original = embeddings.SEARCH_MIN_SCORE
    try:
        for floor in (0.25, 0.30, 0.35, 0.40, 0.45, 0.50):
            embeddings.SEARCH_MIN_SCORE = floor
            runs = []
            for q in queries:
                hits = embeddings.search(workspace_id, q["query"], mode="semantic")
                runs.append((_rank_of([h["slug"] for h in hits], q["expect"]), 0.0, len(hits)))
            m = _score(runs)
            print(
                f"{floor:>7.2f}{m['mrr']:>8.2f}{m['recall@1']:>10.2f}"
                f"{m['zero_results']:>8.2f}{m['misses']:>7}"
            )
    finally:
        embeddings.SEARCH_MIN_SCORE = original

    print("\nKEYWORD_BOOST (modo semantic, piso fijo)")
    print(f"{'boost':>7}{'MRR':>8}{'recall@1':>10}{'miss':>7}")
    original_boost = embeddings.KEYWORD_BOOST
    try:
        for boost in (0.0, 0.05, 0.10, 0.20, 0.30):
            embeddings.KEYWORD_BOOST = boost
            runs = []
            for q in queries:
                hits = embeddings.search(workspace_id, q["query"], mode="semantic")
                runs.append((_rank_of([h["slug"] for h in hits], q["expect"]), 0.0, len(hits)))
            m = _score(runs)
            print(f"{boost:>7.2f}{m['mrr']:>8.2f}{m['recall@1']:>10.2f}{m['misses']:>7}")
    finally:
        embeddings.KEYWORD_BOOST = original_boost


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workspace",
        default="personal",
        help="nombre del volcado, o `all` para juntar todos en un workspace",
    )
    parser.add_argument("--queries", type=Path, default=QUERIES)
    parser.add_argument("--keep", action="store_true", help="no borrar la base al terminar")
    parser.add_argument(
        "--sweep", action="store_true", help="barre los umbrales en vez de comparar"
    )
    parser.add_argument("--label", default="baseline", help="nombre del run en results/")
    args = parser.parse_args()

    queries = json.loads(args.queries.read_text())
    database_url = _create_database()
    os.environ["DATABASE_URL"] = database_url
    os.environ["SEMANTIC_SEARCH"] = "1"
    os.environ.pop("EMBED_STUB", None)
    os.environ.pop("RERANK", None)
    os.environ.setdefault("MODEL_DIR", str(Path(__file__).resolve().parent.parent / "models"))
    os.environ.setdefault("DATA_DIR", "/tmp/doction-eval")

    from app import db, embeddings, meta
    from evals import corpus

    try:
        workspace_id, pages = corpus.load(args.workspace)
        with db.connect() as conn:
            _install_unaccent_configs(conn)
        indexed = embeddings.drain_pending()
        model = embeddings.get_embedder().name
        print(f"corpus: {pages} páginas, {indexed} indexadas, modelo {model}")
        print(f"consultas: {len(queries)}\n")

        # Comprueba que todas las etiquetas apuntan a páginas que existen: un slug
        # mal escrito se convierte en un fallo permanente y silencioso.
        known = {p.slug for p in db.workspace_pages(workspace_id)}
        unknown = sorted({s for q in queries for s in q["expect"] if s not in known})
        if unknown:
            raise SystemExit(f"slugs esperados que no existen en el corpus: {unknown}")

        table: dict[str, dict] = {}
        per_query: dict[str, dict] = {}

        for label, config in FTS_CONFIGS.items():
            runs, detail = [], {}
            for q in queries:
                start = time.perf_counter()
                slugs = _fts_search(db, workspace_id, q["query"], config)
                elapsed = (time.perf_counter() - start) * 1000
                rank = _rank_of(slugs, q["expect"])
                runs.append((rank, elapsed, len(slugs)))
                detail[q["query"]] = rank
            table[label] = _score(runs)
            per_query[label] = detail

        for label, mode, rerank in (
            ("semantic", "semantic", False),
            ("hybrid", "hybrid", False),
            ("hybrid+rerank", "hybrid", True),
        ):
            if rerank:
                os.environ["RERANK"] = "1"
            else:
                os.environ.pop("RERANK", None)
            runs, detail = [], {}
            for q in queries:
                start = time.perf_counter()
                hits = embeddings.search(workspace_id, q["query"], mode=mode)
                elapsed = (time.perf_counter() - start) * 1000
                rank = _rank_of([h["slug"] for h in hits], q["expect"])
                runs.append((rank, elapsed, len(hits)))
                detail[q["query"]] = rank
            table[label] = _score(runs)
            per_query[label] = detail
        os.environ.pop("RERANK", None)

        header = (
            f"{'config':<18}{'recall@1':>10}{'MRR':>8}{'zero':>8}{'miss':>7}{'p50':>9}{'p95':>9}"
        )
        print(header)
        print("─" * len(header))
        for label, m in table.items():
            print(
                f"{label:<18}{m['recall@1']:>10.2f}{m['mrr']:>8.2f}{m['zero_results']:>8.2f}"
                f"{m['misses']:>7}{m['p50_ms']:>8.1f}m{m['p95_ms']:>8.1f}m"
            )

        print("\npor clase (MRR):")
        classes = sorted({q["class"] for q in queries})
        print(f"{'config':<18}" + "".join(f"{c:>8}" for c in classes))
        for label in table:
            row = f"{label:<18}"
            for cls in classes:
                members = [q for q in queries if q["class"] == cls]
                ranks = [per_query[label][q["query"]] for q in members]
                mrr = sum(1 / r if r else 0.0 for r in ranks) / len(ranks)
                row += f"{mrr:>8.2f}"
            print(row)

        if args.sweep:
            _sweep(embeddings, workspace_id, queries)

        RESULTS_DIR.mkdir(exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y-%m-%d")
        out = RESULTS_DIR / f"{stamp}-{args.label}.json"
        out.write_text(
            json.dumps(
                {
                    "workspace": args.workspace,
                    "pages": pages,
                    "queries": len(queries),
                    "label": args.label,
                    # `model` es el nombre que la app graba en page_chunks; el encoder
                    # real lo fija MODEL_DIR, así que sin esa ruta dos runs con modelos
                    # distintos se ven idénticos en el JSON.
                    "model": model,
                    "model_dir": os.environ["MODEL_DIR"],
                    # Sin esto, dos runs a los dos lados de un cambio de troceador
                    # se ven idénticos en el JSON y la comparación queda sin etiqueta.
                    "chunker": meta.CHUNKER_ID,
                    "summary": table,
                    "per_query": per_query,
                },
                indent=2,
                ensure_ascii=False,
            )
            + "\n"
        )
        print(f"\nresultados → {out}")
    finally:
        db.reset_pool()
        if not args.keep:
            _drop_database(database_url)


if __name__ == "__main__":
    main()
