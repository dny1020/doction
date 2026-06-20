"""Primer arranque (sin usuarios) y creación de usuarios por CLI."""

from __future__ import annotations

import importlib
import os
import sys
import tempfile

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def app_mod():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    os.environ["DATABASE_PATH"] = tmp.name
    os.environ["SECRET_KEY"] = "test-secret-key-test-secret-key-32"

    import app.db as d
    import app.main as m

    importlib.reload(d)
    importlib.reload(m)
    yield m

    for s in ("", "-wal", "-shm"):
        try:
            os.remove(tmp.name + s)
        except OSError:
            pass


def test_first_run_redirects_to_register(app_mod):
    """Instancia recién autoalojada sin usuarios → la home lleva a crear la cuenta."""
    with TestClient(app_mod.app) as c:
        r = c.get("/", follow_redirects=False)
        assert r.status_code in (303, 307)
        assert r.headers["location"] == "/register"
        # /login sigue siendo página pública (muestra el formulario + enlace a registro).
        assert c.get("/login", follow_redirects=False).status_code == 200


def test_login_shown_once_a_user_exists(app_mod):
    with TestClient(app_mod.app) as c:
        c.post("/register", data={"email": "a@b.com", "password": "password123"})
        c.cookies.clear()  # desautenticar
        assert c.get("/", follow_redirects=False).headers["location"] == "/login"
        assert c.get("/login", follow_redirects=False).status_code == 200


def test_create_user_script(app_mod):
    from scripts.create_user import main

    argv = sys.argv
    sys.argv = ["create_user", "cli@example.com", "--password", "password123"]
    try:
        assert main() == 0
        # No duplica.
        assert main() == 1
    finally:
        sys.argv = argv

    with TestClient(app_mod.app) as c:
        r = c.post(
            "/login",
            data={"email": "cli@example.com", "password": "password123"},
            follow_redirects=False,
        )
        assert r.status_code == 303  # login correcto
