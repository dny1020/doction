"""Fixtures compartidas para toda la suite.

Antes cada archivo de test definía su propio `client()` casi idéntico (un archivo
SQLite temporal + reload de módulos). Con Postgres esa duplicación ya no tiene
sentido: aquí una sola base de datos aislada por test (CREATE DATABASE / DROP
DATABASE), igual de descartable que el archivo temporal de antes pero contra el
motor real. `DATA_DIR` usa `tmp_path` para que el repo git de páginas y los
uploads sigan aislados por test, independientes de la base de datos.
"""

from __future__ import annotations

import importlib
import os
import uuid

import psycopg
import pytest

# Servidor Postgres de test (no la base final: aquí solo se listan/crean bases).
ADMIN_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql://doction:doction@localhost:5432/postgres"
)


@pytest.fixture()
def main_module(tmp_path, monkeypatch):
    """App fresca: base Postgres aislada (una por test) + DATA_DIR en tmp_path."""
    db_name = f"doction_test_{uuid.uuid4().hex[:16]}"
    with psycopg.connect(ADMIN_DATABASE_URL, autocommit=True) as admin:
        admin.execute(f'CREATE DATABASE "{db_name}"')

    base_url = ADMIN_DATABASE_URL.rsplit("/", 1)[0]
    monkeypatch.setenv("DATABASE_URL", f"{base_url}/{db_name}")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-test-secret-key-32")

    import app.db as db_module
    import app.embeddings as emb_module
    import app.git_repo as git_module
    import app.main as main_mod

    importlib.reload(db_module)
    importlib.reload(git_module)
    importlib.reload(emb_module)
    importlib.reload(main_mod)

    yield main_mod

    db_module.reset_pool()
    with psycopg.connect(ADMIN_DATABASE_URL, autocommit=True) as admin:
        admin.execute(f'DROP DATABASE IF EXISTS "{db_name}" WITH (FORCE)')


@pytest.fixture()
def client(main_module):
    from fastapi.testclient import TestClient

    with TestClient(main_module.app) as c:
        yield c
