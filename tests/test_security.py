"""Hardening: login rate limit, authenticated /uploads, session revocation on password
change, expired JWTs, git SHA validation, the upload size cap, and the embedding worker
skipping a page it cannot index.
"""

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


# ── Rate limit on /api/token ──────────────────────────────────────────────────


def test_api_token_rate_limited(client):
    _register(client)
    for _ in range(5):
        r = client.post("/api/token", json={"email": EMAIL, "password": "wrong"})
        assert r.status_code == 401
    blocked = client.post("/api/token", json={"email": EMAIL, "password": "wrong"})
    assert blocked.status_code == 429
    # Still blocked for the rest of the window, even with the right password.
    correct = client.post("/api/token", json={"email": EMAIL, "password": PASSWORD})
    assert correct.status_code == 429


def test_password_length_capped(client):
    _register(client)
    r = client.post("/api/token", json={"email": EMAIL, "password": "x" * 10_000})
    assert r.status_code == 422  # Pydantic validation, never reaching the KDF


# ── Authenticated /uploads ───────────────────────────────────────────────────


def test_uploads_require_auth(client):
    _register(client)
    url = client.post("/api/uploads", files={"file": ("shot.png", _TINY_PNG, "image/png")}).json()[
        "url"
    ]
    assert client.get(url).status_code == 200  # with a session
    client.cookies.clear()
    assert client.get(url).status_code == 401  # without one


def test_uploads_reject_bad_names(client):
    _register(client)
    # A name that does not match hash.ext is a 404 and never touches the filesystem.
    assert client.get("/uploads/..%2f..%2fetc%2fpasswd").status_code == 404
    assert client.get("/uploads/notahash.png").status_code == 404


def test_upload_too_large_413(client):
    _register(client)
    big = _TINY_PNG + b"\x00" * (5 * 1024 * 1024)
    r = client.post("/api/uploads", files={"file": ("big.png", big, "image/png")})
    assert r.status_code == 413
    assert "detail" in r.json()  # same error shape as the rest of the API


# ── Sessions: expired JWTs and revocation on password change ─────────────────


def test_expired_jwt_rejected(client, main_module):
    _register(client)
    client.cookies.clear()  # the session cookie takes priority over the Bearer
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
    # The session of whoever changed the password is reissued and stays alive.
    assert client.get("/api/me").status_code == 200

    # A JWT issued before the change is revoked: token_version no longer matches.
    # Cookies cleared, since the session cookie takes priority over the Bearer.
    client.cookies.clear()
    assert _get_pages(client, old_jwt).status_code == 401


# ── Validated git SHA (a "--flag" SHA never reaches git show) ────────────────


def test_invalid_git_sha_rejected(client):
    _register(client)
    slug = client.post("/api/pages", json={"title": "Doc", "content": "hola"}).json()["slug"]
    for bad_sha in ("--help", "zzzz", "abc"):  # an option, non-hex, too short
        r = client.get(f"/api/pages/{slug}/history/{bad_sha}/diff")
        assert r.status_code == 404
        r = client.get(f"/api/pages/{slug}/history/{bad_sha}")
        assert r.status_code == 404


# ── Embedding worker: a failing page does not block the queue ────────────────


def test_enrichment_worker_skips_poison_page(client, main_module, monkeypatch):
    import asyncio

    import app.db as db
    import app.embeddings as embeddings

    _register(client)
    client.post("/api/pages", json={"title": "Bad", "content": "contenido"})
    assert db.pages_to_embed(50)  # pending pages (embed_dirty=1)

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
