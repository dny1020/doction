"""Búsqueda semántica local: embeddings ONNX (MiniLM), sin servicios en la nube.

Opt-in vía `SEMANTIC_SEARCH=1`. Si está apagado (o no hay vectores aún), todo
degrada con gracia a la búsqueda de texto completo de Postgres. doction hace
*retrieval*; la generación (RAG, resúmenes) la hace el agente conectado por
MCP — aquí no vive ningún LLM.

El modelo se carga perezosamente y solo cuando se usa, para no gastar RAM en un
Pi cuando la función está apagada. Para tests, `EMBED_STUB=1` usa un encoder
determinista (bag-of-words) y evita depender del modelo real.
"""

import hashlib
import logging
import os
import re
import threading
import unicodedata
from pathlib import Path
from typing import cast

import numpy as np

from app import db, meta
from app.models import SnippetPart

logger = logging.getLogger(__name__)

EMBED_DIM = 384
MAX_TOKENS = 256
# Constante de la fusión de rangos recíprocos. 60 es el valor del artículo original
# (Cormack et al., 2009) y el que usa prácticamente todo el mundo. Lo que hace es
# aplanar la curva: sin ella el primero valdría el doble que el segundo, y con ella
# la diferencia entre los primeros puestos es pequeña y la cola sigue contando algo.
RRF_K = 60
# Peso de la lista vectorial dentro de la fusión. La RRF clásica no lleva pesos y sin
# ellos la fusión sale peor que la semántica sola: las dos listas no valen lo mismo
# sobre este corpus —FTS marca 0.46 de MRR y los vectores 0.77—, así que darles el
# mismo voto arrastra a la buena.
#
# Barrido del arnés (43 páginas, 28 consultas, 2026-09-03-rrf-weight-sweep.json):
#
#   peso       1.0   1.5   2.0   3.0   5.0  10.0
#   MRR       0.74  0.75  0.75  0.76  0.76  0.76
#   recall@1  0.64  0.68  0.68  0.68  0.68  0.68
#
# La meseta empieza en 1.5 y de ahí en adelante todo es ruido. Se coge 2.0, el
# extremo bajo: subirlo más no mide mejor y convertiría la híbrida en una semántica
# con adorno léxico, que sería mentir sobre lo que hace. 2.0 además coincide con la
# proporción entre los MRR medidos de las dos listas (0.77 frente a 0.46).
RRF_VECTOR_WEIGHT = 2.0
# Cuántos resultados del bi-encoder repuntúa el cross-encoder. Sin barrer a
# propósito: el reranker completo no mejora nada medible (MRR 0.73 frente a 0.72
# sin él, y recall@1 0.57 frente a 0.61) mientras multiplica por 29 la latencia
# mediana. Afinar su ventana sería optimizar algo que conviene tener apagado.
# Ojo con la interacción: bajar SEARCH_MIN_SCORE deja pasar más candidatos al
# cross-encoder, así que el reranker se encareció al bajar el piso (54 → 350 ms).
RERANK_CANDIDATES = 20
# Corte del buscador de la UI: decide qué se esconde, no cómo se ordena, así que se
# mide por lo que cuesta esconder. Barrido sobre el wiki real (28 consultas,
# evals/results/2026-08-24-minilm-en.json):
#
#   piso   0.25   0.30   0.35   0.40   0.45   0.50
#   MRR    0.72   0.68   0.67   0.67   0.53   0.38
#   vacías 0.07   0.11   0.14   0.21   0.36   0.54
#   fallos    4      7      8      8     12     17
#
# recall@1 es 0.64 de 0.25 a 0.40: el piso no cambia el primer resultado, solo corta
# la cola. El 0.35 anterior escondía 4 aciertos y doblaba las listas vacías a cambio
# de nada medible. Lo que no mide este barrido es cuánto relleno entra por debajo;
# el precio de 0.25 es una lista más larga.
SEARCH_MIN_SCORE = 0.25

