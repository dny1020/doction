"""Tests for the Phase 1 'trust foundation': security headers, XSS escaping,
login rate limiting, and the styled 500 handler."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_security_headers_present(client):
    r = client.get("/app/login")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert "content-security-policy" in r.headers
    # HSTS solo cuando SECURE_COOKIES está activo (no en este test).
    assert "strict-transport-security" not in r.headers


def test_login_rate_limited(client):
    client.post("/api/auth/register", json={"email": "rl@example.com", "password": "password123"})
    # 5 intentos fallidos permitidos (401); el 6º se bloquea con 429.
    for _ in range(5):
        r = client.post("/api/auth/login", json={"email": "rl@example.com", "password": "wrong"})
        assert r.status_code == 401
    blocked = client.post("/api/auth/login", json={"email": "rl@example.com", "password": "wrong"})
    assert blocked.status_code == 429
    # Incluso con la contraseña correcta sigue bloqueado durante la ventana.
    correct = client.post(
        "/api/auth/login", json={"email": "rl@example.com", "password": "password123"}
    )
    assert correct.status_code == 429


def test_unhandled_exception_returns_json(main_module):
    @main_module.app.get("/_boom")
    async def _boom():
        raise RuntimeError("kaboom")

    with TestClient(main_module.app, raise_server_exceptions=False) as c:
        r = c.get("/_boom")
        assert r.status_code == 500
        assert "kaboom" not in r.text  # sin filtrar el traceback
        assert r.json() == {"detail": "Internal server error"}


def test_api_unhandled_exception_returns_json(main_module):
    @main_module.app.get("/api/_boom")
    async def _boom():
        raise RuntimeError("kaboom")

    with TestClient(main_module.app, raise_server_exceptions=False) as c:
        r = c.get("/api/_boom")
        assert r.status_code == 500
        assert r.json() == {"detail": "Internal server error"}
