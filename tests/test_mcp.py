"""Tests for the MCP server tool functions (called directly, no stdio)."""

from __future__ import annotations

import importlib
import os

import pytest


@pytest.fixture()
def mcp_env(tmp_path):
    """Set up temp DB, create a test user, wire up mcp_server globals."""
    db_file = tmp_path / "test.db"
    os.environ["DATABASE_PATH"] = str(db_file)

    import app.db as db_module
    import app.mcp_server as mcp_module

    importlib.reload(db_module)
    importlib.reload(mcp_module)

    db_module.init_db()
    from app.auth import hash_password
    uid = db_module.create_user("mcp@test.com", hash_password("password123"))
    ws = db_module.ensure_default_workspace(uid)

    mcp_module._user_id = uid
    mcp_module._workspace_id = int(ws["id"])

    return mcp_module


def test_list_workspaces(mcp_env):
    workspaces = mcp_env.list_workspaces()
    assert isinstance(workspaces, list)
    assert len(workspaces) >= 1
    assert "slug" in workspaces[0]
    assert "name" in workspaces[0]


def test_create_and_get_page(mcp_env):
    result = mcp_env.create_page("Hello MCP", "# Hello\nFrom MCP server.")
    assert "slug" in result
    assert result["title"] == "Hello MCP"

    page = mcp_env.get_page(result["slug"])
    assert page["title"] == "Hello MCP"
    assert "From MCP server" in page["content"]


def test_list_pages(mcp_env):
    mcp_env.create_page("Page A", "content a")
    mcp_env.create_page("Page B", "content b")
    pages = mcp_env.list_pages()
    slugs = [p["slug"] for p in pages]
    assert any("page-a" in s for s in slugs)
    assert any("page-b" in s for s in slugs)


def test_search_pages(mcp_env):
    mcp_env.create_page("Kamailio Runbook", "kamailio SIP proxy configuration")
    results = mcp_env.search_pages("kamailio")
    assert len(results) >= 1
    assert any("kamailio" in r["slug"] or "Kamailio" in r["title"] for r in results)


def test_update_page(mcp_env):
    result = mcp_env.create_page("To Update", "original")
    slug = result["slug"]

    updated = mcp_env.update_page(slug, content="updated content")
    assert updated["updated"] is True

    page = mcp_env.get_page(slug)
    assert "updated content" in page["content"]


def test_get_page_not_found_raises(mcp_env):
    with pytest.raises(ValueError, match="Page not found"):
        mcp_env.get_page("nonexistent-slug")


def test_update_page_not_found_raises(mcp_env):
    with pytest.raises(ValueError, match="Page not found"):
        mcp_env.update_page("nonexistent-slug", content="new")


def test_create_subpage(mcp_env):
    parent = mcp_env.create_page("Parent", "parent content")
    child = mcp_env.create_page("Child", "child content", parent_slug=parent["slug"])
    assert "slug" in child

    parent_page = mcp_env.get_page(parent["slug"])
    child_slugs = [c["slug"] for c in parent_page["children"]]
    assert child["slug"] in child_slugs
