"""The two properties the `chunking` spec demands of the embedded text.

They pull in opposite directions, which is why both live here: one wants page context
inside the embedding so identical sections of different pages do not collide, the other
wants it out, because what every section of a page shares cannot say which one answers.
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
    """A query answered by one section retrieves that section, not a sibling."""
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
    """The measurable property: without it, two sections are one vector with two labels."""
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


def test_identically_worded_sections_in_different_pages_do_not_collide(semantic_client):
    """Identical sections embed identically; the page ranking, which sees the title,
    must still keep them from scoring equally.
    """
    client = semantic_client
    token = _token(client)
    _page(client, token, "Kamailio", f"# Kamailio\n\n{IDENTICA}")
    _page(client, token, "Asterisk", f"# Asterisk\n\n{IDENTICA}")
    embeddings.drain_pending()

    hits = embeddings.search(1, "kamailio", mode="hybrid")
    orden = [h["slug"] for h in hits if h["slug"] in ("kamailio", "asterisk")]
    assert orden[:1] == ["kamailio"], orden

    hits = embeddings.search(1, "asterisk", mode="hybrid")
    orden = [h["slug"] for h in hits if h["slug"] in ("kamailio", "asterisk")]
    assert orden[:1] == ["asterisk"], orden
