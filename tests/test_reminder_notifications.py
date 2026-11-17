"""Durable ntfy scheduling, isolation, retries and honest delivery acknowledgements."""

import io
import json
import urllib.error
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest

from app import db, reminders
from app import reminder_notifications as notify
from tests.helpers import get_token, mcp_call, tool_data

NOW = datetime(2030, 11, 16, 14, tzinfo=UTC)


@pytest.fixture(autouse=True)
def controlled_worker(monkeypatch):
    async def noop():
        return

    monkeypatch.setattr(notify, "delivery_worker", noop)
    monkeypatch.setattr(reminders, "utc_now", lambda: NOW)


def user(client):
    token = get_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    ws = tool_data(mcp_call(client, token, "list_workspaces"))[0]["slug"]
    return token, headers, ws


def settings(client, headers, **extra):
    return client.put(
        "/api/notification-settings",
        headers=headers,
        json={
            "enabled": True,
            "ntfy_url": "https://ntfy.example.test/private",
            **extra,
        },
    )


def create(client, token, ws, **extra):
    return tool_data(
        mcp_call(
            client,
            token,
            "create_reminder",
            {
                "workspace": ws,
                "title": "Revisar backup",
                "due_at": (NOW - timedelta(minutes=1)).isoformat(),
                "notes": "Notas privadas que no deben enviarse",
                **extra,
            },
        )
    )


def update(client, token, item, **extra):
    return tool_data(
        mcp_call(
            client,
            token,
            "update_reminder",
            {
                "workspace": item["workspace"],
                "id": item["id"],
                "expected_revision": item["revision"],
                **extra,
            },
        )
    )


def rows():
    with db.connect() as conn:
        return conn.execute("SELECT * FROM reminder_notifications ORDER BY id").fetchall()


def publisher(monkeypatch, outcome=None):
    sent = []

    def publish(config, message):
        sent.append((config["ntfy_url"], message))
        return outcome or (True, None, "message-1", False)

    monkeypatch.setattr(notify, "publish", publish)
    return sent


def test_disabled_by_default_and_secrets_are_never_returned(client, monkeypatch):
    token, headers, ws = user(client)
    item = create(client, token, ws)
    sent = publisher(monkeypatch)
    assert notify.drain_once() == 0 and rows() == [] and sent == []
    assert item["notification"]["state"] == "disabled"
    response = settings(client, headers, token="tk_private")
    assert response.status_code == 200
    assert response.json()["has_token"]
    assert "tk_private" not in response.text
    assert "token" not in client.get("/api/notification-settings", headers=headers).json()
    assert notify.drain_once() == 1
    assert notify.drain_once() == 0 and len(sent) == 1
    assert rows()[0]["status"] == "sent"
    assert "Notas privadas" not in json.dumps(sent)


def test_date_only_sends_at_local_nine_and_timed_reminders_at_the_instant(client, monkeypatch):
    token, headers, ws = user(client)
    settings(client, headers)
    create(client, token, ws, due_at=None, due_date="2030-11-16")
    create(client, token, ws, title="Exacto", due_at=NOW.isoformat())
    sent = publisher(monkeypatch)
    monkeypatch.setattr(reminders, "utc_now", lambda: NOW - timedelta(seconds=1))
    assert notify.drain_once() == 0
    monkeypatch.setattr(reminders, "utc_now", lambda: NOW)
    assert notify.drain_once() == 2 and len(sent) == 2
    assert all(row["attempts"] == 1 for row in rows())


def test_retry_backoff_survives_connection_pool_restart(client, monkeypatch):
    token, headers, ws = user(client)
    settings(client, headers)
    create(client, token, ws)
    sent = publisher(monkeypatch, (False, "connection_error", None, True))
    assert notify.drain_once() == 1
    first = rows()[0]
    assert first["status"] == "pending" and first["next_attempt_at"] == NOW + timedelta(seconds=30)
    assert notify.drain_once() == 0 and len(sent) == 1
    db.reset_pool()
    monkeypatch.setattr(reminders, "utc_now", lambda: NOW + timedelta(seconds=31))
    sent2 = publisher(monkeypatch)
    assert notify.drain_once() == 1 and len(sent2) == 1
    assert rows()[0]["status"] == "sent" and rows()[0]["attempts"] == 2
    assert notify.drain_once() == 0


def test_completion_and_reassignment_cancel_old_pending_notifications(client, monkeypatch):
    token, headers, ws = user(client)
    settings(client, headers)
    item = create(client, token, ws)
    notify.enqueue(NOW)
    item = update(client, token, item, status="completed")
    sent = publisher(monkeypatch)
    assert notify.drain_once() == 0 and rows()[0]["status"] == "cancelled"
    item = update(client, token, item, status="pending")
    assert notify.drain_once() == 1
    item = update(client, token, item, title="Otro título", notes="Otras notas")
    assert notify.drain_once() == 0 and len(sent) == 1
    item = update(client, token, item, due_at=(NOW + timedelta(hours=1)).isoformat())
    assert notify.drain_once() == 0
    monkeypatch.setattr(reminders, "utc_now", lambda: NOW + timedelta(hours=1))
    assert notify.drain_once() == 1 and len(sent) == 2
    assert sent[-1][1]["message"].startswith("Otro título")


