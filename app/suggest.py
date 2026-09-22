"""Local suggestions without an LLM: wikilinks, tags, duplicates and TextRank summaries.

Everything runs on what already exists: the MiniLM vectors in `page_chunks` and the
markdown itself. Each function degrades to a text heuristic with semantic search off,
and says which it used in its `mode` field.
"""

import logging
import math
import re
from collections import Counter

import numpy as np

from app import db, embeddings, graph, meta
from app.models import ChunkVector

logger = logging.getLogger(__name__)

# Generous on purpose: suggestions are top-5 and carry a visible score, so erring
# wide beats looking like a dead feature.
LINK_THRESHOLD = 0.40
DUP_THRESHOLD = 0.90
TAG_VOCAB_BOOST = 1.5  # favours terms already used as tags elsewhere in the workspace
MAX_SUMMARY_SENTENCES = 120  # per page, to bound the cost on a Pi
MIN_SENTENCE_CHARS = 25
MIN_CLUSTER_PAGES = 6

_WORD_RE = re.compile(r"[a-záéíóúüñ][a-z0-9áéíóúüñ_-]{2,}")
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")

# Minimal EN+ES stopwords: enough for TF-IDF over a technical wiki without pulling in
# a dependency for the list.
STOPWORDS = frozenset(
    """
    the a an and or but if then else for while of to in on at by with from as is are was
    were be been being have has had do does did will would should could can may might must
    not no nor so than that this these those it its they them their there here what which
    who whom when where why how all any both each few more most other some such only own
    same very just also into over under again further once about between through during
    before after above below out off up down you your yours she her him his we our us
    el la los las un una unos unas y o pero si entonces para mientras de del al en con
    por como es son era eran ser sido estar esta este estos estas ese esa esos esas
    aquel aquella no ni que cual quien cuando donde porque como todo toda todos todas
    cada mas menos otro otra otros otras alguno alguna algo tan muy solo tambien entre
    sobre desde hasta durante antes despues arriba abajo hay fue han sus tu tus su
    nosotros vosotros ellos ellas usted ustedes se lo le les mi mis te ya
    http https www com org net
    """.split()
)


def tokenize(content: str) -> list[str]:
    """Lowercased body tokens, with frontmatter, code and stopwords removed."""
    _, body = meta.parse_frontmatter(content or "")
    text = meta.strip_code(body).lower()
    return [t for t in _WORD_RE.findall(text) if t not in STOPWORDS]


def _idf(docs: list[set[str]]) -> dict[str, float]:
    """Smoothed per-term IDF over the workspace corpus."""
    n = len(docs)
    df: Counter[str] = Counter()
    for tokens in docs:
        df.update(tokens)
    return {term: math.log((n + 1) / (count + 1)) + 1.0 for term, count in df.items()}


def _page_vectors(rows: list[ChunkVector]) -> tuple[list[tuple[int, str, str]], np.ndarray]:
    """One L2-normalized vector per page, the mean of its chunk vectors.

    Returns [(page_id, slug, title), ...] and the matrix aligned by row.
    """
    groups: dict[int, list[np.ndarray]] = {}
    info: dict[int, tuple[str, str]] = {}
    for row in rows:
        groups.setdefault(row.page_id, []).append(np.frombuffer(row.vector, dtype=np.float32))
        info[row.page_id] = (row.slug, row.title)
    ids = sorted(groups)
    if not ids:
        return [], np.zeros((0, embeddings.EMBED_DIM), dtype=np.float32)
    mat = np.stack([np.mean(groups[pid], axis=0) for pid in ids])
    norms = np.clip(np.linalg.norm(mat, axis=1, keepdims=True), 1e-9, None)
    entries = [(pid, info[pid][0], info[pid][1]) for pid in ids]
    return entries, (mat / norms).astype(np.float32)


# ── Wikilinks and duplicates ─────────────────────────────────────────────────


