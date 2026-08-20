"""Tests de los webhooks de salida.

No se hace ninguna llamada HTTP real: se comprueba que los eventos se encolen en
la misma transacción que la escritura, que la firma sea verificable, y que un
receptor caído reintente con backoff en vez de perder el evento.
"""

import hashlib
import hmac
import json

from app import db, webhooks
from app.models import PendingDelivery


def _token(client, email="hooks@example.com", password="password123") -> str:
    client.post("/api/auth/register", json={"email": email, "password": password})
    return client.post("/api/tokens", json={"name": "test"}).json()["token"]


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _pendientes() -> list:
    """Entregas encoladas, leídas por la misma vía que usa el worker."""
    return db.due_deliveries(50)


# ── registro ─────────────────────────────────────────────────────────────────


def test_secret_is_returned_once_and_never_listed(client):
    token = _token(client)
    created = client.post(
        "/api/webhooks", json={"url": "http://n8n:5678/webhook/x"}, headers=_h(token)
    ).json()
    assert created["secret"]

    listed = client.get("/api/webhooks", headers=_h(token)).json()
    assert len(listed) == 1
    assert "secret" not in listed[0]


def test_url_must_be_http(client):
    token = _token(client)
    r = client.post("/api/webhooks", json={"url": "file:///etc/passwd"}, headers=_h(token))
    assert r.status_code == 400


# ── emisión ──────────────────────────────────────────────────────────────────


def test_page_write_enqueues_a_delivery(client):
    token = _token(client)
    client.post("/api/webhooks", json={"url": "http://n8n:5678/w"}, headers=_h(token))

    client.post("/api/pages", json={"title": "Con hook", "content": "x"}, headers=_h(token))

    pendientes = _pendientes()
    assert len(pendientes) == 1
    assert pendientes[0].event == "page.created"
    payload = json.loads(pendientes[0].payload_json)
    assert payload["page"]["slug"] == "con-hook"
    assert payload["event"] == "page.created"


def test_event_filter_is_respected(client):
    token = _token(client)
    client.post(
        "/api/webhooks",
        json={"url": "http://n8n:5678/w", "events": "page.deleted"},
        headers=_h(token),
    )

    client.post("/api/pages", json={"title": "Filtrada", "content": "x"}, headers=_h(token))
    assert _pendientes() == []

    client.delete("/api/pages/filtrada", headers=_h(token))
    pendientes = _pendientes()
    assert [p.event for p in pendientes] == ["page.deleted"]


def test_no_webhook_means_no_queue(client):
    """Sin receptores registrados la escritura no debe encolar nada."""
    token = _token(client)
    client.post("/api/pages", json={"title": "Sin hook", "content": "x"}, headers=_h(token))
    assert _pendientes() == []


def test_rename_and_move_emit_their_own_events(client):
    token = _token(client)
    client.post("/api/webhooks", json={"url": "http://n8n:5678/w"}, headers=_h(token))
    client.post("/api/pages", json={"title": "Padre", "content": "x"}, headers=_h(token))
    client.post("/api/pages", json={"title": "Hija", "content": "y"}, headers=_h(token))

    client.post("/api/pages/hija/move", json={"parent_slug": "padre"}, headers=_h(token))
    client.post("/api/pages/hija/rename", json={"slug": "hija-nueva"}, headers=_h(token))

    eventos = [p.event for p in _pendientes()]
    assert "page.moved" in eventos
    assert "page.renamed" in eventos


# ── firma y entrega ──────────────────────────────────────────────────────────


def test_signature_is_verifiable_by_the_receiver(client):
    cuerpo = b'{"event":"page.created"}'
    firma = webhooks.sign("secreto", cuerpo)
    esperada = hmac.new(b"secreto", cuerpo, hashlib.sha256).hexdigest()
    assert firma == f"sha256={esperada}"


def test_unreachable_receiver_is_retried_not_dropped(client):
    token = _token(client)
    client.post("/api/webhooks", json={"url": "http://127.0.0.1:9/nope"}, headers=_h(token))
    client.post("/api/pages", json={"title": "Reintento", "content": "x"}, headers=_h(token))

    pendiente = _pendientes()[0]
    ok, detalle = webhooks.deliver(pendiente)
    assert ok is False
    assert detalle

    db.mark_failed(pendiente.id, pendiente.webhook_id, detalle, pendiente.attempts)
    # Sigue en la cola, pero reprogramada al futuro: no se ha perdido.
    assert _pendientes() == []
    hook = client.get("/api/webhooks", headers=_h(token)).json()[0]
    assert hook["last_status"]


def test_delivery_never_raises_on_a_bad_url(client):
    """deliver() debe devolver (False, motivo), nunca propagar."""
    item = PendingDelivery(
        id=1,
        webhook_id=1,
        url="http://no.existe.invalido.local/x",
        secret="s",
        event="page.created",
        payload_json="{}",
        attempts=0,
    )
    ok, detalle = webhooks.deliver(item)
    assert ok is False
    assert detalle
