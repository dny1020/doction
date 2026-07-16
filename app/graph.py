"""Grafo de wikilinks: PageRank, k-means y análisis estructural en numpy puro.

Sin NetworkX a propósito: los workspaces son de escala wiki (decenas o cientos de
páginas), así que una iteración de potencia y un k-means básico bastan y evitan
una dependencia. Las funciones numéricas son puras; `link_insights` es la única
que consulta la base de datos.
"""

import numpy as np

from app import db


def pagerank(matrix: np.ndarray, *, damping: float = 0.85, iters: int = 50) -> np.ndarray:
    """PageRank por iteración de potencia sobre una matriz de adyacencia n×n.

    `matrix[i, j]` es el peso de la arista i→j (vale cualquier matriz no negativa,
    p. ej. una de similitud para TextRank). Las filas sin salidas (dangling)
    reparten su masa uniformemente. Devuelve un vector de scores que suma 1.
    """
    n = matrix.shape[0]
    if n == 0:
        return np.zeros(0, dtype=np.float64)
    m = matrix.astype(np.float64)
    row_sums = m.sum(axis=1, keepdims=True)
    dangling = row_sums.ravel() == 0.0
    m = np.divide(m, row_sums, out=np.zeros_like(m), where=row_sums > 0)

    rank = np.full(n, 1.0 / n)
    for _ in range(iters):
        rank = (1.0 - damping) / n + damping * (m.T @ rank + rank[dangling].sum() / n)
    return rank


def kmeans(mat: np.ndarray, k: int, *, iters: int = 15) -> np.ndarray:
    """K-means básico: devuelve la etiqueta de cluster de cada fila.

    Determinista: los centros iniciales se eligen por punto-más-lejano (estilo
    k-means++), que evita arrancar con dos centros en el mismo grupo. Suficiente
    para agrupar decenas de páginas; no pretende competir con scikit-learn.
    """
    n = mat.shape[0]
    k = max(1, min(k, n))
    chosen = [0]
    for _ in range(1, k):
        dists = np.min([((mat - mat[c]) ** 2).sum(axis=1) for c in chosen], axis=0)
        chosen.append(int(dists.argmax()))
    centers = mat[chosen].copy()
    labels = np.zeros(n, dtype=np.int64)
    for step in range(iters):
        dists = ((mat[:, None, :] - centers[None, :, :]) ** 2).sum(axis=2)
        new_labels = dists.argmin(axis=1)
        if step > 0 and np.array_equal(new_labels, labels):
            break
        labels = new_labels
        for j in range(k):
            members = mat[labels == j]
            if len(members):
                centers[j] = members.mean(axis=0)
    return labels


def _ref(page) -> dict:
    return {"slug": page.slug, "title": page.title}


def link_insights(user_id: int, workspace_id: int, *, top: int = 10) -> dict:
    """Análisis estructural del grafo de wikilinks de un workspace.

    Devuelve páginas centrales (PageRank), huérfanas (sin enlaces en ningún
    sentido), hubs (más salientes), autoridades (más entrantes) y wikilinks
    rotos (destino inexistente), todo como slugs+títulos listos para JSON.
    """
    pages = db.workspace_pages(workspace_id)
    links = db.workspace_links(workspace_id)
    n = len(pages)
    slug_index = {p.slug: i for i, p in enumerate(pages)}
    id_index = {p.id: i for i, p in enumerate(pages)}

    adj = np.zeros((n, n), dtype=np.float64)
    broken: dict[str, list[str]] = {}
    for edge in links:
        src = id_index.get(edge.src_page_id)
        if src is None:
            continue
        dst = slug_index.get(edge.dst_slug)
        if dst is None:
            broken.setdefault(edge.dst_slug, []).append(pages[src].slug)
        elif src != dst:
            adj[src, dst] = 1.0

    out_deg = adj.sum(axis=1)
    in_deg = adj.sum(axis=0)

    central: list[dict] = []
    if adj.any():
        scores = pagerank(adj)
        for i in np.argsort(-scores)[:top]:
            central.append({**_ref(pages[i]), "score": round(float(scores[i]), 4)})

    def _top_by(degrees: np.ndarray, key: str) -> list[dict]:
        out = []
        for i in np.argsort(-degrees)[:5]:
            if degrees[i] > 0:
                out.append({**_ref(pages[i]), key: int(degrees[i])})
        return out

    orphans = [_ref(pages[i]) for i in range(n) if out_deg[i] == 0 and in_deg[i] == 0]
    broken_links = sorted(
        ({"target": target, "sources": sorted(set(sources))} for target, sources in broken.items()),
        key=lambda b: len(b["sources"]),
        reverse=True,
    )
    return {
        "pages": n,
        "links": int(adj.sum()),
        "central": central,
        "orphans": orphans[:50],
        "hubs": _top_by(out_deg, "outgoing"),
        "authorities": _top_by(in_deg, "incoming"),
        "broken_links": broken_links[:20],
    }
