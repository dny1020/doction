"""Búsqueda semántica local: embeddings ONNX (MiniLM), sin servicios en la nube.

Opt-in vía `SEMANTIC_SEARCH=1`. Si está apagado (o no hay vectores aún), todo
degrada con gracia a la búsqueda de texto completo de Postgres. doction hace
*retrieval*; la generación (RAG, resúmenes) la hace el agente conectado por
MCP — aquí no vive ningún LLM.

El modelo se carga perezosamente y solo cuando se usa, para no gastar RAM en un
Pi cuando la función está apagada. Para tests, `EMBED_STUB=1` usa un encoder
determinista (bag-of-words) y evita depender del modelo real.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import threading
from pathlib import Path

import numpy as np

from app import db, meta

logger = logging.getLogger(__name__)

EMBED_DIM = 384
MAX_TOKENS = 256
KEYWORD_BOOST = 0.1  # plan §4: "embedding similarity + keyword boost"

_DEFAULT_MODELS_DIR = Path(__file__).resolve().parent.parent / "models"
_MODELS_DIR = Path(os.environ.get("MODEL_DIR") or _DEFAULT_MODELS_DIR)
MODEL_PATH = str(_MODELS_DIR / "model_quantized.onnx")
TOKENIZER_PATH = str(_MODELS_DIR / "tokenizer.json")

_MARK_RE = re.compile(r"</?mark>")


def _flag(name: str) -> bool:
    return os.environ.get(name, "").lower() in {"1", "true", "yes"}


def semantic_enabled() -> bool:
    """True si la búsqueda semántica está activada por entorno."""
    return _flag("SEMANTIC_SEARCH")


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
        (last_hidden,) = self._sess.run(None, feeds)  # (B, S, 384)
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


_embedder: _OnnxEmbedder | _StubEmbedder | None = None
_embedder_lock = threading.Lock()


def get_embedder() -> _OnnxEmbedder | _StubEmbedder:
    """Singleton perezoso del encoder (carga el modelo solo al primer uso)."""
    global _embedder
    if _embedder is None:
        with _embedder_lock:
            if _embedder is None:
                _embedder = _StubEmbedder() if _flag("EMBED_STUB") else _OnnxEmbedder()
    return _embedder


def reset_embedder() -> None:
    global _embedder
    _embedder = None


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
    return _MARK_RE.sub("", snippet or "")


def _result_score(result: dict) -> float:
    """Clave de ordenación: la puntuación de un resultado de búsqueda."""
    return result["score"]


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
) -> list[dict]:
    """sgrep: similitud de embeddings + boost por keyword. Degrada a FTS si aplica.

    Devuelve resultados explicables: slug, title, score y el mejor chunk (plan:
    "explainability over magic").
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

    results.sort(key=_result_score, reverse=True)
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

    rows = db.search_pages(user_id, workspace_id, query, limit=k)
    chunks = [
        {
            "slug": r.slug,
            "title": r.title,
            "ord": None,
            "score": None,
            "text": _clean(r.snippet),
        }
        for r in rows
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
                await asyncio.to_thread(
                    reindex_page, int(row.id), int(row.workspace_id), row.content or ""
                )
        except asyncio.CancelledError:
            logger.info("embedding worker detenido")
            raise
        except Exception:
            logger.exception("embedding worker error; reintentando")
            await asyncio.sleep(interval)
