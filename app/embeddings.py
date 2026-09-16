"""Local semantic search: ONNX MiniLM embeddings, no cloud services.

Opt-in via `SEMANTIC_SEARCH=1`; with it off, or with nothing indexed yet, everything
degrades to Postgres full-text search. The model loads lazily so a Pi with the feature
off pays no RAM. `EMBED_STUB=1` swaps in a deterministic bag-of-words encoder for tests.
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
from app.models import ChunkVector, SnippetPart

logger = logging.getLogger(__name__)

EMBED_DIM = 384
MAX_TOKENS = 256
# Tie-breaks *which section* of a page is returned, never which page wins: page order is
# plain cosine, computed separately. Some queries are answered by the heading and not by
# the body beneath it.
HEADING_MATCH_BOOST = 0.15

# Reciprocal rank fusion constant, from the original paper (Cormack et al., 2009).
RRF_K = 60
# Weight of the vector list in the fusion. Unweighted RRF scores worse than semantic
# alone: over this corpus the lists are not worth the same (FTS 0.46 MRR, vectors 0.77).
# The sweep plateaus at 1.5; 2.0 is the low end of that plateau.
# See evals/results/2026-09-03-rrf-weight-sweep.json.
RRF_VECTOR_WEIGHT = 2.0
# Cross-encoder rescoring window. Deliberately unswept — the reranker buys nothing
# measurable and costs 29x median latency, so it stays off. See evals/results/.
RERANK_CANDIDATES = 20
# Floor for the UI search box: it decides what is hidden, not how results are ordered.
# recall@1 is flat from 0.25 to 0.40, so a higher floor only truncates the tail — 0.35
# hid 4 correct hits and doubled empty result lists.
# See evals/results/2026-08-24-minilm-en.json.
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
    return _flag("SEMANTIC_SEARCH")


def rerank_enabled() -> bool:
    return _flag("RERANK") and semantic_enabled()


def _l2_normalize(mat: np.ndarray) -> np.ndarray:
    norms = np.clip(np.linalg.norm(mat, axis=1, keepdims=True), 1e-9, None)
    return (mat / norms).astype(np.float32)


# ── Encoders ─────────────────────────────────────────────────────────────────


class _OnnxEmbedder:
    """MiniLM int8 over onnxruntime: mean-pooling then L2 normalize."""

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
        # run() is typed Sequence[ndarray | SparseTensor | list | dict]; this model
        # always returns one dense tensor.
        (last_hidden,) = cast(list[np.ndarray], self._sess.run(None, feeds))  # (B, S, 384)
        mask = attention[:, :, None].astype(np.float32)
        summed = (last_hidden * mask).sum(axis=1)
        counts = np.clip(mask.sum(axis=1), 1e-9, None)
        return _l2_normalize(summed / counts)


class _StubEmbedder:
    """Deterministic bag-of-words encoder for tests; no model file needed."""

    name = "stub"

    def encode(self, texts: list[str]) -> np.ndarray:
        out = np.zeros((len(texts), EMBED_DIM), dtype=np.float32)
        for i, text in enumerate(texts):
            for token in re.findall(r"\w+", text.lower()):
                h = int(hashlib.sha1(token.encode()).hexdigest(), 16)
                out[i, h % EMBED_DIM] += 1.0
        return _l2_normalize(out)


class _OnnxReranker:
    """Cross-encoder scoring (query, text) pairs; sees both together, so it orders better."""

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
    """Deterministic reranker for tests: query/text token overlap."""

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
    global _embedder
    if _embedder is None:
        with _embedder_lock:
            if _embedder is None:
                _embedder = _StubEmbedder() if _flag("EMBED_STUB") else _OnnxEmbedder()
    return _embedder


def get_reranker() -> _OnnxReranker | _StubReranker:
    global _reranker
    if _reranker is None:
        with _embedder_lock:
            if _reranker is None:
                _reranker = _StubReranker() if _flag("EMBED_STUB") else _OnnxReranker()
    return _reranker


def current_model_name() -> str:
    """The configured encoder's name, read off the class so no ONNX session is opened."""
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
    """The section's own heading, then its body.

    The page title and ancestor chain are deliberately left out: every section of a page
    shares that prefix, so it says nothing about which one answers, and including it held
    sibling sections at 0.685 mean cosine. Dropping the heading too measures worse still.
    Identical sections in different pages therefore embed identically, which is correct —
    the page ranking separates them through the lexical channel, which does see the title.
    """
    heading = chunk.headings[-1] if chunk.headings else title
    return f"# {heading}\n\n{chunk.text}" if heading else chunk.text


