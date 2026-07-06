"""Tests for the local ML round (v0.16): suggest links/tags, summaries, insights.

Same approach as test_semantic.py: deterministic stub embedder (EMBED_STUB=1),
no background worker, embedding driven explicitly via drain_pending().
"""

from __future__ import annotations

import json

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app import graph, suggest

# ── Pure functions (no app, no db) ───────────────────────────────────────────


def test_pagerank_prefers_most_linked_node():
    adj = np.zeros((3, 3))
    adj[0, 2] = 1.0
    adj[1, 2] = 1.0
    scores = graph.pagerank(adj)
    assert scores.argmax() == 2
    assert scores.sum() == pytest.approx(1.0)


def test_pagerank_empty_graph():
    assert graph.pagerank(np.zeros((0, 0))).shape == (0,)


def test_kmeans_separates_two_obvious_groups():
    mat = np.array([[0.0, 0.1], [0.1, 0.0], [10.0, 10.1], [10.1, 10.0]])
    labels = graph.kmeans(mat, 2)
    assert labels[0] == labels[1]
    assert labels[2] == labels[3]
    assert labels[0] != labels[2]


def test_tokenize_strips_code_stopwords_and_frontmatter():
    content = "---\ntags: [x]\n---\nThe kamailio dispatcher routes SIP.\n```\nsecret_token\n```"
    tokens = suggest.tokenize(content)
    assert "kamailio" in tokens and "dispatcher" in tokens
    assert "the" not in tokens  # stopword
    assert "secret_token" not in tokens  # inside code fence
    assert "tags" not in tokens  # frontmatter dropped


def test_summarize_empty_and_lead_fallback(monkeypatch):
    monkeypatch.delenv("SEMANTIC_SEARCH", raising=False)
    assert suggest.summarize("")["mode"] == "empty"
    prose = (
        "First sentence with enough characters here. "
        "Second sentence also has enough characters. "
        "Third sentence keeps on going with more words. "
        "Fourth sentence closes the little paragraph."
    )
    out = suggest.summarize(prose, k=2)
    assert out["mode"] == "lead"
    assert len(out["summary"]) == 2
    assert out["summary"][0].startswith("First")


# ── App-level (Postgres + stub embedder) ─────────────────────────────────────


@pytest.fixture()
def client(main_module, monkeypatch):
    monkeypatch.setenv("SEMANTIC_SEARCH", "1")
    monkeypatch.setenv("EMBED_STUB", "1")

    import app.embeddings as emb_module

    emb_module.reset_embedder()

    async def _noop():  # embedding is driven explicitly via _drain()
        return

    monkeypatch.setattr(emb_module, "enrichment_worker", _noop)

    with TestClient(main_module.app) as c:
        yield c


@pytest.fixture()
def client_fts(main_module, monkeypatch):
    """Client with semantic search OFF: exercises the degraded modes."""
    monkeypatch.delenv("SEMANTIC_SEARCH", raising=False)
    with TestClient(main_module.app) as c:
        yield c


def _register(client):
    r = client.post("/api/auth/register", json={"email": "u@test.com", "password": "password123"})
    assert r.status_code == 201


def _create(client, title: str, content: str) -> str:
    r = client.post("/api/pages", json={"title": title, "content": content})
    assert r.status_code == 201, r.text
    return r.json()["slug"]


def _drain():
    import app.embeddings as emb

    return emb.drain_pending()


def _token(client) -> str:
    r = client.post("/api/token", json={"email": "u@test.com", "password": "password123"})
    return r.json()["token"]


