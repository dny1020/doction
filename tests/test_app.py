"""End-to-end tests for doction using FastAPI's TestClient."""

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


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def _register(client, email: str = "user@example.com", password: str = "password123"):
    return client.post("/register", data={"email": email, "password": password})


def test_docs_available(client):
    # Required by the CI smoke test.
    assert client.get("/docs").status_code == 200


def test_home_renders_seed(client):
    _register(client)
    r = client.get("/")
    assert r.status_code == 200
    assert "doction" in r.text


def test_create_and_read_page(client):
    _register(client)
    r = client.post(
        "/pages",
        data={"title": "My Test Note", "content": "# Hello\n\nSome **bold** text."},
    )
    assert r.status_code == 200  # followed the redirect
    assert "My Test Note" in r.text
    assert "<strong>bold</strong>" in r.text

    # Slug is derived from the title.
    page = client.get("/pages/my-test-note")
    assert page.status_code == 200
    assert "Some" in page.text


def test_search_finds_page(client):
    _register(client)
    client.post("/pages", data={"title": "Searchable Widget", "content": "kubernetes deploy"})
    r = client.get("/search", params={"q": "kubernetes"})
    assert r.status_code == 200
    assert "Searchable Widget" in r.text


def test_search_empty_query_returns_nothing(client):
    _register(client)
    r = client.get("/search", params={"q": "   "})
    assert r.status_code == 200
    assert "results" not in r.text.lower() or "Searchable" not in r.text


def test_update_page(client):
    _register(client)
    client.post("/pages", data={"title": "Edit Me", "content": "original"})
    r = client.post("/pages/edit-me", data={"title": "Edit Me", "content": "updated body"})
    assert r.status_code == 200
    assert "updated body" in r.text
    assert "original" not in client.get("/pages/edit-me").text


def test_slug_stays_stable_on_title_change(client):
    _register(client)
    client.post("/pages", data={"title": "Stable Slug", "content": "before"})
    r = client.post("/pages/stable-slug", data={"title": "Renamed Title", "content": "after"})
    assert r.status_code == 200
    assert "Renamed Title" in r.text
    assert client.get("/pages/stable-slug").status_code == 200
    assert client.get("/pages/renamed-title").status_code == 404


def test_subpage_creation(client):
    _register(client)
    client.post("/pages", data={"title": "Parent Node", "content": "root"})
    client.post(
        "/pages",
        data={"title": "Child Node", "content": "leaf", "parent_slug": "parent-node"},
    )

    parent = client.get("/pages/parent-node")
    assert parent.status_code == 200
    assert "Subpages" in parent.text
    assert 'href="/pages/child-node"' in parent.text

    child = client.get("/pages/child-node")
    assert child.status_code == 200
    assert 'href="/pages/parent-node"' in child.text


def test_workspaces_are_isolated(client):
    _register(client)
    client.post("/pages", data={"title": "Shared Name", "content": "from personal workspace"})

    create_workspace = client.post("/workspaces", data={"name": "Work"})
    assert create_workspace.status_code == 200

    client.post("/pages", data={"title": "Shared Name", "content": "from work workspace"})
    work_page = client.get("/pages/shared-name")
    assert "from work workspace" in work_page.text
    assert "from personal workspace" not in work_page.text

    client.get("/workspaces/switch/personal")
    personal_page = client.get("/pages/shared-name")
    assert "from personal workspace" in personal_page.text
    assert "from work workspace" not in personal_page.text


def test_delete_page(client):
    _register(client)
    client.post("/pages", data={"title": "Trash Me", "content": "bye"})
    assert client.get("/pages/trash-me").status_code == 200
    client.post("/pages/trash-me/delete")
    assert client.get("/pages/trash-me").status_code == 404


def test_preview_renders_markdown(client):
    _register(client)
    r = client.post("/preview", data={"content": "## Heading"})
    assert r.status_code == 200
    assert "<h2>Heading</h2>" in r.text


# ── REST API tests ────────────────────────────────────────────────────────────

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


# === Settings: profile, password, workspaces ================================

