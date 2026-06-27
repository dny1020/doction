"""Tests de los endpoints JSON que alimentan la SPA de React (Fase 1)."""

from __future__ import annotations

import importlib
import os
import tempfile

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    """App + base de datos temporal por test (la lifespan crea esquema + seed)."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    os.environ["DATABASE_PATH"] = tmp.name
    os.environ["SECRET_KEY"] = "test-secret-key-test-secret-key-32"

    import app.db as db_module
    import app.main as main_module

    importlib.reload(db_module)
    importlib.reload(main_module)

    with TestClient(main_module.app) as c:
        yield c

    for suffix in ("", "-wal", "-shm"):
        try:
            os.remove(tmp.name + suffix)
        except OSError:
            pass


def _register(client, email="user@example.com", password="password123"):
    return client.post("/api/auth/register", json={"email": email, "password": password})


def test_me_requires_session(client):
    assert client.get("/api/me").status_code == 401


def test_register_then_me(client):
    r = _register(client)
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == "user@example.com"
    assert body["active_workspace"]["slug"] == "personal"
    assert len(body["workspaces"]) == 1

    me = client.get("/api/me")
    assert me.status_code == 200
    assert me.json()["email"] == "user@example.com"


def test_register_validation(client):
    assert _register(client, password="short").status_code == 400
    assert _register(client, email="not-an-email").status_code == 400
    _register(client)
    assert _register(client).status_code == 409  # duplicado


def test_logout_clears_session(client):
    _register(client)
    assert client.get("/api/me").status_code == 200
    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/me").status_code == 401


def test_login_roundtrip(client):
    _register(client)
    client.post("/api/auth/logout")
    ok = client.post(
        "/api/auth/login",
        json={"email": "user@example.com", "password": "password123"},
    )
    assert ok.status_code == 200
    assert ok.json()["email"] == "user@example.com"
    assert client.get("/api/me").status_code == 200


def test_login_wrong_password(client):
    _register(client)
    client.post("/api/auth/logout")
    bad = client.post("/api/auth/login", json={"email": "user@example.com", "password": "nope"})
    assert bad.status_code == 401


def test_switch_workspace(client):
    _register(client)
    client.post("/api/workspaces", json={"name": "Work"})
    me = client.get("/api/me").json()
    other = [w for w in me["workspaces"] if w["slug"] != "personal"][0]
    r = client.post(f"/api/workspaces/{other['slug']}/switch")
    assert r.status_code == 200
    assert r.json()["slug"] == other["slug"]
    assert client.post("/api/workspaces/does-not-exist/switch").status_code == 404


def test_page_view(client):
    _register(client)  # siembra páginas de ejemplo
    r = client.get("/api/pages/welcome-to-doction/view")
    assert r.status_code == 200
    body = r.json()
    assert body["slug"] == "welcome-to-doction"
    assert "content" in body
    for key in ("breadcrumbs", "children", "backlinks", "related"):
        assert isinstance(body[key], list)
    assert client.get("/api/pages/nope/view").status_code == 404