def _call(client, token: str, tool: str, arguments: dict | None = None) -> dict:
    msg = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": tool, "arguments": arguments or {}},
    }
    r = client.post("/api/mcp", json=msg, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    return r.json()["result"]


def _data(result: dict):
    assert not result.get("isError"), result
    return json.loads(result["content"][0]["text"])


def test_suggest_links_semantic_and_excludes_linked(client):
    _register(client)
    a = _create(client, "Kamailio dispatcher", "kamailio dispatcher sip routing failover setup")
    b = _create(client, "SIP failover notes", "kamailio dispatcher sip routing failover extras")
    _create(client, "Coffee recipes", "espresso milk foam barista grinder beans")
    _drain()

    r = client.get(f"/api/pages/{a}/suggest-links")
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "semantic"
    slugs = [s["slug"] for s in body["suggestions"]]
    assert b in slugs
    assert "coffee-recipes" not in slugs

    # Once the page actually links to b, it must disappear from the suggestions.
    r = client.put(
        f"/api/pages/{a}",
        json={"content": f"kamailio dispatcher sip routing failover setup [[{b}]]"},
    )
    assert r.status_code == 200
    _drain()
    slugs = [s["slug"] for s in client.get(f"/api/pages/{a}/suggest-links").json()["suggestions"]]
    assert b not in slugs


def test_suggest_links_title_match_fallback(client_fts):
    _register(client_fts)
    _create(client_fts, "Kamailio Primer", "how to configure the proxy")
    x = _create(client_fts, "Routing overview", "this mentions kamailio primer but has no link")

    body = client_fts.get(f"/api/pages/{x}/suggest-links").json()
    assert body["mode"] == "title-match"
    assert "kamailio-primer" in [s["slug"] for s in body["suggestions"]]

    assert client_fts.get("/api/pages/nope/suggest-links").status_code == 404


def test_suggest_tags_tfidf(client_fts):
    _register(client_fts)
    _create(client_fts, "Other", "generic words that appear here")
    slug = _create(
        client_fts,
        "Kamailio tuning",
        "#voip\nkamailio kamailio kamailio dispatcher tuning tuning parameters",
    )

    body = client_fts.get(f"/api/pages/{slug}/suggest-tags").json()
    tags = [s["tag"] for s in body["suggestions"]]
    assert "kamailio" in tags
    assert "voip" not in tags  # already tagged on the page

    assert client_fts.get("/api/pages/nope/suggest-tags").status_code == 404


def test_summary_textrank(client):
    _register(client)
    slug = _create(
        client,
        "Long note",
        "Kamailio handles the SIP routing for every call. "
        "The dispatcher module balances traffic across nodes. "
        "Failover happens automatically when a node stops replying. "
        "Coffee is a completely unrelated topic in this note. "
        "Monitoring lives in a separate grafana dashboard entirely.",
    )
    r = client.get(f"/api/pages/{slug}/summary?k=2")
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "textrank"
    assert len(body["summary"]) == 2

    assert client.get("/api/pages/nope/summary").status_code == 404


def test_insights_graph_sections(client):
    _register(client)
    a = _create(client, "Hub page", "links out to stuff [[target-page]] [[missing-forever]]")
    t = _create(client, "Target page", "gets linked a lot")
    _create(client, "Lonely page", "no links in or out of this one")
    _drain()

    body = client.get("/api/insights").json()
    assert body["pages"] >= 3
    assert body["links"] >= 1
    assert t in [p["slug"] for p in body["central"]]
    assert a in [p["slug"] for p in body["hubs"]]
    assert t in [p["slug"] for p in body["authorities"]]
    assert "lonely-page" in [p["slug"] for p in body["orphans"]]
    assert "missing-forever" in [b["target"] for b in body["broken_links"]]
    assert body["duplicates"]["mode"] == "semantic"
    assert body["clusters"]["mode"] == "semantic"


def test_insights_detects_duplicates(client):
    _register(client)
    same = "identical content about kamailio dispatcher failover and sip routing here"
    a = _create(client, "Copy one", same)
    b = _create(client, "Copy two", same)
    _drain()

    pairs = client.get("/api/insights").json()["duplicates"]["pairs"]
    assert any({p["a"]["slug"], p["b"]["slug"]} == {a, b} for p in pairs)
    assert all(p["score"] >= suggest.DUP_THRESHOLD for p in pairs)


def test_insights_off_modes_without_semantic(client_fts):
    _register(client_fts)
    _create(client_fts, "Solo", "just one page")
    body = client_fts.get("/api/insights").json()
    assert body["duplicates"]["mode"] == "off"
    assert body["clusters"]["mode"] == "off"


def test_mcp_tools_and_calls(client):
    _register(client)
    token = _token(client)

    r = client.post("/api/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    names = [t["name"] for t in r.json()["result"]["tools"]]
    for tool in ("suggest_links", "suggest_tags", "summarize_page", "workspace_insights"):
        assert tool in names

    slug = _create(client, "MCP note", "kamailio kamailio dispatcher routing for agents")
    _drain()

    tags = _data(_call(client, token, "suggest_tags", {"slug": slug}))
    assert "kamailio" in [s["tag"] for s in tags["suggestions"]]

    insights = _data(_call(client, token, "workspace_insights"))
    assert insights["pages"] >= 1

    summary = _data(_call(client, token, "summarize_page", {"slug": slug, "sentences": 1}))
    assert summary["slug"] == slug

    missing = _call(client, token, "suggest_links", {"slug": "nope"})
    assert missing.get("isError")