def suggest_links(workspace_id: int, slug: str, *, k: int = 5) -> dict | None:
    """Pages this one should link to and does not yet.

    Cosine similarity between page vectors, or literal title mentions in the body when
    semantic search is off. None if the page does not exist.
    """
    page = db.get_page(slug, workspace_id)
    if page is None:
        return None
    linked = set(db.page_outgoing_links(int(page.id or 0))) | {slug}

    if embeddings.semantic_enabled():
        entries, mat = _page_vectors(
            db.workspace_chunk_vectors(
                workspace_id, embeddings.current_model_name(), meta.CHUNKER_ID
            )
        )
        pos = next((i for i, (pid, _, _) in enumerate(entries) if pid == page.id), None)
        if pos is not None and len(entries) > 1:
            sims = mat @ mat[pos]
            suggestions = []
            for i in np.argsort(-sims):
                pid, other_slug, title = entries[i]
                if i == pos or other_slug in linked or sims[i] < LINK_THRESHOLD:
                    continue
                suggestions.append(
                    {"slug": other_slug, "title": title, "score": round(float(sims[i]), 4)}
                )
                if len(suggestions) >= k:
                    break
            return {"slug": slug, "mode": "semantic", "suggestions": suggestions}

    # Without vectors: other pages' titles mentioned in the body but not linked.
    body = meta.strip_code(meta.parse_frontmatter(page.content)[1]).lower()
    suggestions = []
    for other in db.workspace_pages(workspace_id):
        if other.slug in linked:
            continue
        title = (other.title or "").strip().lower()
        if len(title) >= 4 and title in body:
            suggestions.append({"slug": other.slug, "title": other.title, "score": None})
            if len(suggestions) >= k:
                break
    return {"slug": slug, "mode": "title-match", "suggestions": suggestions}


def find_duplicates(workspace_id: int, *, threshold: float = DUP_THRESHOLD, k: int = 20) -> dict:
    """Near-duplicate page pairs by cosine similarity; needs semantic search."""
    if not embeddings.semantic_enabled():
        return {"mode": "off", "pairs": []}
    entries, mat = _page_vectors(
        db.workspace_chunk_vectors(workspace_id, embeddings.current_model_name(), meta.CHUNKER_ID)
    )
    if len(entries) < 2:
        return {"mode": "semantic", "pairs": []}
    sims = mat @ mat.T
    rows, cols = np.triu_indices(len(entries), k=1)
    pairs: list[dict] = []
    for i, j in zip(rows, cols, strict=True):
        score = float(sims[i, j])
        if score >= threshold:
            pairs.append(
                {
                    "a": {"slug": entries[i][1], "title": entries[i][2]},
                    "b": {"slug": entries[j][1], "title": entries[j][2]},
                    "score": round(score, 4),
                }
            )
    pairs.sort(key=lambda p: p["score"], reverse=True)
    return {"mode": "semantic", "pairs": pairs[:k]}


# ── Tags (TF-IDF) ────────────────────────────────────────────────────────────


def suggest_tags(workspace_id: int, slug: str, *, k: int = 5) -> dict | None:
    """Candidate tags: the page's characteristic TF-IDF terms against the workspace.

    Terms already used as tags elsewhere score higher. Needs no vectors; None if the
    page does not exist.
    """
    pages = db.workspace_pages(workspace_id)
    target_idx = next((i for i, p in enumerate(pages) if p.slug == slug), None)
    if target_idx is None:
        return None
    docs = [tokenize(p.content) for p in pages]
    tokens = docs[target_idx]
    if not tokens:
        return {"slug": slug, "suggestions": []}

    idf = _idf([set(d) for d in docs])
    page_meta = db.get_page_meta(workspace_id, slug)
    existing = {meta.normalize_tag(t) for t in (page_meta.tags if page_meta else [])}
    vocab = set(db.workspace_tags(workspace_id))

    counts = Counter(tokens)
    total = len(tokens)
    scores: dict[str, float] = {}
    for token, count in counts.items():
        tag = meta.normalize_tag(token)
        if not tag or tag in existing:
            continue
        score = (count / total) * idf.get(token, 1.0)
        if tag in vocab:
            score *= TAG_VOCAB_BOOST
        scores[tag] = max(scores.get(tag, 0.0), score)

    top = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:k]
    return {
        "slug": slug,
        "suggestions": [{"tag": tag, "score": round(score, 4)} for tag, score in top],
    }


