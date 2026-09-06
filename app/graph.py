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


def link_insights(workspace_id: int, *, top: int = 10) -> dict:
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


# Por encima de esto el navegador deja de poder con la simulación y el dibujo deja
# de decir nada: mil nodos son una mancha. Se recorta por PageRank, que es la
# medida de "importa en este grafo" que ya se calcula aquí.
GRAPH_NODE_LIMIT = 300


def workspace_graph(workspace_id: int, *, limit: int = GRAPH_NODE_LIMIT) -> dict:
    """Nodos y aristas del grafo de wikilinks, listos para dibujar.

    Es la misma materia prima que `link_insights` mira en agregado; aquí sale
    entera porque la vista dibuja el grafo, no su resumen. Un destino que no
    existe se devuelve como arista rota con su slug, no se descarta: es la única
    señal de que alguien contaba con esa página.
    """
    pages = db.workspace_pages(workspace_id)
    links = db.workspace_links(workspace_id)
    slug_index = {p.slug: i for i, p in enumerate(pages)}
    id_index = {p.id: i for i, p in enumerate(pages)}
    n = len(pages)

    adj = np.zeros((n, n), dtype=np.float64)
    broken: list[tuple[int, str]] = []
    for edge in links:
        src = id_index.get(edge.src_page_id)
        if src is None:
            continue
        dst = slug_index.get(edge.dst_slug)
        if dst is None:
            broken.append((src, edge.dst_slug))
        elif src != dst:
            adj[src, dst] = 1.0

    keep = range(n)
    truncated = False
    if n > limit:
        scores = pagerank(adj) if adj.any() else np.zeros(n)
        keep = sorted(np.argsort(-scores)[:limit])
        truncated = True
    kept = {int(i) for i in keep}

    in_deg = adj.sum(axis=0)
    out_deg = adj.sum(axis=1)
    nodes = [
        {
            "slug": pages[i].slug,
            "title": pages[i].title,
            "incoming": int(in_deg[i]),
            "outgoing": int(out_deg[i]),
            # Huérfana: sin enlace en ningún sentido. Un enlace a sí misma no
            # cuenta, porque no la conecta con nada.
            # bool() explícito: numpy devuelve np.bool_ y FastAPI no lo serializa.
            "orphan": bool(in_deg[i] == 0 and out_deg[i] == 0),
        }
        for i in sorted(kept)
    ]

    edges = [
        {"source": pages[src].slug, "target": pages[dst].slug, "broken": False}
        for src in sorted(kept)
        for dst in np.nonzero(adj[src])[0]
        if int(dst) in kept
    ]
    edges += [
        {"source": pages[src].slug, "target": target, "broken": True}
        for src, target in broken
        if src in kept
    ]

    return {
        "nodes": nodes,
        "edges": edges,
        "pages": n,
        "truncated": truncated,
    }


# Topes del recorrido. La profundidad se corta pronto porque a partir del tercer
# salto un wiki bien enlazado devuelve medio workspace, y eso no es contexto: es
# el corpus otra vez. El tope de nodos protege al agente de una respuesta que no
# le cabe en la ventana.
MAX_LINK_DEPTH = 3
LINKED_NODE_LIMIT = 100


def linked_knowledge(
    workspace_id: int,
    slug: str,
    *,
    depth: int = 1,
    limit: int = LINKED_NODE_LIMIT,
) -> dict | None:
    """El vecindario de `slug` en el grafo de wikilinks, hasta `depth` saltos.

    Recorre en los dos sentidos: a quién enlaza esta página y quién la enlaza a
    ella. Un agente que explora quiere las dos respuestas, y pedirlas por separado
    cuesta una ida y vuelta por arista sin llegar a saber dónde acaba el vecindario.

    Cada vecino trae la distancia, el sentido del salto que lo alcanzó y el camino
    completo, para que el agente pueda justificar por qué está mirando algo.
    Devuelve None si la página no existe.
    """
    pages = {p.slug: p for p in db.workspace_pages(workspace_id)}
    if slug not in pages:
        return None

    depth = max(1, min(int(depth), MAX_LINK_DEPTH))
    by_id = {p.id: p.slug for p in pages.values()}

    outgoing: dict[str, set[str]] = {}
    incoming: dict[str, set[str]] = {}
    for edge in db.workspace_links(workspace_id):
        src = by_id.get(edge.src_page_id)
        if src is None or edge.dst_slug == src:
            continue  # un enlace a sí misma no la conecta con nadie
        outgoing.setdefault(src, set()).add(edge.dst_slug)
        # Un destino inexistente no tiene salientes, pero sí es alcanzable.
        incoming.setdefault(edge.dst_slug, set()).add(src)

    seen = {slug}
    neighbors: list[dict] = []
    frontier = [(slug, [slug])]
    truncated = False

    for distance in range(1, depth + 1):
        nxt: list[tuple[str, list[str]]] = []
        for current, path in frontier:
            out_set = outgoing.get(current, set())
            in_set = incoming.get(current, set())
            for other in sorted(out_set | in_set):
                if other in seen:
                    continue  # ya visto: así terminan los ciclos
                seen.add(other)
                if len(neighbors) >= limit:
                    truncated = True
                    continue
                # Dos páginas que se citan la una a la otra son un caso corriente y
                # distinto: contarlo solo como saliente lo borraba de los entrantes,
                # que es justo lo que pregunta quien busca qué depende de esto.
                if other in out_set and other in in_set:
                    via = "both"
                else:
                    via = "outgoing" if other in out_set else "incoming"
                page = pages.get(other)
                neighbors.append(
                    {
                        "slug": other,
                        "title": page.title if page else other,
                        "distance": distance,
                        "via": via,
                        "path": path + [other],
                        "exists": page is not None,
                    }
                )
                # Un destino roto es una hoja: no hay página desde la que seguir.
                if page is not None:
                    nxt.append((other, path + [other]))
        frontier = nxt
        if not frontier:
            break

    return {
        "slug": slug,
        "title": pages[slug].title,
        "depth": depth,
        "neighbors": neighbors,
        "truncated": truncated,
    }
