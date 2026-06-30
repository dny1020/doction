"""End-to-end tests for doction's infra + REST API (agent-facing).

The web UI is the React SPA at /app; its endpoints are covered by
tests/test_spa_api.py. This file focuses on /health, /docs, the Bearer-token
REST API, image uploads, and a legacy-DB migration.
"""

from __future__ import annotations

import base64
import importlib
import os
import tempfile

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    """Fresh app + temp database per test (lifespan creates schema + seed)."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    os.environ["DATABASE_PATH"] = tmp.name
    os.environ["SECRET_KEY"] = "test-secret-key-test-secret-key-32"

    # Re-import so modules pick up the temp DATABASE_PATH cleanly.
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


def _register(client, email: str = "user@example.com", password: str = "password123"):
    """Crea un usuario por la API (deja la cookie de sesión en el cliente)."""
    return client.post("/api/auth/register", json={"email": email, "password": password})


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["db"] == "ok"
    assert "version" in body


def test_docs_available(client):
    # Required by the CI smoke test.
    assert client.get("/docs").status_code == 200


def test_root_redirects_to_spa(client):
    r = client.get("/", follow_redirects=False)
    assert r.status_code in (303, 307)
    assert r.headers["location"] == "/app/"


# ── REST API tests (Bearer token, agent-facing) ───────────────────────────────

def _api_token(client, email="user@example.com", password="password123") -> str:
    _register(client, email, password)
    r = client.post("/api/token", json={"email": email, "password": password})
    assert r.status_code == 200
    return r.json()["token"]


def test_api_token_valid(client):
    token = _api_token(client)
    assert isinstance(token, str) and len(token) > 20


def test_api_token_bad_password(client):
    _register(client)
    r = client.post("/api/token", json={"email": "user@example.com", "password": "wrong"})
    assert r.status_code == 401


def test_api_pages_crud(client):
    token = _api_token(client)
    hdrs = {"Authorization": f"Bearer {token}"}

    # create
    r = client.post(
        "/api/pages", json={"title": "Runbook", "content": "# Steps\nDo X."}, headers=hdrs
    )
    assert r.status_code == 201
    slug = r.json()["slug"]

    # read JSON
    r = client.get(f"/api/pages/{slug}", headers=hdrs)
    assert r.status_code == 200
    assert r.json()["title"] == "Runbook"
    assert r.json()["content"] == "# Steps\nDo X."

    # read raw markdown
    r = client.get(f"/api/pages/{slug}/raw", headers=hdrs)
    assert r.status_code == 200
    assert "# Steps" in r.text

    # update (partial patch)
    r = client.put(f"/api/pages/{slug}", json={"content": "# Steps\nDo Y."}, headers=hdrs)
    assert r.status_code == 200
    assert client.get(f"/api/pages/{slug}", headers=hdrs).json()["content"] == "# Steps\nDo Y."

    # delete
    assert client.delete(f"/api/pages/{slug}", headers=hdrs).status_code == 204
    assert client.get(f"/api/pages/{slug}", headers=hdrs).status_code == 404


def test_api_subpage_creation(client):
    token = _api_token(client)
    hdrs = {"Authorization": f"Bearer {token}"}
    client.post("/api/pages", json={"title": "Parent"}, headers=hdrs)
    client.post("/api/pages", json={"title": "Child", "parent_slug": "parent"}, headers=hdrs)

    page = client.get("/api/pages/parent", headers=hdrs).json()
    assert any(c["slug"] == "child" for c in page["children"])
    assert client.get("/api/pages/child", headers=hdrs).json()["parent_slug"] == "parent"


def test_api_search(client):
    token = _api_token(client)
    hdrs = {"Authorization": f"Bearer {token}"}
    client.post(
        "/api/pages", json={"title": "Terraform Guide", "content": "provision infra"}, headers=hdrs
    )
    r = client.get("/api/search", params={"q": "terraform"}, headers=hdrs)
    assert r.status_code == 200
    assert any(p["slug"] == "terraform-guide" for p in r.json())


def test_api_workspaces(client):
    token = _api_token(client)
    hdrs = {"Authorization": f"Bearer {token}"}
    r = client.post("/api/workspaces", json={"name": "Infra"}, headers=hdrs)
    assert r.status_code == 201
    assert r.json()["slug"] == "infra"

    r = client.get("/api/workspaces", headers=hdrs)
    assert r.status_code == 200
    names = [w["name"] for w in r.json()]
    assert "Infra" in names and "Personal" in names


def test_api_requires_auth(client):
    r = client.get("/api/pages")
    assert r.status_code == 401


# ── Image uploads (used by the SPA editor) ────────────────────────────────────

_TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


def test_image_upload_and_serve(client):
    _register(client)  # deja la cookie de sesión
    r = client.post("/api/uploads", files={"file": ("shot.png", _TINY_PNG, "image/png")})
    assert r.status_code == 200
    url = r.json()["url"]
    assert url.startswith("/uploads/") and url.endswith(".png")
    served = client.get(url)
    assert served.status_code == 200
    assert served.content == _TINY_PNG


def test_image_upload_rejects_non_image(client):
    _register(client)
    r = client.post("/api/uploads", files={"file": ("notes.txt", b"hello world", "text/plain")})
    assert r.status_code == 400


def test_image_upload_rejects_spoofed_content_type(client):
    _register(client)
    # Dice ser png pero los bytes no lo son → rechazado por magic bytes.
    r = client.post("/api/uploads", files={"file": ("x.png", b"not a real png", "image/png")})
    assert r.status_code == 400


def test_image_upload_requires_auth(client):
    r = client.post("/api/uploads", files={"file": ("shot.png", _TINY_PNG, "image/png")})
    assert r.status_code == 401


def test_user_columns_added_on_legacy_db(tmp_path, monkeypatch):
    """init_db adds display_name/avatar_color to an existing users table."""
    import sqlite3

    dbfile = tmp_path / "legacy.db"
    monkeypatch.setenv("DATABASE_PATH", str(dbfile))
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-test-secret-key-32")

    import app.db as db_module

    importlib.reload(db_module)

    conn = sqlite3.connect(dbfile)
    conn.executescript(
        "CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "email TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL, created_at TEXT NOT NULL);"
    )
    conn.commit()
    conn.close()

    db_module.init_db()

    cols = {
        row[1]
        for row in sqlite3.connect(dbfile).execute("PRAGMA table_info(users)")
    }
    assert "display_name" in cols
    assert "avatar_color" in cols
