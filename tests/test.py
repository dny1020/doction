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