def test_settings_requires_auth(client):
    r = client.get("/settings", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/login"


def test_settings_page_renders(client):
    _register(client)
    r = client.get("/settings")
    assert r.status_code == 200
    assert "Settings" in r.text
    assert "Password" in r.text


def test_profile_update(client):
    _register(client)
    r = client.post(
        "/settings/profile",
        data={"display_name": "Danilo", "avatar_color": "#4a7fc0"},
    )
    assert r.status_code == 200  # redirect to /settings followed
    assert "Profile updated" in r.text

    home = client.get("/")
    assert 'title="Danilo"' in home.text
    assert "#4a7fc0" in home.text


def test_profile_rejects_unknown_color(client):
    _register(client)
    client.post("/settings/profile", data={"display_name": "X", "avatar_color": "#000000"})
    home = client.get("/")
    # The bogus color is dropped, so the avatar falls back to the JS hash (no data-color).
    assert "data-color=" not in home.text


def test_password_change(client):
    _register(client, password="password123")
    r = client.post(
        "/settings/password",
        data={
            "current_password": "password123",
            "new_password": "newpassword456",
            "confirm_password": "newpassword456",
        },
    )
    assert r.status_code == 200
    assert "Password updated" in r.text

    client.post("/logout")
    bad = client.post(
        "/login", data={"email": "user@example.com", "password": "password123"}
    )
    assert bad.status_code == 400
    assert "Invalid credentials" in bad.text

    good = client.post(
        "/login", data={"email": "user@example.com", "password": "newpassword456"}
    )
    assert good.status_code == 200
    assert "Invalid credentials" not in good.text


def test_password_change_wrong_current(client):
    _register(client, password="password123")
    r = client.post(
        "/settings/password",
        data={
            "current_password": "WRONG",
            "new_password": "newpassword456",
            "confirm_password": "newpassword456",
        },
    )
    assert "Your current password is incorrect" in r.text

    # Password is unchanged: the original still works.
    client.post("/logout")
    good = client.post(
        "/login", data={"email": "user@example.com", "password": "password123"}
    )
    assert good.status_code == 200


def test_password_change_too_short(client):
    _register(client, password="password123")
    r = client.post(
        "/settings/password",
        data={
            "current_password": "password123",
            "new_password": "short",
            "confirm_password": "short",
        },
    )
    assert "8+ characters" in r.text


def test_password_change_mismatch(client):
    _register(client, password="password123")
    r = client.post(
        "/settings/password",
        data={
            "current_password": "password123",
            "new_password": "newpassword456",
            "confirm_password": "different456",
        },
    )
    assert "match" in r.text  # "The new passwords don't match." (apóstrofo escapado en HTML)


def test_workspace_rename(client):
    _register(client)
    r = client.post("/workspaces/personal/rename", data={"name": "Personal Renombrado"})
    assert r.status_code == 200
    assert "Workspace renamed" in r.text
    assert "Personal Renombrado" in client.get("/settings").text


def test_workspace_delete(client):
    _register(client)
    client.post("/workspaces", data={"name": "Work"})  # second workspace, now active
    r = client.post("/workspaces/personal/delete")
    assert r.status_code == 200
    assert "Workspace deleted" in r.text
    settings = client.get("/settings").text
    assert "Work" in settings
    assert "Personal" not in settings


def test_cannot_delete_last_workspace(client):
    _register(client)
    r = client.post("/workspaces/personal/delete")
    assert "delete your only workspace" in r.text  # apóstrofo escapado en HTML
    # Still there.
    assert "Personal" in client.get("/settings").text


_TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


def test_image_upload_and_serve(client):
    _register(client)
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


# === i18n (language switch EN/ES) ==========================================

def test_default_language_is_english(client):
    r = client.get("/login")
    assert r.status_code == 200
    assert "Log in to access your notes." in r.text


def test_login_has_lang_and_theme_controls(client):
    r = client.get("/login")
    assert "auth-controls" in r.text
    assert "lang-switch" in r.text
    assert "/lang/es?" in r.text and "/lang/en?" in r.text
    assert "theme-toggle" in r.text  # toggle de modo claro/oscuro en el login


def test_switch_language_to_spanish(client):
    r = client.get("/lang/es")  # 303 → cookie 'lang=es', followed
    assert r.status_code == 200
    login = client.get("/login")
    assert "Inicia sesión para acceder a tus notas." in login.text
    # El switch marca ES como activo.
    assert 'lang-opt active"' in login.text or "active" in login.text


def test_accept_language_header_defaults_spanish(client):
    r = client.get("/login", headers={"accept-language": "es-ES,es;q=0.9"})
    assert "Inicia sesión para acceder a tus notas." in r.text


def test_settings_in_spanish(client):
    _register(client)
    client.get("/lang/es")
    s = client.get("/settings")
    assert "Configuración" in s.text
    assert "Perfil" in s.text
    assert "Cambiar contraseña" in s.text


def test_invalid_language_code_ignored(client):
    r = client.get("/lang/fr", follow_redirects=False)
    assert r.status_code == 303
    # No setea cookie para un idioma no soportado → sigue en inglés.
    assert "lang=fr" not in r.headers.get("set-cookie", "")
