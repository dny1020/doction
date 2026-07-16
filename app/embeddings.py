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
from pathlib import Path
from typing import cast

import numpy as np

from app import db, meta

logger = logging.getLogger(__name__)

EMBED_DIM = 384
MAX_TOKENS = 256
KEYWORD_BOOST = 0.1  # plan §4: "embedding similarity + keyword boost"
RERANK_CANDIDATES = 20  # cuántos resultados del bi-encoder repuntúa el cross-encoder
# Corte del buscador de la UI. Medido sobre el wiki: los aciertos caen entre 0.38 y
# 0.86, y por debajo de 0.35 solo aparece relleno (cualquier página contra cualquier
# consulta). Recorta el listado de ~10 a 1-5 sin perder aciertos; no separa del todo
# señal de ruido —el ruido llega a 0.48— así que ordena, no decide.
SEARCH_MIN_SCORE = 0.35

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


def reset_embedder() -> None:
    global _embedder, _reranker
    _embedder = None
    _reranker = None


# ── Storage helpers ──────────────────────────────────────────────────────────


def _to_blob(vec: np.ndarray) -> bytes:
    return np.asarray(vec, dtype=np.float32).tobytes()


def _from_blob(blob: bytes) -> np.ndarray:
    return np.frombuffer(blob, dtype=np.float32)


def reindex_page(page_id: int, workspace_id: int, content: str) -> int:
    """Chunkea, embebe y persiste los vectores de una página. Limpia embed_dirty."""
    embedder = get_embedder()
    chunks = meta.chunk_markdown(content)
    if not chunks:
        db.store_page_chunks(page_id, workspace_id, [], embedder.name)
        return 0
    vectors = embedder.encode(chunks)
    rows = [(i, chunks[i], _to_blob(vectors[i])) for i in range(len(chunks))]
    db.store_page_chunks(page_id, workspace_id, rows, embedder.name)
    return len(rows)


def drain_pending(limit: int = 1000) -> int:
    """Procesa síncronamente todas las páginas sucias (útil en tests/CLI)."""
    done = 0
    while done < limit:
        pending = db.pages_to_embed(min(20, limit - done))
        if not pending:
            break
        for row in pending:
            reindex_page(int(row.id), int(row.workspace_id), row.content or "")
            done += 1
    return done


# ── Search ───────────────────────────────────────────────────────────────────


def _snippet(text: str, length: int = 240) -> str:
    text = " ".join(text.split())
    return text if len(text) <= length else text[:length].rstrip() + "…"


def _clean(snippet: str) -> str:
    snippet = snippet or ""
    return snippet.replace("<mark>", "").replace("</mark>", "")


def _fts_results(user_id: int, workspace_id: int, query: str, k: int) -> list[dict]:
    rows = db.search_pages(user_id, workspace_id, query, limit=k)
    return [
        {
            "slug": r.slug,
            "title": r.title,
            "score": None,
            "chunk": _clean(r.snippet),
            "keyword_match": True,
            "via": "fts",
        }
        for r in rows
    ]


def semantic_search(
    user_id: int,
    workspace_id: int,
    query: str,
    *,
    k: int = 10,
    keyword_boost: bool = True,
    min_score: float | None = None,
) -> list[dict]:
    """sgrep: similitud de embeddings + boost por keyword. Degrada a FTS si aplica.

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
        return _fts_results(user_id, workspace_id, query, k)

    rows = db.workspace_chunk_vectors(user_id, workspace_id)
    if not rows:
        return _fts_results(user_id, workspace_id, query, k)

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
    keyword_slugs: set[str] = set()
    if keyword_boost:
        for hit in db.search_pages(user_id, workspace_id, query):
            keyword_slugs.add(hit.slug)
    for r in results:
        r["keyword_match"] = r["slug"] in keyword_slugs
        if r["keyword_match"]:
            r["score"] += KEYWORD_BOOST
        r["via"] = "semantic"

    results.sort(key=lambda r: r["score"], reverse=True)
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


def rag_context(user_id: int, workspace_id: int, query: str, *, k: int = 6) -> dict:
    """rag como tubería de retrieval: top-k chunks + procedencia, SIN generar texto.

    El agente sintetiza la respuesta a partir de estos fragmentos.
    """
    query = (query or "").strip()
    if not query:
        return {"query": query, "mode": "empty", "chunks": []}

    if semantic_enabled():
        rows = db.workspace_chunk_vectors(user_id, workspace_id)
        if rows:
            qvec = get_embedder().encode([query])[0]
            mat = np.stack([_from_blob(r.vector) for r in rows])
            scores = mat @ qvec
            order = np.argsort(-scores)[:k]
            chunks = [
                {
                    "slug": rows[i].slug,
                    "title": rows[i].title,
                    "ord": int(rows[i].ord),
                    "score": round(float(scores[i]), 4),
                    "text": rows[i].text,
                }
                for i in order
            ]
            return {"query": query, "mode": "semantic", "chunks": chunks}

    hits = db.search_pages(user_id, workspace_id, query, limit=k)
    chunks = [
        {
            "slug": h.slug,
            "title": h.title,
            "ord": None,
            "score": None,
            "text": _clean(h.snippet),
        }
        for h in hits
    ]
    return {"query": query, "mode": "fts", "chunks": chunks}


# ── Background enrichment (sin broker; plan §5 "queue job, enrich later") ──────


async def enrichment_worker(*, interval: float = 2.0, batch: int = 5) -> None:
    """Loop async que embebe páginas sucias en un threadpool (no bloquea el loop)."""
    import asyncio

    logger.info("embedding worker iniciado (model dir=%s)", _MODELS_DIR)
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
                        reindex_page, int(row.id), int(row.workspace_id), row.content or ""
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