def test_notify_only_the_responsible_member_and_stop_after_membership_revoked(client, monkeypatch):
    token, headers, ws = user(client)
    settings(client, headers)
    owner = db.get_user_by_email("u@test.com")
    other_token = get_token(client, email="other@test.com")
    other = db.get_user_by_email("other@test.com")
    other_headers = {"Authorization": f"Bearer {other_token}"}
    settings(client, other_headers, ntfy_url="https://ntfy.example.test/other")
    workspace = db.get_workspace_by_slug(owner.id, ws)
    db.add_workspace_member(workspace.id, other.id)
    item = create(client, token, ws, assignee_id=other.id)
    sent = publisher(monkeypatch)
    assert notify.drain_once() == 1
    assert sent[0][0] == "https://ntfy.example.test/other"
    item = update(client, token, item, due_at=(NOW - timedelta(minutes=2)).isoformat())
    notify.enqueue(NOW)
    db.remove_workspace_member(workspace.id, other.id)
    assert notify.drain_once() == 0 and len(sent) == 1
    assert rows()[-1]["status"] == "cancelled"
    db.add_workspace_member(workspace.id, other.id)
    assert notify.drain_once() == 1 and len(sent) == 2


def test_changed_date_only_clock_does_not_block_ready_deliveries(client, monkeypatch):
    token, headers, ws = user(client)
    settings(client, headers)
    create(client, token, ws, due_at=None, due_date="2030-11-16")
    notify.enqueue(NOW)
    settings(client, headers, date_only_time="10:00")
    create(client, token, ws, title="Con hora")
    sent = publisher(monkeypatch)
    assert notify.drain_once() == 1 and len(sent) == 1
    monkeypatch.setattr(reminders, "utc_now", lambda: NOW + timedelta(hours=1))
    assert notify.drain_once() == 1 and len(sent) == 2


def test_authentication_failure_stops_retrying_until_settings_are_saved(client, monkeypatch):
    token, headers, ws = user(client)
    settings(client, headers)
    create(client, token, ws)
    publisher(monkeypatch, (False, "HTTP 401", None, False))
    assert notify.drain_once() == 1 and rows()[0]["status"] == "failed"
    assert notify.drain_once() == 0
    settings(client, headers, token="tk_fixed")
    sent = publisher(monkeypatch)
    assert notify.drain_once() == 1 and len(sent) == 1


def test_concurrent_workers_send_one_confirmed_notification(client, monkeypatch):
    token, headers, ws = user(client)
    settings(client, headers)
    create(client, token, ws)
    sent = publisher(monkeypatch)
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(notify.drain_once) for _ in range(2)]
        assert sum(f.result() for f in futures) == 1
    assert len(sent) == 1 and rows()[0]["status"] == "sent"


def test_preferences_are_private_and_restricted_tokens_cannot_change_them(client):
    token, headers, ws = user(client)
    settings(client, headers, token="tk_original")
    preserved = settings(client, headers)
    assert preserved.json()["has_token"]
    moved = settings(client, headers, ntfy_url="https://another.example.test/topic")
    assert moved.status_code == 400 and "tk_original" not in moved.text
    assert settings(client, headers, token="").json()["has_token"] is False
    pat = client.post(
        "/api/tokens",
        headers=headers,
        json={
            "name": "reader",
            "policy": {
                "grants": [
                    {"workspace": ws, "actions": ["read"]},
                ]
            },
        },
    ).json()["token"]
    for method in ["get", "put"]:
        result = getattr(client, method)(
            "/api/notification-settings", headers={"Authorization": f"Bearer {pat}"}
        )
        assert result.status_code == 403
    assert (
        client.post(
            "/api/notification-settings/test", headers={"Authorization": f"Bearer {pat}"}
        ).status_code
        == 403
    )
    other = get_token(client, email="other@test.com")
    assert (
        client.get(
            "/api/notification-settings", headers={"Authorization": f"Bearer {other}"}
        ).json()["ntfy_url"]
        == ""
    )


@pytest.mark.parametrize(
    "url",
    [
        "https://ntfy.example.test",
        "file:///tmp/a",
        "https://user:pw@host/topic",
        "https://host/topic?token=private",
        "https://host/topic#fragment",
    ],
)
def test_invalid_destinations_are_rejected(url):
    with pytest.raises(ValueError):
        notify.destination(url)


