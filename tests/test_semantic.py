"""Tests for Phase B semantic search (sgrep / rag).

Uses a deterministic stub embedder (EMBED_STUB=1) and a no-op enrichment worker;
embedding is driven explicitly via embeddings.drain_pending() for determinism.
"""

from __future__ import annotations

import importlib
import json
import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-test-secret-key-32")
    monkeypatch.setenv("SEMANTIC_SEARCH", "1")
    monkeypatch.setenv("EMBED_STUB", "1")

    import app.db as db_module
    import app.embeddings as emb_module
    import app.git_repo as git_module
    import app.main as main_module

    importlib.reload(db_module)
    importlib.reload(git_module)
    importlib.reload(emb_module)
    importlib.reload(main_module)
    emb_module.reset_embedder()

    async def _noop():  # keep embedding deterministic via drain_pending()
        return

    monkeypatch.setattr(emb_module, "enrichment_worker", _noop)

    with TestClient(main_module.app) as c:
        yield c


def _token(client) -> str:
    client.post("/register", data={"email": "u@test.com", "password": "password123"})
    r = client.post("/api/token", json={"email": "u@test.com", "password": "password123"})
    return r.json()["token"]


def _call(client, token: str, tool: str, arguments: dict | None = None) -> dict:
    msg = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
           "params": {"name": tool, "arguments": arguments or {}}}
    r = client.post("/api/mcp", json=msg, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    return r.json()["result"]


def _data(result: dict):
    assert not result.get("isError"), result
    return json.loads(result["content"][0]["text"])


def _drain():
    import app.embeddings as emb
    return emb.drain_pending()


def _seed_pages(client, token):
    _call(client, token, "create_page", {
        "title": "Kamailio dispatcher",
        "content": "kamailio dispatcher load balancing sip routing failover",
    })
    _call(client, token, "create_page", {
        "title": "Coffee recipes",
        "content": "espresso milk foam barista grinder beans",
    })
    _drain()


def test_chunks_created_and_dirty_cleared(client):
    import app.db as db
    token = _token(client)
    _call(client, token, "create_page", {"title": "Note", "content": "alpha beta gamma"})
    assert db.pages_to_embed()  # dirty before drain
    _drain()
    assert db.pages_to_embed() == []  # nothing dirty after drain
    # chunks exist for the workspace
    with db.connect() as conn:
        n = conn.execute("SELECT COUNT(*) AS n FROM page_chunks").fetchone()["n"]
    assert n >= 1


def test_update_marks_dirty_again(client):
    import app.db as db
    token = _token(client)
    created = _data(_call(client, token, "create_page", {"title": "Doc", "content": "first"}))
    _drain()
    assert db.pages_to_embed() == []
    _call(client, token, "update_page", {"slug": created["slug"], "content": "second version"})
    assert any(r.id for r in db.pages_to_embed())


def test_sgrep_ranks_by_meaning(client):
    token = _token(client)
    _seed_pages(client, token)
    results = _data(_call(client, token, "sgrep", {"query": "sip routing"}))
    assert results, results
    assert results[0]["slug"] == "kamailio-dispatcher"
    assert results[0]["via"] == "semantic"
    assert results[0]["score"] is not None
    # the coffee page should not be the top hit
    assert all(r["slug"] != "coffee-recipes" for r in results[:1])


def test_sgrep_keyword_boost_flag(client):
    token = _token(client)
    _seed_pages(client, token)
    results = _data(_call(client, token, "sgrep", {"query": "dispatcher"}))
    top = next(r for r in results if r["slug"] == "kamailio-dispatcher")
    assert top["keyword_match"] is True


def test_rag_returns_chunks_with_provenance(client):
    token = _token(client)
    _seed_pages(client, token)
    out = _data(_call(client, token, "rag", {"query": "load balancing sip"}))
    assert out["mode"] == "semantic"
    assert out["chunks"], out
    chunk = out["chunks"][0]
    assert {"slug", "title", "ord", "score", "text"} <= set(chunk)
    assert chunk["slug"] == "kamailio-dispatcher"


def test_semantic_falls_back_to_fts_when_disabled(client, monkeypatch):
    token = _token(client)
    _seed_pages(client, token)
    monkeypatch.setenv("SEMANTIC_SEARCH", "0")
    results = _data(_call(client, token, "sgrep", {"query": "dispatcher"}))
    assert results
    assert all(r["via"] == "fts" for r in results)
    assert all(r["score"] is None for r in results)


def test_search_endpoint_semantic_mode(client):
    token = _token(client)
    _seed_pages(client, token)
    r = client.get("/api/search", params={"q": "sip routing", "mode": "semantic"},
                   headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    body = r.json()
    assert body and body[0]["slug"] == "kamailio-dispatcher"


@pytest.mark.skipif(
    not os.path.exists(os.environ.get("REAL_MODEL_PATH", "/nonexistent")),
    reason="real ONNX model not present (set REAL_MODEL_PATH to run)",
)
def test_real_onnx_embedder_similarity():
    """Integración opt-in: valida el encoder ONNX real (mean-pooling, normalización)."""
    import app.embeddings as emb
    emb.reset_embedder()
    os.environ.pop("EMBED_STUB", None)
    os.environ["MODEL_DIR"] = os.path.dirname(os.environ["REAL_MODEL_PATH"])
    importlib.reload(emb)
    vecs = emb.get_embedder().encode([
        "kamailio sip routing failover",
        "espresso coffee barista",
        "sip proxy routing setup",
    ])
    sims = vecs @ vecs[0]
    assert sims[2] > sims[1]  # sip-related closer than coffee
