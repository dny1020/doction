"""Primer arranque (sin usuarios) y creación de usuarios por CLI."""

from __future__ import annotations

import sys

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def app_mod(main_module):
    return main_module


def test_root_redirects_to_spa(app_mod):
    """La raíz lleva a la SPA de React (servida en /app)."""
    with TestClient(app_mod.app) as c:
        r = c.get("/", follow_redirects=False)
        assert r.status_code in (303, 307)
        assert r.headers["location"] == "/app/"


def test_registration_open_when_no_users(app_mod):
    """Instancia recién autoalojada sin usuarios → el registro está abierto (bootstrap)."""
    with TestClient(app_mod.app) as c:
        r = c.post(
            "/api/auth/register", json={"email": "first@example.com", "password": "password123"}
        )
        assert r.status_code == 201


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
            "/api/auth/login",
            json={"email": "cli@example.com", "password": "password123"},
        )
        assert r.status_code == 200  # login correcto
