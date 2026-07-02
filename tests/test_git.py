"""Tests for git-based page versioning."""

from __future__ import annotations

import unittest.mock as mock


def _register_and_token(client) -> str:
    client.post("/api/auth/register", json={"email": "u@test.com", "password": "password123"})
    r = client.post("/api/token", json={"email": "u@test.com", "password": "password123"})
    return r.json()["token"]


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_git_commit_stored_on_create(client):
    token = _register_and_token(client)
    r = client.post(
        "/api/pages",
        json={"title": "My Page", "content": "Hello git"},
        headers=_headers(token),
    )
    assert r.status_code == 201
    slug = r.json()["slug"]

    import app.db as db_module
    page = db_module.get_page(slug, *_get_uid_wid())
    assert page is not None
    assert page.git_commit is not None
    assert len(page.git_commit) == 7


def test_history_endpoint_returns_commits(client):
    token = _register_and_token(client)
    r = client.post(
        "/api/pages",
        json={"title": "History Test", "content": "v1"},
        headers=_headers(token),
    )
    slug = r.json()["slug"]

    client.put(
        f"/api/pages/{slug}",
        json={"content": "v2"},
        headers=_headers(token),
    )

    r = client.get(f"/api/pages/{slug}/history", headers=_headers(token))
    assert r.status_code == 200
    history = r.json()
    assert len(history) >= 2
    assert "sha" in history[0]
    assert "timestamp" in history[0]
    assert "message" in history[0]
    # El autor del commit es el email del usuario que inició sesión.
    assert history[0]["author"] == "u@test.com"


def test_history_at_commit_returns_old_content(client):
    token = _register_and_token(client)
    r = client.post(
        "/api/pages",
        json={"title": "Rollback Test", "content": "original content"},
        headers=_headers(token),
    )
    slug = r.json()["slug"]

    history_r = client.get(f"/api/pages/{slug}/history", headers=_headers(token))
    first_sha = history_r.json()[0]["sha"]

    client.put(f"/api/pages/{slug}", json={"content": "updated content"}, headers=_headers(token))

    r = client.get(f"/api/pages/{slug}/history/{first_sha}", headers=_headers(token))
    assert r.status_code == 200
    assert "original content" in r.json()["content"]


def test_git_failure_is_silent(client):
    """If git fails (e.g. not installed), page creation still succeeds."""
    token = _register_and_token(client)
    import app.git_repo as git_module

    with mock.patch.object(git_module, "commit_page", return_value=None):
        r = client.post(
            "/api/pages",
            json={"title": "No Git", "content": "still works"},
            headers=_headers(token),
        )
    assert r.status_code == 201


def test_history_returns_empty_for_unknown_slug(client):
    token = _register_and_token(client)
    r = client.get("/api/pages/nonexistent/history", headers=_headers(token))
    assert r.status_code == 404


def test_history_diff_returns_unified_diff(client):
    token = _register_and_token(client)
    slug = client.post(
        "/api/pages", json={"title": "Diff Test", "content": "line one"}, headers=_headers(token)
    ).json()["slug"]
    client.put(f"/api/pages/{slug}", json={"content": "line one changed"}, headers=_headers(token))

    latest_sha = client.get(
        f"/api/pages/{slug}/history", headers=_headers(token)
    ).json()[0]["sha"]
    r = client.get(f"/api/pages/{slug}/history/{latest_sha}/diff", headers=_headers(token))
    assert r.status_code == 200
    diff = r.json()["diff"]
    assert "line one changed" in diff
    assert "@@" in diff


def test_history_diff_root_commit_is_full_add(client):
    token = _register_and_token(client)
    slug = client.post(
        "/api/pages",
        json={"title": "Root Diff", "content": "original line"},
        headers=_headers(token),
    ).json()["slug"]
    client.put(f"/api/pages/{slug}", json={"content": "v2"}, headers=_headers(token))

    first_sha = client.get(f"/api/pages/{slug}/history", headers=_headers(token)).json()[-1]["sha"]
    r = client.get(f"/api/pages/{slug}/history/{first_sha}/diff", headers=_headers(token))
    assert r.status_code == 200
    assert "original line" in r.json()["diff"]


def _get_uid_wid() -> tuple[int, int]:
    import app.db as db_module
    user = db_module.get_user_by_email("u@test.com")
    assert user is not None
    uid = int(user.id)
    ws = db_module.ensure_default_workspace(uid)
    wid = int(ws.id)
    return uid, wid
