"""Tests de la visibilidad de entregas de webhooks.

doction entrega hacia fuera: firma el evento y lo manda, reintentando con backoff.
Lo que faltaba era poder ver si esas entregas están llegando — `last_status` solo
cuenta el último intento y una cola atascada detrás no se veía.
"""

from app import db


def _register(client, email="a@test.com"):
    return client.post("/api/auth/register", json={"email": email, "password": "password123"})


def _token(client, email="a@test.com") -> str:
    _register(client, email)
    r = client.post("/api/token", json={"email": email, "password": "password123"})
    return r.json()["token"]


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _hook(client, token: str) -> int:
    r = client.post(
        "/api/webhooks",
        json={"url": "https://example.test/hook", "events": ""},
        headers=_h(token),
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_queued_delivery_reads_as_pending(client):
    token = _token(client)
    hook = _hook(client, token)
    client.post("/api/pages", json={"title": "Fires an event", "content": "x"}, headers=_h(token))

    deliveries = client.get(f"/api/webhooks/{hook}/deliveries", headers=_h(token)).json()
    assert deliveries, "crear una página debería encolar page.created"
    assert deliveries[0]["event"] == "page.created"
    assert deliveries[0]["status"] == "pending"
    assert deliveries[0]["attempts"] == 0


def test_exhausted_delivery_reads_as_failed_not_delivered(client):
    """`delivered_at` marca "ya no se reintenta", no "salió bien"."""
    token = _token(client)
    hook = _hook(client, token)
    client.post("/api/pages", json={"title": "Fires an event", "content": "x"}, headers=_h(token))
    pending = client.get(f"/api/webhooks/{hook}/deliveries", headers=_h(token)).json()[0]

    db.mark_failed(pending["id"], hook, "connection refused", db.MAX_DELIVERY_ATTEMPTS - 1)

    delivery = client.get(f"/api/webhooks/{hook}/deliveries", headers=_h(token)).json()[0]
    assert delivery["delivered_at"] is not None  # el worker no lo reintenta más
    assert delivery["status"] == "failed"
    assert delivery["last_error"] == "connection refused"


def test_delivered_reads_as_delivered(client):
    token = _token(client)
    hook = _hook(client, token)
    client.post("/api/pages", json={"title": "Fires an event", "content": "x"}, headers=_h(token))
    pending = client.get(f"/api/webhooks/{hook}/deliveries", headers=_h(token)).json()[0]

    db.mark_delivered(pending["id"], hook, "200")

    delivery = client.get(f"/api/webhooks/{hook}/deliveries", headers=_h(token)).json()[0]
    assert delivery["status"] == "delivered"
    assert delivery["last_error"] is None


def test_the_list_marks_a_failing_hook(client):
    token = _token(client)
    hook = _hook(client, token)
    client.post("/api/pages", json={"title": "Fires an event", "content": "x"}, headers=_h(token))

    hooks = client.get("/api/webhooks", headers=_h(token)).json()
    assert hooks[0]["pending"] == 1 and hooks[0]["failed"] == 0

    pending = client.get(f"/api/webhooks/{hook}/deliveries", headers=_h(token)).json()[0]
    db.mark_failed(pending["id"], hook, "boom", db.MAX_DELIVERY_ATTEMPTS - 1)

    hooks = client.get("/api/webhooks", headers=_h(token)).json()
    assert hooks[0]["pending"] == 0 and hooks[0]["failed"] == 1


def test_history_never_carries_the_signing_secret(client):
    token = _token(client)
    hook = _hook(client, token)
    client.post("/api/pages", json={"title": "Fires an event", "content": "x"}, headers=_h(token))

    body = client.get(f"/api/webhooks/{hook}/deliveries", headers=_h(token)).text
    assert "secret" not in body and "signature" not in body.lower()
    # Tampoco el cuerpo del evento: esto es una vista de operación, no un volcado.
    assert "payload" not in body


def test_another_workspace_cannot_read_deliveries(client):
    token_a = _token(client, "a@test.com")
    hook = _hook(client, token_a)
    token_b = _token(client, "b@test.com")

    r = client.get(f"/api/webhooks/{hook}/deliveries", headers=_h(token_b))
    assert r.status_code == 404

    # Sin sesión ni bearer: 401 como cualquier otra ruta autenticada. Hay que
    # limpiar la cookie que dejó el registro, o la petición va firmada como B.
    client.cookies.clear()
    assert client.get(f"/api/webhooks/{hook}/deliveries").status_code == 401
