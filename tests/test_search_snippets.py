"""Search snippets carry no markup in any mode; highlighting travels as spans.

Guards the stored XSS where <mark> from ts_headline was painted as HTML.
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
    """Sentinels are stripped from the text before highlighting."""
    token = _token(client)
    _page(client, token, "Kamailio dispatcher", "\x01todo marcado\x02 dispatcher")

    parts = _search(client, token, "dispatcher", "keyword")[0]["parts"]
    marked = [part["text"].lower() for part in parts if part["match"]]
    assert all("todo marcado" not in text for text in marked)
    assert all("\x01" not in part["text"] and "\x02" not in part["text"] for part in parts)


def test_semantic_and_hybrid_snippets_carry_no_markup(semantic_client):
    """All three modes share a shape: none is safe unless all are."""
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


# ── Markdown syntax does not reach the snippet ───────────────────────────────

MARKDOWN_PAGE = """---
type: runbook
tags: [tls]
---

# Renovación TLS

See the [[deploy-runbook|deploy runbook]] and the [guide](https://example.com/very/long/url).

## Steps

| Step | Command |
| --- | ------: |
| 1 | `certbot renew` |
| 2 | **restart** nginx |

> Careful: the *dry-run* renews nothing.

- first bullet
- second bullet

```mermaid
graph TD;
  A[Certbot]-->B[nginx];
```

Closing prose after the diagram.
"""

SYNTAX = ["##", "|", "[[", "]]", "```", "**", "`", "> ", "~~~"]


def _hit(client, token, query, slug):
    """The hit for `slug`: registration seeds pages that match some of these queries too."""
    r = client.get("/api/search", params={"q": query}, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    hits = [hit for hit in r.json() if hit["slug"] == slug]
    assert hits, f"no hit for {query!r} on {slug!r}"
    return hits[0]


def _runbook(client):
    token = _token(client)
    return token, _page(client, token, "TLS runbook", MARKDOWN_PAGE)


def test_snippet_carries_no_markdown_syntax(client):
    token, slug = _runbook(client)
    for query in ("certbot", "nginx", "prose", "renovacion"):
        snippet = _hit(client, token, query, slug)["snippet"]
        for mark in SYNTAX:
            assert mark not in snippet, f"{query!r} -> {snippet!r} still carries {mark!r}"


def test_mermaid_source_never_becomes_a_snippet(client):
    """A fenced block goes before the twelve words are chosen, not cleaned up after."""
    token, slug = _runbook(client)
    snippet = _hit(client, token, "graph", slug)["snippet"]
    assert "graph TD" not in snippet
    assert "-->" not in snippet


def test_a_wikilink_shows_its_label(client):
    """The reader sees what the writer wrote, not the slug behind it."""
    token, slug = _runbook(client)
    assert "deploy runbook" in _hit(client, token, "deploy", slug)["snippet"]


def test_a_link_url_does_not_eat_the_window(client):
    """Twelve words of URL are twelve words the reader cannot use."""
    token, slug = _runbook(client)
    snippet = _hit(client, token, "guide", slug)["snippet"]
    assert "guide" in snippet
    assert "example.com" not in snippet


def test_stripping_did_not_cost_the_highlighting(client):
    """The spans still come back, and still add up to the snippet."""
    token, slug = _runbook(client)
    hit = _hit(client, token, "certbot", slug)
    matched = [part["text"] for part in hit["parts"] if part["match"]]
    assert matched, hit["parts"]
    assert any("certbot" in text.lower() for text in matched)
    assert "".join(part["text"] for part in hit["parts"]) == hit["snippet"]


def test_a_page_cannot_forge_a_highlight_through_the_stripping(client):
    """The control characters are removed from what the stripping produced, not before it."""
    token = _token(client)
    slug = _page(client, token, "Forged", "\x01certbot\x02 renew and **\x01nginx\x02** restart")
    hit = _hit(client, token, "renew", slug)
    assert "\x01" not in hit["snippet"] and "\x02" not in hit["snippet"]
    matched = [part["text"] for part in hit["parts"] if part["match"]]
    assert all("certbot" not in text.lower() for text in matched), matched


def test_ranking_is_unaffected_by_the_stripping(client):
    """Syntax comes off the snippet, not off search_vector: a heading is still findable."""
    token = _token(client)
    slug = _page(client, token, "Headed", "## Kamailio dispatcher\n\nbody text")
    r = client.get(
        "/api/search", params={"q": "kamailio"}, headers={"Authorization": f"Bearer {token}"}
    )
    assert slug in [hit["slug"] for hit in r.json()]
