"""Tests for the Phase A intelligence tools: extract / list_backlinks / related_pages."""

from __future__ import annotations

import importlib
import json
import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path):
    db_file = tmp_path / "test.db"
    os.environ["DATABASE_PATH"] = str(db_file)
    os.environ["SECRET_KEY"] = "test-secret-key-test-secret-key-32"

    import app.db as db_module
    import app.git_repo as git_module
    import app.main as main_module

    importlib.reload(db_module)
    importlib.reload(git_module)
    importlib.reload(main_module)

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


def test_extract_by_type_and_tag(client):
    token = _token(client)
    _call(client, token, "create_page", {
        "title": "Migrate SIP",
        "content": "---\ntype: decision\ntags: [sip, kamailio]\n---\nWe migrate.",
    })
    _call(client, token, "create_page", {
        "title": "SBC Runbook",
        "content": "---\ntype: runbook\ntags: [sbc]\n---\nFailover steps.",
    })

    decisions = _data(_call(client, token, "extract", {"type": "decision"}))
    assert [p["slug"] for p in decisions] == ["migrate-sip"]
    assert decisions[0]["tags"] == ["sip", "kamailio"]

    sip_tagged = _data(_call(client, token, "extract", {"tag": "sip"}))
    assert [p["slug"] for p in sip_tagged] == ["migrate-sip"]

    # No filter returns everything in the workspace (seed pages included).
    all_pages = _data(_call(client, token, "extract"))
    assert {"migrate-sip", "sbc-runbook"} <= {p["slug"] for p in all_pages}


def test_backlinks_follow_wikilinks(client):
    token = _token(client)
    _call(client, token, "create_page", {"title": "Failover", "content": "the target page"})
    _call(client, token, "create_page",
          {"title": "Runbook", "content": "see [[failover]] for details"})

    back = _data(_call(client, token, "list_backlinks", {"slug": "failover"}))
    assert [p["slug"] for p in back] == ["runbook"]

    # Updating to drop the link removes the backlink (re-indexed on save).
    _call(client, token, "update_page", {"slug": "runbook", "content": "no link now"})
    assert _data(_call(client, token, "list_backlinks", {"slug": "failover"})) == []


def test_related_pages_by_shared_tags(client):
    token = _token(client)
    _call(client, token, "create_page",
          {"title": "A", "content": "---\ntags: [sip, voip]\n---\na"})
    _call(client, token, "create_page",
          {"title": "B", "content": "---\ntags: [sip, voip]\n---\nb"})
    _call(client, token, "create_page",
          {"title": "C", "content": "---\ntags: [sip]\n---\nc"})

    related = _data(_call(client, token, "related_pages", {"slug": "a"}))
    slugs = [p["slug"] for p in related]
    assert slugs[0] == "b"  # shares 2 tags, ranked first
    assert "c" in slugs     # shares 1 tag
    assert related[0]["shared_tags"] == 2


def test_related_pages_missing_is_tool_error(client):
    token = _token(client)
    result = _call(client, token, "related_pages", {"slug": "nope"})
    assert result["isError"] is True