def reindex_page(page_id: int, workspace_id: int, title: str, content: str) -> int:
    """Chunk, embed and store a page's vectors, clearing embed_dirty."""
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
    """Embed every dirty page synchronously; for tests and the CLI."""
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
    """A whole semantic chunk, unhighlighted, so `parts` has one shape across all modes."""
    return [SnippetPart(text=text, match=False)]


def _fts_results(
    workspace_id: int, query: str, k: int, tags: list[str] | None = None
) -> list[dict]:
    rows = db.search_pages(workspace_id, query, limit=k, tags=tags)
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
    tags: list[str] | None = None,
) -> list[dict]:
    """The vector list: cosine similarity, ranked. Falls back to FTS when unavailable.

    Cosine only — the lexical mix lives in `search(mode="hybrid")` and fuses by rank.
    Without `min_score` the list is the whole workspace in order, which is what an agent
    over MCP wants and a search box does not. The floor applies before the cross-encoder,
    so reranking reorders what passed it and never rescues what did not.
    """
    query = (query or "").strip()
    if not query:
        return []
    if not semantic_enabled():
        return _fts_results(workspace_id, query, k, tags=tags)

    rows = db.workspace_chunk_vectors(workspace_id, current_model_name(), meta.CHUNKER_ID)
    if tags:
        # Narrowed before scoring, not after: the fusion combines by position, so an
        # excluded page left holding a rank counts as much as a result.
        allowed = db.slugs_with_tags(workspace_id, tags)
        rows = [row for row in rows if row.slug in allowed]
    if not rows:
        return _fts_results(workspace_id, query, k, tags=tags)

    qvec = get_embedder().encode([query])[0]
    mat = np.stack([_from_blob(r.vector) for r in rows])
    scores = mat @ qvec  # cosine; everything is normalized

    terms = {word for word in _words(query) if len(word) > 2}

    best: dict[int, dict] = {}
    for idx, row in enumerate(rows):
        pid = int(row.page_id)
        score = float(scores[idx])
        # Two criteria on purpose: `score` is plain cosine and ranks pages, `pick` only
        # chooses which section represents this one.
        pick = score + HEADING_MATCH_BOOST * _heading_match(terms, row.path)
        previous = best.get(pid)
        top = max(score, previous["score"]) if previous else score
        if previous is None or pick > previous["_pick"]:
            best[pid] = {
                "slug": row.slug,
                "title": row.title,
                "score": score,
                "chunk": row.text,
                "ord": int(row.ord),
                "section": row.path,
                "page_type": row.page_type,
                "tags": row.tags,
                "_pick": pick,
            }
        # Carried separately because switching representative section rebuilds the dict.
        best[pid]["score"] = top

    results = list(best.values())
    for r in results:
        r.pop("_pick", None)
        r["via"] = "semantic"

    # Slug tie-break, so the same query always returns the same order.
    results.sort(key=lambda r: (-r["score"], r["slug"]))
    if min_score is not None:
        results = [r for r in results if r["score"] >= min_score]

    if rerank_enabled() and results:
        # `score` stays the bi-encoder's, so the result is still explainable.
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
    """RRF score per slug: the sum of 1/(k + position) over every list it appears in.

    By position and not by score, because a cosine and a ts_rank share no unit: any
    constant added from one to the other is arbitrary somewhere down the list. An empty
    list contributes nothing, so one dead channel leaves the other's order intact.
    """
    scores: dict[str, float] = {}
    for weight, ranking in rankings:
        for position, slug in enumerate(ranking, start=1):
            scores[slug] = scores.get(slug, 0.0) + weight / (RRF_K + position)
    return scores


def _hybrid(workspace_id: int, query: str, *, tags: list[str] | None = None) -> list[dict]:
    """The lexical and vector lists, fused by rank.

    Only the order is fused. A page found by FTS still shows its highlighted extract —
    what the sidebar renders in <mark> — and one found only by vectors shows its chunk.
    """
    # Each list is narrowed inside its own engine: fusing positions requires the
    # positions to already be counted over the filtered set.
    lexical = db.search_pages(workspace_id, query, tags=tags)
    vector = semantic_search(workspace_id, query, min_score=SEARCH_MIN_SCORE, tags=tags)
    # With semantics off, or nothing indexed, `semantic_search` already returned FTS
    # hits. Fusing FTS with itself reorders nothing and would claim two channels voted.
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
        # The FTS extract wins because it carries the highlighting; the vector hit's
        # other fields survive if the page came through both.
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
                "via": "both"
                if in_lexical and in_vector
                else ("fts" if in_lexical else "semantic"),
                "lexical_rank": lexical_rank.get(slug),
                "vector_rank": vector_rank.get(slug),
            }
        )
    # Slug tie-break, so the same query always returns the same order.
    results.sort(key=lambda r: (-r["rrf"], r["slug"]))
    return results