_DEFAULT_MODELS_DIR = Path(__file__).resolve().parent.parent / "models"
_MODELS_DIR = Path(os.environ.get("MODEL_DIR") or _DEFAULT_MODELS_DIR)
MODEL_PATH = str(_MODELS_DIR / "model_quantized.onnx")
TOKENIZER_PATH = str(_MODELS_DIR / "tokenizer.json")
RERANKER_MODEL_PATH = str(_MODELS_DIR / "reranker" / "model_quantized.onnx")
RERANKER_TOKENIZER_PATH = str(_MODELS_DIR / "reranker" / "tokenizer.json")


def _flag(name: str) -> bool:
    return os.environ.get(name, "").lower() in {"1", "true", "yes"}


def semantic_enabled() -> bool:
    """True si la búsqueda semántica está activada por entorno."""
    return _flag("SEMANTIC_SEARCH")


def rerank_enabled() -> bool:
    """True si el reranker cross-encoder está activado (requiere semántica activa)."""
    return _flag("RERANK") and semantic_enabled()


def _l2_normalize(mat: np.ndarray) -> np.ndarray:
    norms = np.clip(np.linalg.norm(mat, axis=1, keepdims=True), 1e-9, None)
    return (mat / norms).astype(np.float32)


# ── Encoders ─────────────────────────────────────────────────────────────────


class _OnnxEmbedder:
    """MiniLM int8 vía onnxruntime + tokenizer HF. Mean-pooling + L2 normalize."""

    name = "all-MiniLM-L6-v2-int8"

    def __init__(self) -> None:
        import onnxruntime as ort
        from tokenizers import Tokenizer

        self._tok = Tokenizer.from_file(TOKENIZER_PATH)
        self._tok.enable_truncation(max_length=MAX_TOKENS)
        self._tok.enable_padding()
        self._sess = ort.InferenceSession(MODEL_PATH, providers=["CPUExecutionProvider"])
        self._inputs = set()
        for model_input in self._sess.get_inputs():
            self._inputs.add(model_input.name)

    def encode(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, EMBED_DIM), dtype=np.float32)
        encs = self._tok.encode_batch(texts)
        input_ids = np.array([e.ids for e in encs], dtype=np.int64)
        attention = np.array([e.attention_mask for e in encs], dtype=np.int64)
        feeds: dict[str, np.ndarray] = {"input_ids": input_ids, "attention_mask": attention}
        if "token_type_ids" in self._inputs:
            feeds["token_type_ids"] = np.array([e.type_ids for e in encs], dtype=np.int64)
        # run() promete Sequence[ndarray | SparseTensor | list | dict]; este modelo
        # siempre devuelve un único tensor denso.
        (last_hidden,) = cast(list[np.ndarray], self._sess.run(None, feeds))  # (B, S, 384)
        mask = attention[:, :, None].astype(np.float32)
        summed = (last_hidden * mask).sum(axis=1)
        counts = np.clip(mask.sum(axis=1), 1e-9, None)
        return _l2_normalize(summed / counts)


class _StubEmbedder:
    """Encoder determinista bag-of-words para tests (sin modelo)."""

    name = "stub"

    def encode(self, texts: list[str]) -> np.ndarray:
        out = np.zeros((len(texts), EMBED_DIM), dtype=np.float32)
        for i, text in enumerate(texts):
            for token in re.findall(r"\w+", text.lower()):
                h = int(hashlib.sha1(token.encode()).hexdigest(), 16)
                out[i, h % EMBED_DIM] += 1.0
        return _l2_normalize(out)


