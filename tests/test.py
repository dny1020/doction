"""End-to-end tests for doction using FastAPI's TestClient."""

from __future__ import annotations

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
    # Prevent HuggingFace model download in tests; embedder=None → FTS fallback.
    os.environ["HF_HUB_OFFLINE"] = "1"

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
