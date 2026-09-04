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


def _section_recall(details: list[tuple[str | None, str | None]]) -> dict:
    """Recall de sección, contado aparte del de página y solo sobre quien lo declara.

    Mezclarlo con el recall de página escondería el efecto: una consulta puede acertar
    la página y traer la sección equivocada, que es justo el fallo que el troceado por
    encabezados existe para arreglar y que hasta ahora no se medía.
    """
    scored = [(want, got) for want, got in details if want]
    if not scored:
        return {}
    hits = sum(1 for want, got in scored if got and want.casefold() in got.casefold())
    return {"section_recall": hits / len(scored), "section_queries": len(scored)}


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
    piso, no el MRR global. `RRF_K` sí es de orden: aplana la curva de la fusión.
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

    print("\nRRF_VECTOR_WEIGHT (modo hybrid)")
    print(f"{'peso':>7}{'MRR':>8}{'recall@1':>10}{'miss':>7}")
    original_weight = embeddings.RRF_VECTOR_WEIGHT
    try:
        for weight in (1.0, 1.5, 2.0, 3.0, 5.0, 10.0):
            embeddings.RRF_VECTOR_WEIGHT = weight
            runs = []
            for q in queries:
                hits = embeddings.search(workspace_id, q["query"], mode="hybrid")
                runs.append((_rank_of([h["slug"] for h in hits], q["expect"]), 0.0, len(hits)))
            m = _score(runs)
            print(f"{weight:>7.1f}{m['mrr']:>8.2f}{m['recall@1']:>10.2f}{m['misses']:>7}")
    finally:
        embeddings.RRF_VECTOR_WEIGHT = original_weight


FILTER_QUERIES = Path(__file__).parent / "queries-filters.json"


def _filter_cases(embeddings, workspace_id: int) -> dict:
    """Puntúa el filtro por etiquetas de `search_knowledge`, aparte del conjunto principal.

    En su propio archivo y su propia fila a propósito: meter estas consultas en el
    conjunto de siempre cambiaría las métricas principales y ninguna corrida anterior
    volvería a ser comparable.

    Las etiquetas las pone el cargador (`corpus._tag_by_origin`), porque el corpus real
    no trae ninguna utilizable.
    """
    if not FILTER_QUERIES.is_file():
        return {}
    cases = json.loads(FILTER_QUERIES.read_text())
    runs = []
    for case in cases:
        start = time.perf_counter()
        hits = embeddings.search(workspace_id, case["query"], mode="hybrid", tags=case.get("tags"))
        elapsed = (time.perf_counter() - start) * 1000
        slugs = [h["slug"] for h in hits]
        if case["expect"]:
            rank = _rank_of(slugs, case["expect"])
        else:
            # Un filtro que excluye la respuesta debe devolver vacío, no la lista sin
            # filtrar. Acertar aquí es no devolver nada.
            rank = 1 if not slugs else 0
        runs.append((rank, elapsed, len(slugs)))
    return _score(runs)


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
            runs, detail, sections = [], {}, []
            for q in queries:
                start = time.perf_counter()
                hits = embeddings.search(workspace_id, q["query"], mode=mode)
                elapsed = (time.perf_counter() - start) * 1000
                rank = _rank_of([h["slug"] for h in hits], q["expect"])
                runs.append((rank, elapsed, len(hits)))
                detail[q["query"]] = rank
                # La sección del primer acierto que sí era la página buena: si la
                # página falla, la sección no dice nada.
                found = next((h for h in hits if h["slug"] in q["expect"]), None)
                sections.append(
                    (q.get("expected_heading"), found.get("section") if found else None)
                )
            table[label] = {**_score(runs), **_section_recall(sections)}
            per_query[label] = detail
        os.environ.pop("RERANK", None)

        # `rag` mide el contexto ensamblado, que es lo que recibe un agente. Las filas
        # `semantic` y `hybrid` miden `embeddings.search`, así que un cambio dentro de
        # `rag_context` no las mueve: sin esta fila el efecto sería invisible.
        runs, sections = [], []
        for q in queries:
            start = time.perf_counter()
            out = embeddings.rag_context(workspace_id, q["query"])
            elapsed = (time.perf_counter() - start) * 1000
            chunks = out["chunks"]
            rank = _rank_of([c["slug"] for c in chunks], q["expect"])
            runs.append((rank, elapsed, len(chunks)))
            found = next((c for c in chunks if c["slug"] in q["expect"]), None)
            sections.append((q.get("expected_heading"), found.get("section") if found else None))
        table["rag"] = {**_score(runs), **_section_recall(sections)}

        filters = _filter_cases(embeddings, workspace_id)
        if filters:
            table["hybrid+tags"] = filters

        header = (
            f"{'config':<18}{'recall@1':>10}{'MRR':>8}{'sección':>9}"
            f"{'zero':>8}{'miss':>7}{'p50':>9}{'p95':>9}"
        )
        print(header)
        print("─" * len(header))
        for label, m in table.items():
            # El recall de sección va aparte del de página: una consulta puede acertar
            # la página y traer la sección equivocada, que es el fallo que el troceado
            # por encabezados existe para arreglar.
            section = f"{m['section_recall']:>9.2f}" if "section_recall" in m else f"{'—':>9}"
            print(
                f"{label:<18}{m['recall@1']:>10.2f}{m['mrr']:>8.2f}{section}"
                f"{m['zero_results']:>8.2f}{m['misses']:>7}{m['p50_ms']:>8.1f}m{m['p95_ms']:>8.1f}m"
            )
        scored = next(
            (m.get("section_queries") for m in table.values() if m.get("section_queries")), 0
        )
        if scored:
            print(f"\nrecall de sección medido sobre {scored} consultas que la declaran")

        print("\npor clase (MRR):")
        classes = sorted({q["class"] for q in queries})
        print(f"{'config':<18}" + "".join(f"{c:>8}" for c in classes))
        # Solo las filas del conjunto principal: `hybrid+tags` puntúa otras consultas
        # y no tiene detalle por clase. Sin este filtro reventaba con un KeyError
        # después de imprimir la tabla y antes de escribir el JSON, así que la corrida
        # se veía bien en pantalla y no dejaba resultado.
        for label in per_query:
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
