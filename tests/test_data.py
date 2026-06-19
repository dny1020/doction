"""Tests for Phase 2 data features: soft-delete/trash and workspace export."""

from __future__ import annotations

import importlib
import io
import os
import tempfile
import zipfile

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    os.environ["DATABASE_PATH"] = tmp.name
    os.environ["SECRET_KEY"] = "test-secret-key-test-secret-key-32"

    import app.db as db_module
    import app.main as main_module

    importlib.reload(db_module)
    importlib.reload(main_module)

    with TestClient(main_module.app) as c:
        c.post("/register", data={"email": "u@example.com", "password": "password123"})
        yield c

    for suffix in ("", "-wal", "-shm"):
        try:
            os.remove(tmp.name + suffix)
        except OSError:
            pass


def _ws_slug(client) -> str:
    return client.get("/api/workspaces").json()[0]["slug"]


def test_soft_delete_hides_page_but_keeps_it_recoverable(client):
    client.post("/pages", data={"title": "Temp Note", "content": "secret body"})
    assert client.get("/pages/temp-note").status_code == 200

    # Borrar = mover a la papelera.
    client.post("/pages/temp-note/delete")
    assert client.get("/pages/temp-note").status_code == 404

    # No aparece en búsqueda...
    search = client.get("/search?q=Temp")
    assert "temp-note" not in search.text
    # ...pero sí en la papelera.
    trash = client.get("/trash")
    assert trash.status_code == 200
    assert "Temp Note" in trash.text


def test_restore_brings_page_back(client):
    client.post("/pages", data={"title": "Comeback", "content": "body"})
    client.post("/pages/comeback/delete")
    assert client.get("/pages/comeback").status_code == 404

    client.post("/trash/comeback/restore")
    assert client.get("/pages/comeback").status_code == 200
    # Ya no figura en la papelera (su acción de restaurar desaparece de la lista).
    assert "/trash/comeback/restore" not in client.get("/trash").text


def test_purge_deletes_permanently(client):
    client.post("/pages", data={"title": "Gone", "content": "body"})
    client.post("/pages/gone/delete")
    client.post("/trash/gone/purge")
    assert client.get("/pages/gone").status_code == 404
    assert "/trash/gone/purge" not in client.get("/trash").text
    # Tras purgar, el slug vuelve a estar libre para una página nueva.
    client.post("/pages", data={"title": "Gone", "content": "fresh"})
    assert client.get("/pages/gone").status_code == 200


def test_export_returns_zip_of_live_pages(client):
    slug = _ws_slug(client)
    client.post("/pages", data={"title": "Keep Me", "content": "# keep"})
    client.post("/pages", data={"title": "Drop Me", "content": "# drop"})
    client.post("/pages/drop-me/delete")

    r = client.get(f"/api/workspaces/{slug}/export")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/zip"

    zf = zipfile.ZipFile(io.BytesIO(r.content))
    names = zf.namelist()
    assert f"{slug}/keep-me.md" in names
    assert f"{slug}/drop-me.md" not in names  # soft-deleted ⇒ excluida
    assert zf.read(f"{slug}/keep-me.md").decode() == "# keep"


def test_export_unknown_workspace_404(client):
    assert client.get("/api/workspaces/nope/export").status_code == 404


def test_api_token_ui_create_and_revoke(client):
    # Crear: la respuesta muestra el token en claro una sola vez.
    r = client.post("/settings/tokens", data={"name": "laptop"})
    assert r.status_code == 200
    assert "doction_" in r.text
    assert "laptop" in r.text

    # Al recargar settings ya no se muestra el secreto, pero sí el token en la lista.
    s = client.get("/settings")
    assert "laptop" in s.text
    assert "doction_" not in s.text

    # Revocar por id.
    tid = client.get("/api/tokens").json()[0]["id"]
    client.post(f"/settings/tokens/{tid}/delete")
    assert client.get("/api/tokens").json() == []
