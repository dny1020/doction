"""Tests for workspace export (zip of live pages).

Soft-delete/trash is covered by tests/test_spa_api.py; token management by
tests/test_tokens.py.
"""

from __future__ import annotations

import io
import zipfile

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(main_module):
    with TestClient(main_module.app) as c:
        # Registro por la API: deja la cookie de sesión, que autentica /api/*.
        c.post("/api/auth/register", json={"email": "u@example.com", "password": "password123"})
        yield c


def _ws_slug(client) -> str:
    return client.get("/api/workspaces").json()[0]["slug"]


def test_export_returns_zip_of_live_pages(client):
    slug = _ws_slug(client)
    client.post("/api/pages", json={"title": "Keep Me", "content": "# keep"})
    client.post("/api/pages", json={"title": "Drop Me", "content": "# drop"})
    client.delete("/api/pages/drop-me")  # soft-delete

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