def search(
    workspace_id: int,
    query: str,
    *,
    mode: str = "keyword",
    tags: list[str] | None = None,
) -> list[dict]:
    """The three search modes: `keyword` (FTS), `semantic` and `hybrid`.

    Here rather than in the route so the evaluation harness measures what users get
    instead of a reimplementation of it.
    """
    if not query.strip():
        return []

    if mode == "hybrid":
        return _hybrid(workspace_id, query, tags=tags)

    if mode == "semantic":
        results = list(semantic_search(workspace_id, query, min_score=SEARCH_MIN_SCORE, tags=tags))
        for r in results:
            r["snippet"] = r["chunk"]
            r["parts"] = _one_part(r["chunk"])
        return results

    return [
        {"slug": r.slug, "title": r.title, "snippet": r.snippet, "parts": r.parts}
        for r in db.search_pages(workspace_id, query, tags=tags)
    ]


# Assembled context budget, in characters (~1500 tokens), bounding the chunks rather
# than counting them: six long sections eat the window of the model that reads them.
CONTEXT_BUDGET = 6000

# Above this share of shared words, two chunks say the same thing. High on purpose:
# the expensive mistake is dropping a section that answered.
DUPLICATE_OVERLAP = 0.8
# Below this many words overlap means nothing, so only literal containment counts.
_MIN_WORDS_FOR_OVERLAP = 20


def _fold(text: str) -> str:
    """Lowercased and unaccented, matching how search compares."""
    normalized = unicodedata.normalize("NFKD", text.casefold())
    return "".join(c for c in normalized if not unicodedata.combining(c))


def _words(text: str) -> set[str]:
    """Words, folded and stripped of attached punctuation, as `db._fts_query` splits them."""
    return set(re.findall(r"[\w]+", _fold(text), flags=re.UNICODE))


def _heading_match(terms: set[str], path: str) -> float:
    """What share of the query's terms appear in the heading path.

    Graded rather than binary, and over the whole path: an ancestor heading also places
    a section.
    """
    if not terms or not path:
        return 0.0
    return len(terms & _words(path)) / len(terms)


def _says_the_same(first: dict, second: dict) -> bool:
    """Whether two chunks repeat the same passage.

    Three ways to: same section of the same page, one contained in the other, or nearly
    all words shared. Two *different* sections of one page are not duplicates.
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
    """Take chunks in order until the budget runs out; returns (kept, truncated).

    A chunk that does not fit is skipped whole rather than cut: half a chunk is text the
    page does not say, and stopping at the first overflow wastes the rest of the budget.
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
    """`Workspace > Page > Section`, skipping empty parts, so a chunk read alone is placed."""
    return " > ".join(part for part in [workspace, title, section] if part)


def _fts_context(workspace_id: int, query: str, workspace: str, pages: int) -> list[dict]:
    """Lexical-channel candidates: whole sections, not ranking extracts.

    `ts_headline` returns twelve words chosen to show a person why a result matched —
    good for ordering, useless as an answer. The page is chunked the same way the indexer
    chunks it, on the fly, since with semantics off no worker has stored anything.
    """
    terms = {word for word in _words(query) if len(word) > 2}
    candidates: list[dict] = []
    for hit in db.search_pages(workspace_id, query, limit=pages):
        page = db.get_page(hit.slug, workspace_id)
        if page is None:
            continue
        # An all-zero tie (FTS matched on a stem literal comparison cannot see) resolves
        # to the first section, the page's opening.
        best = None
        best_score = -1.0
        for chunk in meta.chunk_markdown(page.content):
            score = len(terms & _words(chunk.text)) / len(terms) if terms else 0.0
            if score > best_score:
                best, best_score = chunk, score
        if best is None:
            continue
        section = " > ".join(best.headings)
        front, _ = meta.parse_frontmatter(page.content)
        candidates.append(
            {
                "slug": hit.slug,
                "title": hit.title,
                "ord": None,
                # No vectors, no cosine to report: None rather than an invented number.
                "score": None,
                "path": _context_path(workspace, hit.title, section),
                "section": section,
                "page_type": front.get("type"),
                "tags": meta.extract_tags(page.content),
                "text": best.text,
            }
        )
    return candidates