def test_publish_json_unicode_token_and_response_validation(monkeypatch):
    captured = []

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self, limit):
            return json.dumps({"id": "message1", "topic": "private", "event": "message"}).encode()

    def open_request(req, timeout):
        captured.append(req)
        return Response()

    monkeypatch.setattr(notify._OPENER, "open", open_request)
    config = {"ntfy_url": "https://host/prefix/private", "ntfy_token": "tk_secret"}
    assert notify.publish(config, {"title": "Revisión", "message": "Bogotá"}) == (
        True,
        None,
        "message1",
        False,
    )
    request = captured[0]
    assert request.full_url == "https://host/prefix/"
    assert request.get_header("Authorization") == "Bearer tk_secret"
    assert json.loads(request.data)["message"] == "Bogotá"

    def failed(req, timeout):
        raise urllib.error.URLError("private URL with tk_secret")

    monkeypatch.setattr(notify._OPENER, "open", failed)
    result = notify.publish(config, {"message": "Hello"})
    assert result == (False, "connection_error", None, True)
    assert "tk_secret" not in str(result)

    def denied(req, timeout):
        raise urllib.error.HTTPError(req.full_url, 403, "secret response", {}, io.BytesIO())

    monkeypatch.setattr(notify._OPENER, "open", denied)
    assert notify.publish(config, {"message": "Hello"}) == (False, "HTTP 403", None, False)


def test_test_endpoint_uses_saved_preferences_without_enabling_real_delivery(client, monkeypatch):
    _, headers, _ = user(client)
    settings(client, headers, enabled=False)
    sent = publisher(monkeypatch)
    response = client.post("/api/notification-settings/test", headers=headers)
    assert response.status_code == 200 and response.json() == {"sent": True}
    assert len(sent) == 1 and "Prueba" in sent[0][1]["title"]
    assert client.get("/api/notification-settings", headers=headers).json()["enabled"] is False


def test_transient_failures_are_bounded_and_disabling_pauses_queue(client, monkeypatch):
    token, headers, ws = user(client)
    settings(client, headers)
    create(client, token, ws)
    sent = publisher(monkeypatch, (False, "HTTP 503", None, True))
    clock = NOW
    for attempt in range(1, notify.MAX_ATTEMPTS + 1):
        monkeypatch.setattr(reminders, "utc_now", lambda current=clock: current)
        assert notify.drain_once() == 1
        record = rows()[0]
        assert record["attempts"] == attempt
        clock = record["next_attempt_at"]
    assert record["status"] == "failed" and len(sent) == notify.MAX_ATTEMPTS
    settings(client, headers, enabled=False)
    assert notify.drain_once() == 0
    settings(client, headers)
    sent = publisher(monkeypatch)
    assert notify.drain_once() == 1 and len(sent) == 1


def test_reassignment_replaces_queued_recipient(client, monkeypatch):
    token, headers, ws = user(client)
    settings(client, headers)
    item = create(client, token, ws)
    notify.enqueue(NOW)
    owner = db.get_user_by_email("u@test.com")
    other_token = get_token(client, email="other@test.com")
    other = db.get_user_by_email("other@test.com")
    settings(client, {"Authorization": f"Bearer {other_token}"}, ntfy_url="https://host/other")
    db.add_workspace_member(db.get_workspace_by_slug(owner.id, ws).id, other.id)
    update(client, token, item, assignee_id=other.id)
    sent = publisher(monkeypatch)
    assert notify.drain_once() == 1
    assert [entry[0] for entry in sent] == ["https://host/other"]
    assert [row["status"] for row in rows()] == ["cancelled", "sent"]


def test_http_publish_to_local_ntfy_and_redirects_do_not_forward_secrets(monkeypatch):
    import threading
    import urllib.request
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    received = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            raw = self.rfile.read(int(self.headers["Content-Length"]))
            received.append((self.path, self.headers.get("Authorization"), json.loads(raw)))
            if self.path == "/redirect/":
                self.send_response(302)
                self.send_header("Location", "/destination/")
                self.end_headers()
            else:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(
                    json.dumps({"id": "local-id", "event": "message", "topic": "private"}).encode()
                )

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setattr(
        notify,
        "_OPENER",
        urllib.request.build_opener(urllib.request.ProxyHandler({}), notify._NoRedirect()),
    )
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        ok = notify.publish(
            {"ntfy_url": base + "/private", "ntfy_token": "tk_local"},
            {"title": "Revisión Bogotá", "message": "Mensaje"},
        )
        assert ok == (True, None, "local-id", False)
        assert received[0] == (
            "/",
            "Bearer tk_local",
            {"topic": "private", "title": "Revisión Bogotá", "message": "Mensaje"},
        )
        denied = notify.publish(
            {"ntfy_url": base + "/redirect/private", "ntfy_token": "tk_local"},
            {"message": "No redirect"},
        )
        assert denied == (False, "HTTP 302", None, False)
        assert len(received) == 2 and all(entry[0] != "/destination/" for entry in received)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_invalid_notification_settings_never_echo_tokens(client):
    _, headers, _ = user(client)
    secret = "tk_private_" + "x" * 4100
    response = settings(client, headers, token=secret)
    assert response.status_code == 422 and "tk_private" not in response.text
    response = settings(client, headers, token="tk_priváte")
    assert response.status_code == 400 and "tk_priváte" not in response.text
