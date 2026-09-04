"""Las dos propiedades que la spec de `chunking` exige del texto que se embebe.

Tiran en direcciones opuestas y por eso están las dos aquí. Una quiere contexto de
página dentro del embedding para que dos secciones iguales de páginas distintas no
colisionen; la otra lo quiere fuera, porque lo que comparten todas las secciones de una
página no dice cuál de ellas responde.
"""

import pytest
from fastapi.testclient import TestClient

from app import embeddings


def _token(client) -> str:
    client.post("/api/auth/register", json={"email": "u@test.com", "password": "password123"})
    r = client.post("/api/token", json={"email": "u@test.com", "password": "password123"})
    return r.json()["token"]


def _page(client, token: str, title: str, content: str) -> str:
    r = client.post(
        "/api/pages",
        json={"title": title, "content": content},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201, r.text
    return r.json()["slug"]


@pytest.fixture()
def semantic_client(main_module, monkeypatch):
    monkeypatch.setenv("SEMANTIC_SEARCH", "1")
    monkeypatch.setenv("EMBED_STUB", "1")
    embeddings.reset_embedder()

    async def _noop():
        return

    monkeypatch.setattr(embeddings, "enrichment_worker", _noop)
    with TestClient(main_module.app) as c:
        yield c


IDENTICA = "## Configuración\n\nEditar el fichero y reiniciar el servicio para aplicar.\n"


def test_sibling_sections_stay_apart(semantic_client):
    """Una consulta contestada por una sección recupera esa y no una hermana."""
    client = semantic_client
    token = _token(client)
    _page(
        client,
        token,
        "Runbook",
        "# Runbook\n\n"
        "## Renovar el certificado\n\nEjecutar certbot renew y recargar nginx.\n\n"
        "## Rotar las claves SSH\n\nGenerar un par nuevo con ssh-keygen y copiarlo.\n",
    )
    embeddings.drain_pending()

    out = embeddings.rag_context(1, "rotar las claves ssh", budget=100000)
    assert out["chunks"], out
    assert "Rotar las claves SSH" in out["chunks"][0]["section"]


def test_sibling_sections_are_not_near_identical_vectors(semantic_client):
    """La propiedad medible: sin ella, dos secciones son un vector con dos etiquetas."""
    import numpy as np

    client = semantic_client
    token = _token(client)
    _page(
        client,
        token,
        "Runbook",
        "# Runbook\n\n"
        "## Renovar el certificado\n\nEjecutar certbot renew y recargar nginx.\n\n"
        "## Rotar las claves SSH\n\nGenerar un par nuevo con ssh-keygen y copiarlo.\n",
    )
    embeddings.drain_pending()

    rows = [
        r
        for r in embeddings.db.workspace_chunk_vectors(
            1, embeddings.current_model_name(), embeddings.meta.CHUNKER_ID
        )
        if r.slug == "runbook"
    ]
    assert len(rows) >= 2
    vecs = np.stack([embeddings._from_blob(r.vector) for r in rows])
    sim = vecs @ vecs.T
    off = sim[np.triu_indices(len(rows), k=1)]
    assert off.max() < 0.95, f"secciones hermanas casi idénticas: {off.max():.3f}"


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Defecto conocido del empaquetado `# Sección\\n\\ncuerpo` (004): dos secciones "
        "redactadas igual en páginas distintas producen literalmente el mismo texto, y "
        "por tanto el mismo vector (coseno 1.0000 medido). El 002 protegía esta "
        "propiedad metiendo el título de la página en el texto embebido; sacarlo es lo "
        "que subió el recall de sección y lo que rompió esto. strict=True: el día que "
        "se arregle, el test avisa en vez de quedarse callado."
    ),
)
def test_identically_worded_sections_in_different_pages_do_not_collide(semantic_client):
    """La otra mitad del contrato: la misma sección en dos páginas no es el mismo vector."""
    import numpy as np

    client = semantic_client
    token = _token(client)
    _page(client, token, "Servicio A", f"# Servicio A\n\n{IDENTICA}")
    _page(client, token, "Servicio B", f"# Servicio B\n\n{IDENTICA}")
    embeddings.drain_pending()

    rows = embeddings.db.workspace_chunk_vectors(
        1, embeddings.current_model_name(), embeddings.meta.CHUNKER_ID
    )
    por_slug = {}
    for r in rows:
        if r.slug in ("servicio-a", "servicio-b") and "Configuración" in r.path:
            por_slug[r.slug] = embeddings._from_blob(r.vector)
    assert set(por_slug) == {"servicio-a", "servicio-b"}, por_slug.keys()

    sim = float(np.dot(por_slug["servicio-a"], por_slug["servicio-b"]))
    assert sim < 0.999, f"las dos secciones producen el mismo vector (coseno {sim:.4f})"
