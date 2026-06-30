"""Tests for long-lived personal access tokens (PAT) at /api/tokens."""

from __future__ import annotations

import importlib
import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path):
    """Fresh app + temp DB per test; git repo lands in tmp_path/pages/."""
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


def _register_and_token(client, email: str = "u@test.com") -> str:
    client.post("/api/auth/register", json={"email": email, "password": "password123"})
    r = client.post("/api/token", json={"email": email, "password": "password123"})
    # Drop the session cookie so requests authenticate via Bearer header only.
    client.cookies.clear()
    return r.json()["token"]


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _create_pat(client, jwt: str, name: str = "agent") -> dict:
    r = client.post("/api/tokens", json={"name": name}, headers=_headers(jwt))
    assert r.status_code == 201
    return r.json()


def test_create_requires_auth(client):
    assert client.post("/api/tokens", json={"name": "x"}).status_code == 401


def test_create_returns_plaintext_once(client):
    jwt = _register_and_token(client)
    created = _create_pat(client, jwt)
    assert created["token"].startswith("doction_")
    assert created["name"] == "agent"
    listed = client.get("/api/tokens", headers=_headers(jwt)).json()
    assert len(listed) == 1
    assert listed[0]["name"] == "agent"
    assert "token" not in listed[0] and "token_hash" not in listed[0]


def test_pat_works_on_rest_api(client):
    jwt = _register_and_token(client)
    pat = _create_pat(client, jwt)["token"]
    r = client.get("/api/pages", headers=_headers(pat))
    assert r.status_code == 200


def test_pat_works_on_mcp(client):
    jwt = _register_and_token(client)
    pat = _create_pat(client, jwt)["token"]
    r = client.post(
        "/api/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/call",
              "params": {"name": "list_workspaces", "arguments": {}}},
        headers=_headers(pat),
    )
    assert r.status_code == 200
    assert "personal" in r.json()["result"]["content"][0]["text"]


def test_pat_sets_last_used(client):
    jwt = _register_and_token(client)
    created = _create_pat(client, jwt)
    listed = client.get("/api/tokens", headers=_headers(jwt)).json()
    assert listed[0]["last_used_at"] is None
    client.get("/api/pages", headers=_headers(created["token"]))
    listed = client.get("/api/tokens", headers=_headers(jwt)).json()
    assert listed[0]["last_used_at"] is not None


def test_revoke(client):
    jwt = _register_and_token(client)
    created = _create_pat(client, jwt)
    r = client.delete(f"/api/tokens/{created['id']}", headers=_headers(jwt))
    assert r.status_code == 204
    assert client.get("/api/pages", headers=_headers(created["token"])).status_code == 401
    r = client.delete(f"/api/tokens/{created['id']}", headers=_headers(jwt))
    assert r.status_code == 404


def test_invalid_pat_rejected(client):
    _register_and_token(client)
    r = client.get("/api/pages", headers=_headers("doction_" + "0" * 40))
    assert r.status_code == 401


def test_revoke_other_users_token_fails(client):
    jwt_a = _register_and_token(client)
    created = _create_pat(client, jwt_a)
    jwt_b = _register_and_token(client, email="b@test.com")
    r = client.delete(f"/api/tokens/{created['id']}", headers=_headers(jwt_b))
    assert r.status_code == 404
    assert client.get("/api/pages", headers=_headers(created["token"])).status_code == 200
