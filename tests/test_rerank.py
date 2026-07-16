"""Tests for the opt-in cross-encoder reranker (RERANK=1 on top of sgrep).

Uses the deterministic stub reranker (EMBED_STUB=1): score = query-token overlap.
"""

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app import embeddings


def test_stub_reranker_orders_by_overlap():
    scores = embeddings._StubReranker().score(
        "sip routing", ["sip routing failover sip", "espresso milk foam"]
    )
    assert scores[0] > scores[1]
    assert embeddings._StubReranker().score("q", []).shape == (0,)


def test_rerank_enabled_requires_semantic(monkeypatch):
    monkeypatch.setenv("RERANK", "1")
    monkeypatch.delenv("SEMANTIC_SEARCH", raising=False)
    assert not embeddings.rerank_enabled()
    monkeypatch.setenv("SEMANTIC_SEARCH", "1")
    assert embeddings.rerank_enabled()


@pytest.fixture()
def client(main_module, monkeypatch):
    monkeypatch.setenv("SEMANTIC_SEARCH", "1")
    monkeypatch.setenv("EMBED_STUB", "1")
    monkeypatch.setenv("RERANK", "1")

    embeddings.reset_embedder()

    async def _noop():
        return

    monkeypatch.setattr(embeddings, "enrichment_worker", _noop)

    with TestClient(main_module.app) as c:
        yield c


def _seed(client):
    r = client.post("/api/auth/register", json={"email": "u@test.com", "password": "password123"})
    assert r.status_code == 201
    for title, content in [
        ("Routing deep dive", "sip routing sip routing sip routing failover details"),
        ("Routing mention", "one line that says sip routing among other unrelated words"),
    ]:
        r = client.post("/api/pages", json={"title": title, "content": content})
        assert r.status_code == 201
    embeddings.drain_pending()


def test_search_results_are_reranked(client):
    _seed(client)
    results = client.get("/api/search?q=sip+routing&mode=semantic").json()
    ours = [r for r in results if r["slug"].startswith("routing-")]
    assert ours, results
    for r in ours:
        assert r["via"] == "semantic+rerank"
        assert "rerank_score" in r and "score" in r
    rerank_scores = [r["rerank_score"] for r in results if "rerank_score" in r]
    assert rerank_scores == sorted(rerank_scores, reverse=True)
    # El cross-encoder (stub: solape de tokens) pone el texto denso en sip/routing primero.
    assert ours[0]["slug"] == "routing-deep-dive"


def test_without_rerank_flag_via_stays_semantic(client, monkeypatch):
    _seed(client)
    monkeypatch.delenv("RERANK")
    results = client.get("/api/search?q=sip+routing&mode=semantic").json()
    assert results
    assert all(r["via"] == "semantic" for r in results)
    assert all("rerank_score" not in r for r in results)


def test_reranker_stub_singleton(monkeypatch):
    monkeypatch.setenv("EMBED_STUB", "1")
    embeddings.reset_embedder()
    assert isinstance(embeddings.get_reranker(), embeddings._StubReranker)
    assert embeddings.get_reranker() is embeddings.get_reranker()
    embeddings.reset_embedder()


def test_stub_scores_are_float32():
    out = embeddings._StubReranker().score("a b", ["a b a", "c"])
    assert out.dtype == np.float32
