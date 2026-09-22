"""Fixtures shared by the whole suite.

One isolated database per test (CREATE DATABASE / DROP DATABASE), and `DATA_DIR` on
`tmp_path` so the page git repo and the uploads are isolated too.

The tests bring their own Postgres: with `TEST_DATABASE_URL` unset, conftest starts a
`doction-test-pg` container with its datadir in tmpfs on loopback port 55432, so the
suite does not depend on the dev compose. Cleanup: `docker rm -f doction-test-pg`.
"""

import importlib
import os
import subprocess
import time
import uuid

import psycopg
import pytest
from psycopg import sql

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
    """Admin URL of the test Postgres, for CREATE/DROP DATABASE only.

    TEST_DATABASE_URL first, then the ephemeral local container.
    """
    url = os.environ.get("TEST_DATABASE_URL")
    if url:
        return url

    url = f"postgresql://doction:doction@localhost:{TEST_PG_PORT}/postgres"
    if _reachable(url):
        return url

    # Start (or restart) the ephemeral Postgres. With the datadir in tmpfs every start
    # is from scratch, and no file on disk can have its permissions break.
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
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(db_name)))

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
        admin.execute(
            sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(db_name))
        )


@pytest.fixture()
def client(main_module):
    from fastapi.testclient import TestClient

    with TestClient(main_module.app) as c:
        yield c