def _section_candidates(workspace_id: int, query: str, workspace: str, pool: int) -> list[dict]:
    """Candidate chunks: the fusion picks the pages, cosine picks the section.

    Walked in rounds — the best section of every page, then each page's second — so the
    budget spreads sideways first. An agent assembling context wants one section from
    every relevant page before five from the first.
    """
    rows = db.workspace_chunk_vectors(workspace_id, current_model_name(), meta.CHUNKER_ID)
    if not rows:
        return []

    # The vector work is done once and reused for both decisions. Calling `_hybrid` here
    # would load the vectors and encode the query a second time: 187 ms median, not 12.
    qvec = get_embedder().encode([query])[0]
    mat = np.stack([_from_blob(r.vector) for r in rows])
    scores = mat @ qvec
    terms = {word for word in _words(query) if len(word) > 2}

    by_page: dict[str, list[tuple[float, float, ChunkVector]]] = {}
    top: dict[str, float] = {}
    for i, row in enumerate(rows):
        score = float(scores[i])
        pick = score + HEADING_MATCH_BOOST * _heading_match(terms, row.path)
        by_page.setdefault(row.slug, []).append((pick, score, row))
        top[row.slug] = max(top.get(row.slug, score), score)
    for chunks in by_page.values():
        chunks.sort(key=lambda item: -item[0])

    # Same fusion the UI and MCP serve: its lexical half carries the title signal the
    # vector channel gave up when the title left the embedding.
    vector_order = sorted(top, key=lambda slug: (-top[slug], slug))
    lexical_order = [hit.slug for hit in db.search_pages(workspace_id, query)]
    fused = _rrf([(1.0, lexical_order), (RRF_VECTOR_WEIGHT, vector_order)])
    if not fused:
        return []
    order = {slug: i for i, slug in enumerate(sorted(fused, key=lambda s: (-fused[s], s)))}

    # `pool` bounds the candidates, not the pages: deduplication compares each candidate
    # against every kept one, so a long list costs quadratically.
    pages = sorted((s for s in by_page if s in order), key=lambda slug: order[slug])
    candidates: list[dict] = []
    for round_ in range(max(len(by_page[slug]) for slug in pages)):
        for slug in pages:
            if round_ >= len(by_page[slug]):
                continue
            _, score, row = by_page[slug][round_]
            if len(candidates) >= pool:
                return candidates
            candidates.append(
                {
                    "slug": row.slug,
                    "title": row.title,
                    "ord": int(row.ord),
                    "score": round(score, 4),
                    "path": _context_path(workspace, row.title, row.path),
                    "section": row.path,
                    "page_type": row.page_type,
                    "tags": row.tags,
                    "text": row.text,
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
    """Retrieval only: chunks plus provenance, no generated text.

    Everything returned is literally in a stored page; the agent synthesises the answer.
    Bounded by character budget rather than chunk count, and never repeating a passage.
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
        candidates = _section_candidates(workspace_id, query, workspace, pool)
        if candidates:
            mode = "semantic"

    if mode == "fts":
        candidates = _fts_context(workspace_id, query, workspace, pool)

    chunks, truncated = _pack_context(candidates, budget, limit)
    return {"query": query, "mode": mode, "chunks": chunks, "truncated": truncated}


# ── Background enrichment (no broker) ────────────────────────────────────────


async def enrichment_worker(*, interval: float = 2.0, batch: int = 5) -> None:
    """Embeds dirty pages in a threadpool so the event loop stays free."""
    import asyncio

    logger.info("embedding worker started (model dir=%s)", _MODELS_DIR)
    # A changed encoder leaves vectors from another space in the table; comparing them
    # by cosine means nothing, so they are re-queued before anything new is served.
    stale = await asyncio.to_thread(
        db.mark_stale_model_dirty, current_model_name(), meta.CHUNKER_ID
    )
    if stale:
        logger.info("reindexing %d pages: model or chunker changed", stale)
    while True:
        try:
            pending = await asyncio.to_thread(db.pages_to_embed, batch)
            if not pending:
                await asyncio.sleep(interval)
                continue
            for row in pending:
                # Per page, so one page that always fails cannot head every batch.
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
                    logger.exception("could not index page %s; skipping until edited", row.id)
                    await asyncio.to_thread(db.clear_embed_dirty, int(row.id))
        except asyncio.CancelledError:
            logger.info("embedding worker stopped")
            raise
        except Exception:
            logger.exception("embedding worker error; retrying")
            await asyncio.sleep(interval)
