"""Search snippets: the server returns no markup, in any mode.

Covers the defect behind it: `ts_headline` wrapped the match in <mark> and left the rest of
the page text alone, and the sidebar painted it with dangerouslySetInnerHTML — stored XSS
with the markdown renderer entirely intact.

Checked here: the server adds no markup of its own and highlighting travels as spans. That
the client paints those spans as text is checked by reading the client.
"""

import pytest
from fastapi.testclient import TestClient

PAYLOAD = "<img src=x onerror=alert(1)> dispatcher failover"


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


def _search(client, token: str, query: str, mode: str) -> list[dict]:
    r = client.get(
        f"/api/search?q={query}&mode={mode}", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture()
def semantic_client(main_module, monkeypatch):
    """A client with semantic search on and the deterministic embedder."""
    monkeypatch.setenv("SEMANTIC_SEARCH", "1")
    monkeypatch.setenv("EMBED_STUB", "1")

    import app.embeddings as emb_module

    emb_module.reset_embedder()

    async def _noop():
        return

    monkeypatch.setattr(emb_module, "enrichment_worker", _noop)
    with TestClient(main_module.app) as c:
        yield c


def test_keyword_snippet_adds_no_markup(client):
    token = _token(client)
    _page(client, token, "Kamailio dispatcher", PAYLOAD)

    hits = _search(client, token, "dispatcher", "keyword")
    assert hits, "la página debería salir en los resultados"
    snippet = hits[0]["snippet"]
    assert "<mark>" not in snippet and "</mark>" not in snippet
    assert PAYLOAD.split()[0] in snippet, "el texto de la página se conserva: es texto"


def test_keyword_snippet_marks_only_the_match(client):
    token = _token(client)
    _page(client, token, "Kamailio dispatcher", PAYLOAD)

    parts = _search(client, token, "dispatcher", "keyword")[0]["parts"]
    assert (
        "".join(part["text"] for part in parts)
        == _search(client, token, "dispatcher", "keyword")[0]["snippet"]
    )
    marked = [part["text"].lower() for part in parts if part["match"]]
    assert marked, "el término buscado debería quedar marcado"
    assert all("dispatcher" in text for text in marked)
    assert not any("img" in text or "onerror" in text for text in marked)


def test_control_characters_in_content_cannot_forge_a_match(client):
    """Los centinelas se borran del texto antes de resaltar."""
    token = _token(client)
    _page(client, token, "Kamailio dispatcher", "\x01todo marcado\x02 dispatcher")

    parts = _search(client, token, "dispatcher", "keyword")[0]["parts"]
    marked = [part["text"].lower() for part in parts if part["match"]]
    assert all("todo marcado" not in text for text in marked)
    assert all("\x01" not in part["text"] and "\x02" not in part["text"] for part in parts)


def test_semantic_and_hybrid_snippets_carry_no_markup(semantic_client):
    """Los tres modos comparten forma: ninguno es seguro mientras otro no lo sea."""
    from app import embeddings

    client = semantic_client
    token = _token(client)
    _page(client, token, "Kamailio dispatcher", PAYLOAD)
    embeddings.drain_pending()

    for mode in ("keyword", "semantic", "hybrid"):
        hits = _search(client, token, "dispatcher", mode)
        assert hits, mode
        for hit in hits:
            assert "<mark>" not in hit["snippet"], mode
            assert isinstance(hit["parts"], list) and hit["parts"], mode
            assert "".join(part["text"] for part in hit["parts"]) == hit["snippet"], mode


def test_snippet_does_not_lead_with_frontmatter(client):
    """A quick capture opens with `--- type: memo ---`; showing that as the page text
    turns the metadata into the result."""
    token = _token(client)
    _page(client, token, "Captura", "---\ntype: memo\n---\n\nrevisar el dispatcher del SBC")

    hits = _search(client, token, "dispatcher", "keyword")
    hit = next(h for h in hits if "dispatcher" in h["snippet"])
    assert "type: memo" not in hit["snippet"]
    assert "---" not in hit["snippet"]