# ── Extractive summary (TextRank) ────────────────────────────────────────────


def _sentences(body: str) -> list[str]:
    """Prose sentences from the body, dropping code, headings, tables, lists and images."""
    text = meta.strip_code(body)
    kept: list[str] = []
    for para in re.split(r"\n\s*\n", text):
        lines = [ln.strip() for ln in para.splitlines()]
        prose = [ln for ln in lines if ln and not ln.startswith(("#", "|", ">", "-", "*", "!["))]
        if prose:
            kept.append(" ".join(prose))
    sentences = []
    for block in kept:
        for sent in _SENTENCE_RE.split(block):
            sent = sent.strip()
            if len(sent) >= MIN_SENTENCE_CHARS:
                sentences.append(sent)
    return sentences[:MAX_SUMMARY_SENTENCES]


def summarize(content: str, *, k: int = 3) -> dict:
    """TextRank over sentence-embedding similarity: the k most central sentences.

    Returned in their original order. Degrades to the first k sentences (`lead`) with
    semantic search off.
    """
    _, body = meta.parse_frontmatter(content or "")
    sentences = _sentences(body)
    if not sentences:
        return {"mode": "empty", "summary": []}
    if len(sentences) <= k:
        return {"mode": "lead", "summary": sentences}
    if not embeddings.semantic_enabled():
        return {"mode": "lead", "summary": sentences[:k]}

    vectors = embeddings.get_embedder().encode(sentences)
    sim = np.clip(vectors @ vectors.T, 0.0, None).astype(np.float64)
    np.fill_diagonal(sim, 0.0)
    scores = graph.pagerank(sim)
    top = sorted(int(i) for i in np.argsort(-scores)[:k])
    return {"mode": "textrank", "summary": [sentences[i] for i in top]}


# ── Workspace insights ───────────────────────────────────────────────────────


def _topic_clusters(workspace_id: int, *, max_clusters: int = 5) -> dict:
    """Group pages by topic (k-means over vectors), labelled by their top TF-IDF terms."""
    entries, mat = _page_vectors(
        db.workspace_chunk_vectors(workspace_id, embeddings.current_model_name(), meta.CHUNKER_ID)
    )
    if len(entries) < MIN_CLUSTER_PAGES:
        return {"mode": "semantic", "groups": []}
    k = min(max_clusters, max(2, len(entries) // 4))
    labels = graph.kmeans(mat, k)

    pages = {p.id: p for p in db.workspace_pages(workspace_id)}
    docs = {pid: tokenize(pages[pid].content) for pid, _, _ in entries if pid in pages}
    idf = _idf([set(d) for d in docs.values()])

    groups: list[dict] = []
    for cluster in sorted(set(labels.tolist())):
        members = [entries[i] for i in range(len(entries)) if labels[i] == cluster]
        counts: Counter[str] = Counter()
        for pid, _, _ in members:
            counts.update(docs.get(pid, []))
        total = sum(counts.values()) or 1
        ranked = sorted(counts, key=lambda t: (counts[t] / total) * idf.get(t, 1.0), reverse=True)
        groups.append(
            {
                "label": ranked[:3],
                "pages": [{"slug": slug, "title": title} for _, slug, title in members],
            }
        )
    groups.sort(key=lambda g: len(g["pages"]), reverse=True)
    return {"mode": "semantic", "groups": groups}


def workspace_insights(workspace_id: int) -> dict:
    """Workspace health: wikilink graph structure, plus duplicates and topic clusters."""
    insights = graph.link_insights(workspace_id)
    insights["duplicates"] = find_duplicates(workspace_id)
    if embeddings.semantic_enabled():
        insights["clusters"] = _topic_clusters(workspace_id)
    else:
        insights["clusters"] = {"mode": "off", "groups": []}
    return insights
