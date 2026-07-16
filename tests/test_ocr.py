"""Tests for opt-in OCR upload indexing (OCR_UPLOADS=1).

The tesseract binary itself is faked (monkeypatched): what's under test is the
wiring — extract → store in upload_texts → FTS search → REST/MCP surfacing.
"""

import json
import subprocess
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import ocr

# Solo importa el prefijo (magic bytes); extract_text está monkeypatcheado.
PNG = b"\x89PNG\r\n\x1a\n" + b"fake-png-payload"


@pytest.fixture()
def client(main_module, monkeypatch):
    monkeypatch.setenv("OCR_UPLOADS", "1")
    monkeypatch.setattr(ocr, "extract_text", lambda path: "kamailio dispatcher screenshot")
    with TestClient(main_module.app) as c:
        yield c


@pytest.fixture()
def client_no_ocr(main_module, monkeypatch):
    monkeypatch.delenv("OCR_UPLOADS", raising=False)
    with TestClient(main_module.app) as c:
        yield c


def _register(client):
    r = client.post("/api/auth/register", json={"email": "u@test.com", "password": "password123"})
    assert r.status_code == 201


def _upload(client):
    return client.post("/api/uploads", files={"file": ("shot.png", PNG, "image/png")})


def _upload_hits(client, q="kamailio", *, wait=True):
    """Search results of type=upload, polling briefly (OCR runs in a background task)."""
    for _ in range(100 if wait else 1):
        results = client.get(f"/api/search?q={q}&uploads=1").json()
        hits = [r for r in results if r.get("type") == "upload"]
        if hits:
            return hits
        time.sleep(0.05)
    return []


def test_upload_gets_indexed_and_searchable(client):
    _register(client)
    r = _upload(client)
    assert r.status_code == 200
    url = r.json()["url"]

    hits = _upload_hits(client)
    assert hits, "OCR text never became searchable"
    assert hits[0]["url"] == url
    assert "kamailio" in hits[0]["snippet"].lower()


def test_default_search_stays_pages_only(client):
    _register(client)
    _upload(client)
    assert _upload_hits(client)  # indexed
    # Without uploads=1 the response shape is unchanged (SPA compatibility).
    results = client.get("/api/search?q=kamailio").json()
    assert all(r.get("type") != "upload" for r in results)


def test_mcp_search_pages_includes_uploads(client):
    _register(client)
    _upload(client)
    assert _upload_hits(client)

    token = client.post(
        "/api/token", json={"email": "u@test.com", "password": "password123"}
    ).json()["token"]
    msg = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": "search_pages", "arguments": {"query": "dispatcher"}},
    }
    r = client.post("/api/mcp", json=msg, headers={"Authorization": f"Bearer {token}"})
    data = json.loads(r.json()["result"]["content"][0]["text"])
    assert any(item.get("type") == "upload" for item in data)


def test_ocr_disabled_indexes_nothing(client_no_ocr):
    _register(client_no_ocr)
    assert _upload(client_no_ocr).status_code == 200
    time.sleep(0.2)
    assert _upload_hits(client_no_ocr, wait=False) == []


def test_extract_text_handles_tesseract_failure(monkeypatch, tmp_path):
    img = tmp_path / "x.png"
    img.write_bytes(PNG)
    monkeypatch.setattr("app.ocr.shutil.which", lambda name: "/usr/bin/tesseract")

    monkeypatch.setattr(
        "app.ocr.subprocess.run",
        lambda *a, **kw: SimpleNamespace(returncode=1, stdout="", stderr="boom"),
    )
    assert ocr.extract_text(img) is None

    def _timeout(*a, **kw):
        raise subprocess.TimeoutExpired(cmd="tesseract", timeout=1)

    monkeypatch.setattr("app.ocr.subprocess.run", _timeout)
    assert ocr.extract_text(img) is None


def test_extract_text_without_binary(monkeypatch, tmp_path):
    monkeypatch.setattr("app.ocr.shutil.which", lambda name: None)
    assert ocr.extract_text(tmp_path / "x.png") is None


def test_index_upload_skips_empty_text(monkeypatch):
    monkeypatch.setattr(ocr, "extract_text", lambda path: "   \n ")
    # Sin texto no debe tocar la base de datos (no hay conexión válida en este test).
    assert ocr.index_upload("x.png", 1, 1, Path("/nonexistent.png")) is False
