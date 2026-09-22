"""Visibility into webhook deliveries.

`last_status` covers only the last attempt, so a queue stuck behind it was invisible.
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
    """`delivered_at` means "no longer retried", not "succeeded"."""
    token = _token(client)
    hook = _hook(client, token)
    client.post("/api/pages", json={"title": "Fires an event", "content": "x"}, headers=_h(token))
    pending = client.get(f"/api/webhooks/{hook}/deliveries", headers=_h(token)).json()[0]

    db.mark_failed(pending["id"], hook, "connection refused", db.MAX_DELIVERY_ATTEMPTS - 1)

    delivery = client.get(f"/api/webhooks/{hook}/deliveries", headers=_h(token)).json()[0]
    assert delivery["delivered_at"] is not None  # the worker retries it no further
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
    # Nor the event body: this is an operational view, not a dump.
    assert "payload" not in body


def test_another_workspace_cannot_read_deliveries(client):
    token_a = _token(client, "a@test.com")
    hook = _hook(client, token_a)
    token_b = _token(client, "b@test.com")

    r = client.get(f"/api/webhooks/{hook}/deliveries", headers=_h(token_b))
    assert r.status_code == 404

    # No session and no bearer is a 401 like any other authenticated route. The cookie
    # registration left has to be cleared, or the request goes out signed as B.
    client.cookies.clear()
    assert client.get(f"/api/webhooks/{hook}/deliveries").status_code == 401
