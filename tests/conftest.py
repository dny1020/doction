"""Fixtures compartidas para toda la suite.

Antes cada archivo de test definía su propio `client()` casi idéntico (un archivo
SQLite temporal + reload de módulos). Con Postgres esa duplicación ya no tiene
sentido: aquí una sola base de datos aislada por test (CREATE DATABASE / DROP
DATABASE), igual de descartable que el archivo temporal de antes pero contra el
motor real. `DATA_DIR` usa `tmp_path` para que el repo git de páginas y los
uploads sigan aislados por test, independientes de la base de datos.

El servidor Postgres de los tests es **propio y efímero**: si `TEST_DATABASE_URL`
no está definida (CI sí la define — Postgres embebido en el stage `test` del
Dockerfile), conftest levanta un contenedor `doction-test-pg` con el datadir en
tmpfs (RAM), en el puerto 55432 solo-loopback. Nada que ver con el Postgres de
dev del compose: la suite ya no depende de que ese contenedor exista, esté
corriendo o tenga los permisos bien. Limpieza: `docker rm -f doction-test-pg`
(o nada — pesa ~40 MB de RAM y arranca solo la próxima vez).
"""

from __future__ import annotations

import importlib
import os
import subprocess
import time
import uuid

import psycopg
import pytest

TEST_PG_CONTAINER = "doction-test-pg"
TEST_PG_PORT = 55432
TEST_PG_IMAGE = "postgres:16-alpine"


def _reachable(url: str) -> bool:
    try:
        with psycopg.connect(url, connect_timeout=2):
            return True
    except psycopg.OperationalError:
        return False


@pytest.fixture(scope="session")
def admin_database_url() -> str:
    """URL admin del servidor Postgres de tests (solo para CREATE/DROP DATABASE).

    Prioridad: TEST_DATABASE_URL (CI/config manual) → contenedor efímero local.
    """
    url = os.environ.get("TEST_DATABASE_URL")
    if url:
        return url

    url = f"postgresql://doction:doction@localhost:{TEST_PG_PORT}/postgres"
    if _reachable(url):
        return url

    # Arranca (o re-arranca) el Postgres efímero. Con tmpfs el datadir vive en
    # RAM: cada arranque parte de cero (initdb re-corre con estas credenciales)
    # y no existe ningún archivo en disco cuyos permisos puedan romperse.
    started = subprocess.run(["docker", "start", TEST_PG_CONTAINER], capture_output=True, text=True)
    if started.returncode != 0:
        created = subprocess.run(
            [
                "docker",
                "run",
                "-d",
                "--name",
                TEST_PG_CONTAINER,
                "-p",
                f"127.0.0.1:{TEST_PG_PORT}:5432",
                "-e",
                "POSTGRES_USER=doction",
                "-e",
                "POSTGRES_PASSWORD=doction",
                "--tmpfs",
                "/var/lib/postgresql/data",
                TEST_PG_IMAGE,
            ],
            capture_output=True,
            text=True,
        )
        if created.returncode != 0:
            pytest.exit(
                "No se pudo levantar el Postgres de tests "
                f"({TEST_PG_CONTAINER}): {created.stderr.strip()}\n"
                "Alternativa: exporta TEST_DATABASE_URL hacia un Postgres accesible.",
                returncode=1,
            )

    for _ in range(60):
        if _reachable(url):
            return url
        time.sleep(0.5)
    pytest.exit(
        f"Timeout esperando el Postgres de tests en localhost:{TEST_PG_PORT} "
        f"(contenedor {TEST_PG_CONTAINER}); revisa `docker logs {TEST_PG_CONTAINER}`.",
        returncode=1,
    )


@pytest.fixture()
def main_module(tmp_path, monkeypatch, admin_database_url):
    """App fresca: base Postgres aislada (una por test) + DATA_DIR en tmp_path."""
    db_name = f"doction_test_{uuid.uuid4().hex[:16]}"
    with psycopg.connect(admin_database_url, autocommit=True) as admin:
        admin.execute(f'CREATE DATABASE "{db_name}"')

    base_url = admin_database_url.rsplit("/", 1)[0]
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
    with psycopg.connect(admin_database_url, autocommit=True) as admin:
        admin.execute(f'DROP DATABASE IF EXISTS "{db_name}" WITH (FORCE)')


@pytest.fixture()
def client(main_module):
    from fastapi.testclient import TestClient

    with TestClient(main_module.app) as c:
        yield c