class _OnnxReranker:
    """Cross-encoder ms-marco MiniLM int8: puntúa pares (query, texto).

    A diferencia del bi-encoder, ve query y texto juntos, así que ordena mejor;
    solo se usa para repuntuar los primeros RERANK_CANDIDATES (opt-in RERANK=1).
    """

    name = "ms-marco-MiniLM-L-6-v2-int8"

    def __init__(self) -> None:
        import onnxruntime as ort
        from tokenizers import Tokenizer

        self._tok = Tokenizer.from_file(RERANKER_TOKENIZER_PATH)
        self._tok.enable_truncation(max_length=MAX_TOKENS)
        self._tok.enable_padding()
        self._sess = ort.InferenceSession(RERANKER_MODEL_PATH, providers=["CPUExecutionProvider"])
        self._inputs = {model_input.name for model_input in self._sess.get_inputs()}

    def score(self, query: str, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros(0, dtype=np.float32)
        encs = self._tok.encode_batch([(query, text) for text in texts])
        feeds: dict[str, np.ndarray] = {
            "input_ids": np.array([e.ids for e in encs], dtype=np.int64),
            "attention_mask": np.array([e.attention_mask for e in encs], dtype=np.int64),
        }
        if "token_type_ids" in self._inputs:
            feeds["token_type_ids"] = np.array([e.type_ids for e in encs], dtype=np.int64)
        (logits,) = cast(list[np.ndarray], self._sess.run(None, feeds))  # (B, 1)
        return logits.ravel().astype(np.float32)


class _StubReranker:
    """Reranker determinista para tests: solape de tokens query∩texto."""

    name = "stub"

    def score(self, query: str, texts: list[str]) -> np.ndarray:
        q_tokens = set(re.findall(r"\w+", query.lower()))
        out = np.zeros(len(texts), dtype=np.float32)
        for i, text in enumerate(texts):
            t_tokens = re.findall(r"\w+", text.lower())
            out[i] = sum(1.0 for t in t_tokens if t in q_tokens)
        return out


_embedder: _OnnxEmbedder | _StubEmbedder | None = None
_reranker: _OnnxReranker | _StubReranker | None = None
_embedder_lock = threading.Lock()


def get_embedder() -> _OnnxEmbedder | _StubEmbedder:
    """Singleton perezoso del encoder (carga el modelo solo al primer uso)."""
    global _embedder
    if _embedder is None:
        with _embedder_lock:
            if _embedder is None:
                _embedder = _StubEmbedder() if _flag("EMBED_STUB") else _OnnxEmbedder()
    return _embedder


def get_reranker() -> _OnnxReranker | _StubReranker:
    """Singleton perezoso del cross-encoder (mismo patrón que get_embedder)."""
    global _reranker
    if _reranker is None:
        with _embedder_lock:
            if _reranker is None:
                _reranker = _StubReranker() if _flag("EMBED_STUB") else _OnnxReranker()
    return _reranker


def current_model_name() -> str:
    """Nombre del encoder configurado, sin cargar el modelo.

    `name` es atributo de clase en ambos encoders, así que se puede saber con qué
    modelo se escribieron los vectores sin abrir la sesión ONNX — importa porque
    esto se consulta también con la semántica apagada.
    """
    return _StubEmbedder.name if _flag("EMBED_STUB") else _OnnxEmbedder.name


def reset_embedder() -> None:
    global _embedder, _reranker
    _embedder = None
    _reranker = None


# ── Storage helpers ──────────────────────────────────────────────────────────


def _to_blob(vec: np.ndarray) -> bytes:
    return np.asarray(vec, dtype=np.float32).tobytes()


def _from_blob(blob: bytes) -> np.ndarray:
    return np.frombuffer(blob, dtype=np.float32)


def _embed_text(title: str, chunk) -> str:
    """Lo que se embebe: la ruta del fragmento y luego su cuerpo.

    La ruta va dentro del embedding y no solo en una columna al lado. Una sección
    titulada «Renovación» solo significa algo junto a la página en la que vive, y un
    encoder que nunca ve el título de la página no puede situarla: dos secciones
    redactadas igual en páginas distintas producirían el mismo vector.

    El workspace no entra: la recuperación filtra por workspace, así que nunca
    desempata nada dentro de una búsqueda. La ruta completa que ve un agente se
    compone al leer, donde el nombre del workspace ya se conoce.
    """
    path = " > ".join([title, *chunk.headings]) if title else " > ".join(chunk.headings)
    return f"{path}\n\n{chunk.text}" if path else chunk.text


def reindex_page(page_id: int, workspace_id: int, title: str, content: str) -> int:
    """Chunkea, embebe y persiste los vectores de una página. Limpia embed_dirty."""
    embedder = get_embedder()
    chunks = meta.chunk_markdown(content)
    if not chunks:
        db.store_page_chunks(page_id, workspace_id, [], embedder.name, meta.CHUNKER_ID)
        return 0
    vectors = embedder.encode([_embed_text(title, c) for c in chunks])
    rows = [
        (i, chunks[i].text, " > ".join(chunks[i].headings), _to_blob(vectors[i]))
        for i in range(len(chunks))
    ]
    db.store_page_chunks(page_id, workspace_id, rows, embedder.name, meta.CHUNKER_ID)
    return len(rows)


def drain_pending(limit: int = 1000) -> int:
    """Procesa síncronamente todas las páginas sucias (útil en tests/CLI)."""
    done = 0
    while done < limit:
        pending = db.pages_to_embed(min(20, limit - done))
        if not pending:
            break
        for row in pending:
            reindex_page(int(row.id), int(row.workspace_id), row.title, row.content or "")
            done += 1
    return done


# ── Search ───────────────────────────────────────────────────────────────────


def _snippet(text: str, length: int = 240) -> str:
    text = " ".join(text.split())
    return text if len(text) <= length else text[:length].rstrip() + "…"


def _one_part(text: str) -> list[SnippetPart]:
    """Un fragmento semántico entero, sin resaltar: la semántica no casa términos.

    Existe para que /api/search devuelva `parts` con la misma forma en los tres
    modos — el cliente pinta tramos y no tiene que saber de dónde vino el hit.
    """
    return [SnippetPart(text=text, match=False)]


def _fts_results(workspace_id: int, query: str, k: int) -> list[dict]:
    rows = db.search_pages(workspace_id, query, limit=k)
    return [
        {
            "slug": r.slug,
            "title": r.title,
            "score": None,
            "chunk": r.snippet,
            "keyword_match": True,
            "via": "fts",
        }
        for r in rows
    ]


def semantic_search(
    workspace_id: int,
    query: str,
    *,
    k: int = 10,
    min_score: float | None = None,
) -> list[dict]:
    """La lista vectorial: similitud de embeddings, ordenada. Degrada a FTS si aplica.

    Solo el coseno. La mezcla con la búsqueda léxica vive en `search(mode="hybrid")`
    y se hace por rango, no sumando una constante a esta puntuación.

    Devuelve resultados explicables: slug, title, score y el mejor chunk (plan:
    "explainability over magic").

    `min_score` descarta los resultados por debajo del coseno dado. Sin él la lista
    trae siempre el workspace entero ordenado, que es lo que quiere un agente por
    MCP pero no un buscador. No aplica al fallback FTS (ahí el score es None).
    Con RERANK=1 el corte va antes del cross-encoder: este solo reordena lo que ya
    pasó el piso de coseno, no lo rescata.
    """
    query = (query or "").strip()
    if not query:
        return []
    if not semantic_enabled():
        return _fts_results(workspace_id, query, k)

    rows = db.workspace_chunk_vectors(workspace_id, current_model_name(), meta.CHUNKER_ID)
    if not rows:
        return _fts_results(workspace_id, query, k)

    qvec = get_embedder().encode([query])[0]
    mat = np.stack([_from_blob(r.vector) for r in rows])
    scores = mat @ qvec  # coseno (todo normalizado)

    best: dict[int, dict] = {}
    for idx, row in enumerate(rows):
        pid = int(row.page_id)
        score = float(scores[idx])
        if pid not in best or score > best[pid]["score"]:
            best[pid] = {
                "slug": row.slug,
                "title": row.title,
                "score": score,
                "chunk": row.text,
                "ord": int(row.ord),
            }

    results = list(best.values())
    for r in results:
        r["via"] = "semantic"

    # Desempate por slug: dos coseno idénticos ordenados por el orden de llegada de
    # la consulta harían que la misma búsqueda diera dos órdenes distintos.
    results.sort(key=lambda r: (-r["score"], r["slug"]))
    if min_score is not None:
        results = [r for r in results if r["score"] >= min_score]

    if rerank_enabled() and results:
        # Repuntúa los primeros candidatos con el cross-encoder y reordena por su
        # score; se conserva `score` (bi-encoder) para que el resultado siga
        # siendo explicable.
        pool = results[:RERANK_CANDIDATES]
        rerank_scores = get_reranker().score(query, [r["chunk"] for r in pool])
        for r, rerank_score in zip(pool, rerank_scores, strict=True):
            r["rerank_score"] = round(float(rerank_score), 4)
            r["via"] = "semantic+rerank"
        pool.sort(key=lambda r: r["rerank_score"], reverse=True)
        out = pool[:k]
    else:
        out = results[:k]

    for r in out:
        r["score"] = round(r["score"], 4)
        r["chunk"] = _snippet(r["chunk"])
    return out


def _rrf(rankings: list[tuple[float, list[str]]]) -> dict[str, float]:
    """Puntuación RRF por slug: suma de 1/(k + posición) en cada lista donde aparece.

    Se combina por posición y no por puntuación a propósito. Un coseno y un ts_rank
    no comparten unidad, así que cualquier constante que sume el uno al otro es
    arbitraria en algún punto de la lista: la vieja KEYWORD_BOOST de 0.1 era enorme
    al lado del hueco entre los puestos 3 y 4, y despreciable al lado del que hay
    entre el 1 y el 10.

    Una lista vacía no aporta nada y no rompe nada: si un canal no devuelve, la
    fusión es el orden del otro.
    """
    scores: dict[str, float] = {}
    for weight, ranking in rankings:
        for position, slug in enumerate(ranking, start=1):
            scores[slug] = scores.get(slug, 0.0) + weight / (RRF_K + position)
    return scores


def _hybrid(workspace_id: int, query: str, *, tags: list[str] | None = None) -> list[dict]:
    """Búsqueda híbrida: la lista léxica y la vectorial, fusionadas por rango.

    Antes esto concatenaba —los aciertos de FTS delante, los semánticos detrás— y
    eso ponía a FTS primero por posición y no por mérito: un acierto léxico mediocre
    tapaba uno semántico bueno. Se notaba en el arnés, donde `hybrid` perdía contra
    `semantic` sola en las consultas conceptuales.

    El fragmento que se enseña no cambia de fuente: si la página salió por FTS se
    sigue enseñando su extracto resaltado, que es lo que la barra lateral pinta en
    <mark>; si solo salió por la semántica, su chunk. Lo que cambia es el orden.
    """
    lexical = db.search_pages(workspace_id, query, tags=tags)
    vector = semantic_search(workspace_id, query, min_score=SEARCH_MIN_SCORE)
    if tags:
        # Las dos listas se acotan antes de fusionar, no después: filtrar el
        # resultado ya ordenado devolvería menos de lo que hay, y una página que hoy
        # queda fuera del corte tiene que poder salir cuando el filtro quita a las de
        # encima.
        allowed = db.slugs_with_tags(workspace_id, tags)
        vector = [hit for hit in vector if hit["slug"] in allowed]
    # Con la semántica apagada, o el workspace todavía sin indexar, `semantic_search`
    # ya devuelve aciertos de FTS. Fusionar FTS consigo misma no reordena nada y
    # además etiquetaría la procedencia como si hubieran votado dos canales: cuando
    # solo hay uno, la híbrida ES la léxica.
    if vector and vector[0]["via"] == "fts":
        vector = []

    lexical_rank = {hit.slug: i for i, hit in enumerate(lexical, start=1)}
    vector_rank = {hit["slug"]: i for i, hit in enumerate(vector, start=1)}
    scores = _rrf(
        [
            (1.0, [h.slug for h in lexical]),
            (RRF_VECTOR_WEIGHT, [h["slug"] for h in vector]),
        ]
    )

    by_slug: dict[str, dict] = {}
    for hit in vector:
        by_slug[hit["slug"]] = {**hit, "snippet": hit["chunk"], "parts": _one_part(hit["chunk"])}
    for hit in lexical:
        # El extracto de FTS gana porque trae el resaltado; el resto de campos del
        # acierto vectorial (score, chunk, ord) se conservan si también salió por ahí.
        existing = by_slug.get(hit.slug, {"slug": hit.slug, "title": hit.title, "score": None})
        by_slug[hit.slug] = {**existing, "snippet": hit.snippet, "parts": hit.parts}

    results = []
    for slug, row in by_slug.items():
        in_lexical = slug in lexical_rank
        in_vector = slug in vector_rank
        results.append(
            {
                **row,
                "rrf": round(scores[slug], 6),
                "keyword_match": in_lexical,
                # La procedencia es parte del resultado: quien elige entre dos
                # fragmentos necesita distinguir un acierto exacto de un vecino
                # semántico, y quien depura un orden malo necesita poder revisarlo.
                "via": "both"
                if in_lexical and in_vector
                else ("fts" if in_lexical else "semantic"),
                "lexical_rank": lexical_rank.get(slug),
                "vector_rank": vector_rank.get(slug),
            }
        )
    # Desempate por slug para que la misma consulta dé siempre el mismo orden.
    results.sort(key=lambda r: (-r["rrf"], r["slug"]))
    return results


def search(
    workspace_id: int,
    query: str,
    *,
    mode: str = "keyword",
    tags: list[str] | None = None,
) -> list[dict]:
    """Los tres modos del buscador: `keyword` (FTS), `semantic` y `hybrid`.

    Vive aquí y no en la ruta porque el harness de evaluación mide exactamente lo
    que recibe el usuario; si la mezcla de `hybrid` se quedara inline en el
    endpoint habría que reimplementarla para medirla, y entonces lo medido sería
    la copia y no el código que se despliega.
    """
    if not query.strip():
        return []

    if mode == "hybrid":
        return _hybrid(workspace_id, query, tags=tags)

    if mode == "semantic":
        results = list(semantic_search(workspace_id, query, min_score=SEARCH_MIN_SCORE))
        if tags:
            allowed = db.slugs_with_tags(workspace_id, tags)
            results = [r for r in results if r["slug"] in allowed]
        for r in results:
            r["snippet"] = r["chunk"]
            r["parts"] = _one_part(r["chunk"])
        return results

    return [
        {"slug": r.slug, "title": r.title, "snippet": r.snippet, "parts": r.parts}
        for r in db.search_pages(workspace_id, query, tags=tags)
    ]


# Presupuesto del contexto ensamblado, en caracteres. Antes eran seis fragmentos
# fijos, que no es una cota de nada: seis secciones cortas caben en cualquier sitio y
# seis largas se comen la ventana del modelo que las va a leer. 6000 caracteres son
# ~1500 tokens, que dejan sitio de sobra para la pregunta y la respuesta, y coinciden
# más o menos con seis fragmentos del techo del troceador — así el comportamiento por
# defecto se parece al de antes sin ser una cuenta.
CONTEXT_BUDGET = 6000

# Por encima de esta proporción de palabras en común, dos fragmentos dicen lo mismo.
# Alto a propósito: el error caro es descartar una sección que respondía.
DUPLICATE_OVERLAP = 0.8
# Por debajo de estas palabras el solape no significa nada —dos frases cortas del
# mismo tema comparten casi todo—, así que ahí solo cuenta la contención literal.
_MIN_WORDS_FOR_OVERLAP = 20


def _fold(text: str) -> str:
    """Minúsculas y sin tildes, para comparar como compara la búsqueda."""
    normalized = unicodedata.normalize("NFKD", text.casefold())
    return "".join(c for c in normalized if not unicodedata.combining(c))


def _words(text: str) -> set[str]:
    """Palabras del texto, plegadas y sin puntuación pegada.

    Mismo criterio que `db._fts_query`: sin esto `` `certbot `` con la comilla pegada
    no casaba con `certbot`, y la sección que respondía perdía contra la primera.
    """
    return set(re.findall(r"[\w]+", _fold(text), flags=re.UNICODE))


def _says_the_same(first: dict, second: dict) -> bool:
    """¿Estos dos fragmentos repiten el mismo pasaje?

    Tres formas de que lo hagan: venir de la misma sección de la misma página —son
    trozos de un mismo bloque partido por el techo—, que uno esté contenido en el
    otro, o que compartan casi todas sus palabras.

    Dos secciones *distintas* de una misma página no son duplicados: responden a
    partes distintas de la pregunta, y colapsarlas sería el error contrario.
    """
    if first["slug"] == second["slug"] and first["section"] == second["section"]:
        return True

    a, b = _fold(" ".join(first["text"].split())), _fold(" ".join(second["text"].split()))
    if a in b or b in a:
        return True

    words_a, words_b = _words(first["text"]), _words(second["text"])
    smaller = min(len(words_a), len(words_b))
    if smaller < _MIN_WORDS_FOR_OVERLAP:
        return False
    return len(words_a & words_b) / smaller >= DUPLICATE_OVERLAP


def _pack_context(
    candidates: list[dict], budget: int, limit: int | None
) -> tuple[list[dict], bool]:
    """Escoge fragmentos en orden hasta agotar el presupuesto. (elegidos, se recortó).

    Un fragmento que no cabe se deja fuera entero y se sigue con el siguiente: cortarlo
    por la mitad devolvería un texto que la página no dice, y pararse en seco dejaría
    el presupuesto sin usar porque justo el segundo era enorme.
    """
    kept: list[dict] = []
    used = 0
    truncated = False
    for candidate in candidates:
        if limit is not None and len(kept) >= limit:
            truncated = True
            break
        if any(_says_the_same(candidate, chosen) for chosen in kept):
            continue
        size = len(candidate["text"])
        if used + size > budget:
            truncated = True
            continue
        kept.append(candidate)
        used += size
    return kept, truncated


def _context_path(workspace: str, title: str, section: str) -> str:
    """`Workspace > Página > Sección`, saltándose los tramos vacíos.

    Es lo que sitúa un fragmento leído por su cuenta. Sin él, el agente recibía
    «corre certbot renew» sin saber de qué runbook ni de qué máquina hablaba.
    """
    return " > ".join(part for part in [workspace, title, section] if part)


def _fts_context(workspace_id: int, query: str, workspace: str, pages: int) -> list[dict]:
    """Candidatos del canal léxico: secciones enteras, no extractos de ranking.

    `ts_headline` devuelve doce palabras elegidas para enseñarle a una persona por qué
    coincidió un resultado. Sirve para ordenar y no para responder: un agente que
    recibía eso recibía trozos de frase. Aquí se trocea la página igual que la trocea
    el indexador y se elige la sección que más términos de la consulta contiene, de
    modo que el fragmento sea el mismo que devolvería el canal vectorial.

    Se trocea al vuelo porque con la semántica apagada no corre el worker y no hay
    fragmentos guardados. Es el camino degradado y solo paga quien está en él.
    """
    terms = {word for word in _words(query) if len(word) > 2}
    candidates: list[dict] = []
    for hit in db.search_pages(workspace_id, query, limit=pages):
        page = db.get_page(hit.slug, workspace_id)
        if page is None:
            continue
        # Empate a cero —la coincidencia de FTS venía de un stem que la comparación
        # literal no ve— se resuelve con la primera sección, que es la apertura de la
        # página y lo más parecido a un resumen que hay sin inventar nada.
        best = None
        best_score = -1.0
        for chunk in meta.chunk_markdown(page.content):
            score = len(terms & _words(chunk.text)) / len(terms) if terms else 0.0
            if score > best_score:
                best, best_score = chunk, score
        if best is None:
            continue
        section = " > ".join(best.headings)
        candidates.append(
            {
                "slug": hit.slug,
                "title": hit.title,
                "ord": None,
                # Sin vectores no hay coseno que informar. None y no un número
                # inventado: un score falso se compararía con los de verdad.
                "score": None,
                "path": _context_path(workspace, hit.title, section),
                "section": section,
                "text": best.text,
            }
        )
    return candidates


def rag_context(
    workspace_id: int,
    query: str,
    *,
    budget: int = CONTEXT_BUDGET,
    limit: int | None = None,
) -> dict:
    """rag como tubería de retrieval: fragmentos + procedencia, SIN generar texto.

    El agente sintetiza la respuesta a partir de estos fragmentos. Todo lo que sale de
    aquí está literalmente en una página guardada.

    Acotado por presupuesto de caracteres y no por número de fragmentos, y sin repetir
    un pasaje dos veces: el contexto de un agente es un recurso escaso y gastarlo dos
    veces en la misma frase es gastarlo mal. `limit` sigue aceptándose como tope de
    piezas para quien quiera menos, pero la cota es el presupuesto.
    """
    query = (query or "").strip()
    if not query:
        return {"query": query, "mode": "empty", "chunks": [], "truncated": False}

    ws = db.get_workspace_by_id(workspace_id)
    workspace = ws.name if ws else ""

    # Cuántos candidatos mirar antes de empaquetar. Con el techo del troceador en
    # 1000 caracteres, el doble del presupuesto siempre trae de sobra para llenarlo
    # aunque la mitad se caiga por duplicada.
    pool = max(1, (2 * budget) // 500)

    candidates: list[dict] = []
    mode = "fts"
    if semantic_enabled():
        rows = db.workspace_chunk_vectors(workspace_id, current_model_name(), meta.CHUNKER_ID)
        if rows:
            mode = "semantic"
            qvec = get_embedder().encode([query])[0]
            mat = np.stack([_from_blob(r.vector) for r in rows])
            scores = mat @ qvec
            candidates = [
                {
                    "slug": rows[i].slug,
                    "title": rows[i].title,
                    "ord": int(rows[i].ord),
                    "score": round(float(scores[i]), 4),
                    "path": _context_path(workspace, rows[i].title, rows[i].path),
                    "section": rows[i].path,
                    "text": rows[i].text,
                }
                for i in np.argsort(-scores)[:pool]
            ]

    if mode == "fts":
        candidates = _fts_context(workspace_id, query, workspace, pool)

    chunks, truncated = _pack_context(candidates, budget, limit)
    return {"query": query, "mode": mode, "chunks": chunks, "truncated": truncated}


# ── Background enrichment (sin broker; plan §5 "queue job, enrich later") ──────


async def enrichment_worker(*, interval: float = 2.0, batch: int = 5) -> None:
    """Loop async que embebe páginas sucias en un threadpool (no bloquea el loop)."""
    import asyncio

    logger.info("embedding worker iniciado (model dir=%s)", _MODELS_DIR)
    # Un cambio de encoder deja vectores de otro espacio en la tabla; compararlos
    # por coseno no significa nada. Se re-encolan antes de servir nada nuevo.
    stale = await asyncio.to_thread(
        db.mark_stale_model_dirty, current_model_name(), meta.CHUNKER_ID
    )
    if stale:
        logger.info("reindexando %d páginas: cambió el modelo o el troceador", stale)
    while True:
        try:
            pending = await asyncio.to_thread(db.pages_to_embed, batch)
            if not pending:
                await asyncio.sleep(interval)
                continue
            for row in pending:
                # try/except por página: sin esto, una página que siempre falla
                # encabezaba cada batch y bloqueaba la cola para siempre.
                try:
                    await asyncio.to_thread(
                        reindex_page,
                        int(row.id),
                        int(row.workspace_id),
                        row.title,
                        row.content or "",
                    )
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.exception(
                        "no se pudo indexar la página %s; se salta hasta su próxima edición",
                        row.id,
                    )
                    await asyncio.to_thread(db.clear_embed_dirty, int(row.id))
        except asyncio.CancelledError:
            logger.info("embedding worker detenido")
            raise
        except Exception:
            logger.exception("embedding worker error; reintentando")
            await asyncio.sleep(interval)
