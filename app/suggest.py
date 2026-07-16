"""Sugerencias locales sin LLM: wikilinks, tags (TF-IDF), duplicados y resumen TextRank.

Todo corre sobre lo que ya existe: los vectores MiniLM de `page_chunks` (cuando
`SEMANTIC_SEARCH=1`) y el propio markdown. Cero dependencias nuevas — numpy ya
está. Cada función degrada con gracia cuando la búsqueda semántica está apagada
(heurística de texto o lista vacía) y lo dice en su campo `mode`, siguiendo el
principio de "explainability over magic" de sgrep.
"""

import logging
import math
import re
from collections import Counter

import numpy as np

from app import db, embeddings, graph, meta
from app.models import ChunkVector

logger = logging.getLogger(__name__)

LINK_THRESHOLD = 0.40  # similitud mínima para sugerir un wikilink (top-5 y con score
# visible, así que mejor pecar de generoso que parecer una función muerta)
DUP_THRESHOLD = 0.90  # similitud mínima para considerar dos páginas casi duplicadas
TAG_VOCAB_BOOST = 1.5  # premia términos que ya son tag en el workspace (vocabulario común)
MAX_SUMMARY_SENTENCES = 120  # tope de frases a embeber por página (coste en el Pi)
MIN_SENTENCE_CHARS = 25
MIN_CLUSTER_PAGES = 6

_WORD_RE = re.compile(r"[a-záéíóúüñ][a-z0-9áéíóúüñ_-]{2,}")
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")

# Stopwords EN+ES mínimas: suficiente para TF-IDF de una wiki técnica, sin
# arrastrar una lista de NLTK como dependencia.
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
    """Tokens en minúsculas del cuerpo: sin frontmatter, sin código, sin stopwords."""
    _, body = meta.parse_frontmatter(content or "")
    text = meta.strip_code(body).lower()
    return [t for t in _WORD_RE.findall(text) if t not in STOPWORDS]


def _idf(docs: list[set[str]]) -> dict[str, float]:
    """IDF suavizado por término sobre el corpus del workspace."""
    n = len(docs)
    df: Counter[str] = Counter()
    for tokens in docs:
        df.update(tokens)
    return {term: math.log((n + 1) / (count + 1)) + 1.0 for term, count in df.items()}


def _page_vectors(rows: list[ChunkVector]) -> tuple[list[tuple[int, str, str]], np.ndarray]:
    """Vector por página = media L2-normalizada de sus vectores de chunk.

    Devuelve [(page_id, slug, title), …] y la matriz alineada por filas.
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


# ── Wikilinks y duplicados ───────────────────────────────────────────────────


def suggest_links(workspace_id: int, slug: str, *, k: int = 5) -> dict | None:
    """Páginas del workspace que esta página debería enlazar y aún no enlaza.

    Con semántica activa: similitud coseno entre vectores de página. Apagada o
    sin vectores todavía: menciones literales de títulos ajenos en el cuerpo.
    None si la página no existe.
    """
    page = db.get_page(slug, workspace_id)
    if page is None:
        return None
    linked = set(db.page_outgoing_links(int(page.id or 0))) | {slug}

    if embeddings.semantic_enabled():
        entries, mat = _page_vectors(db.workspace_chunk_vectors(workspace_id))
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

    # Fallback sin vectores: títulos de otras páginas mencionados y sin enlazar.
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
    """Pares de páginas casi duplicadas por similitud coseno (solo con semántica)."""
    if not embeddings.semantic_enabled():
        return {"mode": "off", "pairs": []}
    entries, mat = _page_vectors(db.workspace_chunk_vectors(workspace_id))
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
    """Tags candidatos para una página: términos TF-IDF característicos frente al
    resto del workspace, con premio a los que ya existen como tag en otras
    páginas. No necesita vectores. None si la página no existe."""
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


# ── Resumen extractivo (TextRank) ────────────────────────────────────────────


def _sentences(body: str) -> list[str]:
    """Frases de prosa del cuerpo: fuera código, encabezados, tablas, listas e imágenes."""
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
    """Resumen extractivo: TextRank sobre similitud de embeddings de frases.

    Sin LLM: elige las k frases más centrales y las devuelve en su orden
    original. Con la semántica apagada degrada a las primeras k frases (`lead`).
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


# ── Insights del workspace ───────────────────────────────────────────────────


def _topic_clusters(workspace_id: int, *, max_clusters: int = 5) -> dict:
    """Agrupa las páginas por tema (k-means sobre vectores) y etiqueta cada grupo
    con sus términos TF-IDF más característicos."""
    entries, mat = _page_vectors(db.workspace_chunk_vectors(workspace_id))
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
    """Panel de salud del workspace: estructura del grafo de wikilinks más las
    señales semánticas (duplicados y clusters de temas) cuando hay vectores."""
    insights = graph.link_insights(workspace_id)
    insights["duplicates"] = find_duplicates(workspace_id)
    if embeddings.semantic_enabled():
        insights["clusters"] = _topic_clusters(workspace_id)
    else:
        insights["clusters"] = {"mode": "off", "groups": []}
    return insights
