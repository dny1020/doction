"""Tests de GET /api/system: qué informa el despliegue sobre sí mismo.

Solo lectura: las banderas vienen del entorno del proceso, no de preferencias.
"""

import pytest

from app import db


def _register(client, email="user@example.com", password="password123"):
    return client.post("/api/auth/register", json={"email": email, "password": password})


def _report(client) -> dict:
    r = client.get("/api/system")
    assert r.status_code == 200, r.text
    return r.json()


def test_requires_authentication(client):
    assert client.get("/api/system").status_code == 401


def test_reports_version_and_database(client):
    _register(client)
    body = _report(client)
    assert body["db"] == "ok"
    assert body["version"] and body["version"] != "0.0.0"
    for flag in ("semantic_search", "rerank", "ocr_uploads"):
        assert isinstance(body[flag], bool)


def test_flags_follow_the_environment(client, monkeypatch):
    _register(client)
    assert _report(client)["ocr_uploads"] is False
    monkeypatch.setenv("OCR_UPLOADS", "1")
    assert _report(client)["ocr_uploads"] is True


def test_index_counts_absent_when_semantic_is_off(client, monkeypatch):
    """Un 0 con la función apagada no se distingue de un índice roto: mejor omitirlo."""
    _register(client)
    monkeypatch.delenv("SEMANTIC_SEARCH", raising=False)
    body = _report(client)
    assert body["semantic_search"] is False
    for key in ("embedding_model", "indexed_pages", "pending_pages"):
        assert key not in body


class _ExplodingEncoder:
    """Tiene nombre pero no se puede construir: si el informe lo instancia, falla."""

    name = "all-MiniLM-L6-v2-int8"

    def __init__(self):
        raise AssertionError("el informe no debe construir el encoder ONNX")


def test_reporting_does_not_load_the_model(client, monkeypatch):
    """Informar es barato: lee el nombre del atributo de clase, no abre la sesión."""
    from app import embeddings

    _register(client)
    monkeypatch.setenv("SEMANTIC_SEARCH", "1")
    monkeypatch.delenv("EMBED_STUB", raising=False)
    embeddings.reset_embedder()
    monkeypatch.setattr(embeddings, "_OnnxEmbedder", _ExplodingEncoder)

    body = _report(client)
    assert body["semantic_search"] is True
    assert body["embedding_model"] == "all-MiniLM-L6-v2-int8"


def test_index_counts_track_embedding_progress(client, monkeypatch):
    monkeypatch.setenv("SEMANTIC_SEARCH", "1")
    monkeypatch.setenv("EMBED_STUB", "1")
    from app import embeddings

    embeddings.reset_embedder()
    _register(client)

    before = _report(client)
    assert before["pending_pages"] > 0
    assert before["indexed_pages"] == 0

    embeddings.drain_pending()
    after = _report(client)
    assert after["pending_pages"] == 0
    assert after["indexed_pages"] == before["pending_pages"]


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_report_is_read_only(client, method):
    _register(client)
    assert getattr(client, method)("/api/system").status_code == 405


def test_index_counts_helper(client):
    """db.index_counts cuenta páginas, no chunks: una página con varios chunks es una."""
    _register(client)
    with db.connect() as conn:
        row = conn.execute("SELECT id FROM workspaces ORDER BY id LIMIT 1").fetchone()
    assert row is not None
    total, indexed = db.index_counts(int(row["id"]), "cualquier-modelo", "cualquier-troceador")
    assert total > 0
    assert indexed == 0
