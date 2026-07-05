"""Tests de los endurecimientos v0.15: rate-limit en /api/token, /uploads
autenticado, revocación de sesiones al cambiar la contraseña (token_version),
JWT expirado, validación del SHA de git, límite de tamaño de subida y el
worker de embeddings saltándose páginas envenenadas."""

from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta

import jwt as pyjwt

EMAIL = "sec@example.com"
PASSWORD = "password123"

_TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


def _register(client, email: str = EMAIL, password: str = PASSWORD):
    r = client.post("/api/auth/register", json={"email": email, "password": password})
    assert r.status_code == 201


def _get_pages(client, token: str):
    return client.get("/api/pages", headers={"Authorization": f"Bearer {token}"})


# ── Rate limit en /api/token (antes solo /api/auth/login estaba protegido) ────


def test_api_token_rate_limited(client):
    _register(client)
    for _ in range(5):
        r = client.post("/api/token", json={"email": EMAIL, "password": "wrong"})
        assert r.status_code == 401
    blocked = client.post("/api/token", json={"email": EMAIL, "password": "wrong"})
    assert blocked.status_code == 429
    # Incluso con la contraseña correcta sigue bloqueado durante la ventana.
    correct = client.post("/api/token", json={"email": EMAIL, "password": PASSWORD})
    assert correct.status_code == 429


def test_password_length_capped(client):
    _register(client)
    r = client.post("/api/token", json={"email": EMAIL, "password": "x" * 10_000})
    assert r.status_code == 422  # validación de Pydantic, sin llegar al KDF


# ── /uploads autenticado (antes era un StaticFiles público) ───────────────────


def test_uploads_require_auth(client):
    _register(client)
    url = client.post("/api/uploads", files={"file": ("shot.png", _TINY_PNG, "image/png")}).json()[
        "url"
    ]
    assert client.get(url).status_code == 200  # con sesión
    client.cookies.clear()
    assert client.get(url).status_code == 401  # sin sesión


def test_uploads_reject_bad_names(client):
    _register(client)
    # Nombres que no cumplan el patrón hash.ext → 404, nunca tocan el filesystem.
    assert client.get("/uploads/..%2f..%2fetc%2fpasswd").status_code == 404
    assert client.get("/uploads/notahash.png").status_code == 404


def test_upload_too_large_413(client):
    _register(client)
    big = _TINY_PNG + b"\x00" * (5 * 1024 * 1024)
    r = client.post("/api/uploads", files={"file": ("big.png", big, "image/png")})
    assert r.status_code == 413
    assert "detail" in r.json()  # mismo shape de error que el resto de la API


# ── Sesiones: JWT expirado y revocación por cambio de contraseña ──────────────


def test_expired_jwt_rejected(client, main_module):
    _register(client)
    client.cookies.clear()  # la cookie de sesión tiene prioridad sobre el Bearer
    expired = pyjwt.encode(
        {"sub": "1", "ver": 0, "exp": datetime.now(UTC) - timedelta(minutes=1)},
        main_module.app.state.secret_key,
        algorithm="HS256",
    )
    assert _get_pages(client, expired).status_code == 401


def test_password_change_revokes_old_jwts(client):
    _register(client)
    old_jwt = client.post("/api/token", json={"email": EMAIL, "password": PASSWORD}).json()["token"]

    r = client.post(
        "/api/settings/password",
        json={
            "current_password": PASSWORD,
            "new_password": "newpassword123",
            "confirm_password": "newpassword123",
        },
    )
    assert r.status_code == 200
    # La sesión de quien cambió la contraseña se reemite en la respuesta y sigue viva.
    assert client.get("/api/me").status_code == 200

    # El JWT emitido antes del cambio queda revocado (token_version ya no coincide).
    # Cookies fuera: la cookie de sesión tiene prioridad sobre el Bearer.
    client.cookies.clear()
    assert _get_pages(client, old_jwt).status_code == 401


# ── SHA de git validado (un sha tipo "--flag" no llega a git show) ────────────


def test_invalid_git_sha_rejected(client):
    _register(client)
    slug = client.post("/api/pages", json={"title": "Doc", "content": "hola"}).json()["slug"]
    for bad_sha in ("--help", "zzzz", "abc"):  # opción, no-hex, demasiado corto
        r = client.get(f"/api/pages/{slug}/history/{bad_sha}/diff")
        assert r.status_code == 404
        r = client.get(f"/api/pages/{slug}/history/{bad_sha}")
        assert r.status_code == 404


# ── Worker de embeddings: una página que falla no bloquea la cola ─────────────


def test_enrichment_worker_skips_poison_page(client, main_module, monkeypatch):
    import asyncio

    import app.db as db
    import app.embeddings as embeddings

    _register(client)
    client.post("/api/pages", json={"title": "Bad", "content": "contenido"})
    assert db.pages_to_embed(50)  # hay pendientes (embed_dirty=1)

    def boom(*args, **kwargs):
        raise RuntimeError("poison page")

    monkeypatch.setattr(embeddings, "reindex_page", boom)

    async def run_until_drained():
        task = asyncio.create_task(embeddings.enrichment_worker(interval=0.01, batch=5))
        try:
            for _ in range(200):
                if not await asyncio.to_thread(db.pages_to_embed, 50):
                    return
                await asyncio.sleep(0.02)
            raise AssertionError("el worker no drenó la cola: página envenenada la bloquea")
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    asyncio.run(run_until_drained())
    assert db.pages_to_embed(50) == []
