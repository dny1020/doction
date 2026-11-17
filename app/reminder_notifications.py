"""Per-user ntfy delivery with a durable queue and one notification per schedule generation."""

import asyncio
import json
import logging
import os
import re
import threading
import urllib.error
import urllib.request
from datetime import timedelta
from urllib.parse import quote, urlsplit, urlunsplit

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from app import access, db, reminders

logger = logging.getLogger(__name__)
INTERVAL = 30
TIMEOUT = 10
MAX_ATTEMPTS = 8
USER_LOCK = 27912


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    enabled: bool = False
    ntfy_url: str = Field(default="", max_length=2000)
    token: SecretStr | None = Field(
        default=None, max_length=4096, json_schema_extra={"writeOnly": True}
    )
    date_only_time: str = Field(default="09:00", pattern=r"^\d{2}:\d{2}$")


def destination(url):
    """Return the JSON publishing endpoint and topic; secrets never belong in the URL."""
    try:
        parsed = urlsplit(url.rstrip("/"))
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or any(c.isspace() for c in url)
        ):
            raise ValueError
        parsed.netloc.encode("ascii")
        _ = parsed.port
        prefix, _, topic = parsed.path.rpartition("/")
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", topic) or any(
            part in {".", ".."} for part in prefix.split("/")
        ):
            raise ValueError
        return urlunsplit((parsed.scheme, parsed.netloc, prefix + "/", "", "")), topic
    except (ValueError, UnicodeError) as exc:
        raise ValueError(
            "Use an HTTP(S) ntfy topic URL without credentials, query or fragment"
        ) from exc


def _private_settings(user_id):
    if access.policy.get() is not None:
        raise PermissionError("Restricted tokens cannot manage notification settings")
    with db.connect() as conn:
        return conn.execute(
            "SELECT * FROM notification_settings WHERE user_id = %s", (user_id,)
        ).fetchone()


def get_settings(user_id):
    row = _private_settings(user_id)
    return {
        "enabled": row["enabled"] if row else False,
        "ntfy_url": row["ntfy_url"] if row else "",
        "has_token": bool(row and row["ntfy_token"]),
        "date_only_time": row["date_only_time"].strftime("%H:%M") if row else "09:00",
    }


def save_settings(user_id, body):
    _private_settings(user_id)  # reject restricted credentials before validating or writing
    from datetime import time

    provided_token = body.token.get_secret_value() if body.token is not None else None
    clock = time.fromisoformat(body.date_only_time)
    endpoint = destination(body.ntfy_url) if body.ntfy_url else None
    if body.enabled and endpoint is None:
        raise ValueError("Configure an ntfy topic before enabling notifications")
    if provided_token is not None and any(ord(c) < 33 or ord(c) > 126 for c in provided_token):
        raise ValueError("The ntfy token must contain printable ASCII without spaces")
    with db.connect() as conn:
        conn.execute("SELECT pg_advisory_xact_lock(%s, %s)", (USER_LOCK, user_id))
        old = conn.execute(
            "SELECT * FROM notification_settings WHERE user_id = %s", (user_id,)
        ).fetchone()
        if (
            old
            and old["ntfy_token"]
            and provided_token is None
            and body.ntfy_url != old["ntfy_url"]
        ):
            previous = urlsplit(old["ntfy_url"])
            current = urlsplit(body.ntfy_url)
            if (previous.scheme, previous.netloc) != (current.scheme, current.netloc):
                raise ValueError(
                    "Provide a new token or explicitly clear it when changing ntfy server"
                )
        token = provided_token if provided_token is not None else (old["ntfy_token"] if old else "")
        conn.execute(
            "INSERT INTO notification_settings "
            "(user_id, enabled, ntfy_url, ntfy_token, date_only_time) "
            "VALUES (%s, %s, %s, %s, %s) ON CONFLICT (user_id) DO UPDATE SET "
            "enabled = EXCLUDED.enabled, ntfy_url = EXCLUDED.ntfy_url, "
            "ntfy_token = EXCLUDED.ntfy_token, date_only_time = EXCLUDED.date_only_time",
            (user_id, body.enabled, body.ntfy_url, token, clock),
        )
        if body.enabled:
            conn.execute(
                "UPDATE reminder_notifications SET status = 'pending', attempts = 0, "
                "last_error = NULL, next_attempt_at = NOW() "
                "WHERE assignee_id = %s AND status = 'failed'",
                (user_id,),
            )
    return get_settings(user_id)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, _req, _fp, _code, _msg, _headers, _newurl):
        return None


_OPENER = urllib.request.build_opener(_NoRedirect())


def publish(settings, message):
    """(success, sanitized error, ntfy message id, retryable). Never log URLs or tokens."""
    endpoint, topic = destination(settings["ntfy_url"])
    payload = {"topic": topic, **message}
    headers = {"Content-Type": "application/json; charset=utf-8"}
    if settings["ntfy_token"]:
        headers["Authorization"] = "Bearer " + settings["ntfy_token"]
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload, ensure_ascii=False).encode(),
        headers=headers,
        method="POST",
    )
    try:
        with _OPENER.open(request, timeout=TIMEOUT) as response:
            if not 200 <= response.status < 300:
                return False, f"HTTP {response.status}", None, response.status >= 500
            raw = response.read(65537)
            if len(raw) > 65536:
                return False, "invalid_response", None, True
            result = json.loads(raw)
            message_id = result.get("id")
            if (
                not isinstance(message_id, str)
                or not message_id
                or len(message_id) > 256
                or result.get("topic") != topic
                or result.get("event") != "message"
            ):
                return False, "invalid_response", None, True
            return True, None, message_id, False
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code}", None, exc.code in {408, 429} or exc.code >= 500
    except (ValueError, AttributeError, TypeError):
        return False, "invalid_response", None, True
    except (OSError, urllib.error.URLError):
        return False, "connection_error", None, True


def test_settings(user_id):
    settings = _private_settings(user_id)
    if not settings or not settings["ntfy_url"]:
        raise ValueError("Save an ntfy topic before sending a test")
    ok, error, _, _ = publish(
        settings,
        {
            "title": "Doction · Prueba de recordatorios",
            "message": "Los avisos de tus recordatorios llegarán a este topic.",
        },
    )
    if not ok:
        raise ValueError(f"ntfy test failed: {error}")
    return {"sent": True}


_DUE = "COALESCE(r.due_at, (r.due_date + s.date_only_time) AT TIME ZONE r.timezone)"
_ELIGIBLE = """r.status = 'pending' AND r.assignee_id = s.user_id AND s.enabled
    AND EXISTS (SELECT 1 FROM workspace_members m
                WHERE m.workspace_id = r.workspace_id AND m.user_id = r.assignee_id)"""


def enqueue(now, limit=100):
    with db.connect() as conn:
        conn.execute(
            "UPDATE reminder_notifications n SET status = 'cancelled' WHERE n.status = 'pending' "
            "AND NOT EXISTS (SELECT 1 FROM reminders r WHERE r.id = n.reminder_id "
            "AND r.status = 'pending' AND r.notification_generation = n.generation "
            "AND r.assignee_id = n.assignee_id AND EXISTS (SELECT 1 FROM workspace_members m "
            "WHERE m.workspace_id = r.workspace_id AND m.user_id = n.assignee_id))",
        )
        conn.execute(
            "INSERT INTO reminder_notifications "
            "(reminder_id, generation, assignee_id, next_attempt_at) "
            "SELECT r.id, r.notification_generation, r.assignee_id, %s FROM reminders r "
            "JOIN notification_settings s ON s.user_id = r.assignee_id WHERE "
            + _ELIGIBLE
            + " AND "
            + _DUE
            + " <= %s AND NOT EXISTS (SELECT 1 FROM reminder_notifications n "
            "WHERE n.reminder_id = r.id AND n.generation = r.notification_generation "
            "AND n.status <> 'cancelled') "
            "ORDER BY " + _DUE + ", r.id LIMIT %s ON CONFLICT (reminder_id, generation) "
            "DO UPDATE SET status = 'pending', attempts = 0, last_error = NULL, "
            "next_attempt_at = EXCLUDED.next_attempt_at "
            "WHERE reminder_notifications.status = 'cancelled'",
            (now, now, limit),
        )


def _message(conn, row):
    zone = reminders.ZoneInfo(row["timezone"])
    when = (
        row["due_at"].astimezone(zone).strftime("%Y-%m-%d %H:%M")
        if row["due_at"]
        else row["due_date"].isoformat()
    )
    lines = [
        row["title"],
        f"Workspace: {row['workspace_name']}",
        f"Fecha: {when} · {row['timezone']}",
    ]
    pages = conn.execute(
        "SELECT p.title FROM reminder_pages rp JOIN pages p ON p.id = rp.page_id "
        "WHERE rp.reminder_id = %s AND p.deleted_at IS NULL ORDER BY p.title LIMIT 10",
        (row["reminder_id"],),
    ).fetchall()
    if pages:
        lines.append("Documentos: " + ", ".join(p["title"] for p in pages))
    result = {"title": "Doction · Recordatorio", "message": "\n".join(lines), "tags": ["bell"]}
    base = os.environ.get("DOCTION_PUBLIC_URL", "").rstrip("/")
    parsed = urlsplit(base)
    if base and parsed.scheme in {"http", "https"} and parsed.netloc and not parsed.username:
        app_path = "/" + os.getenv("DOCTION_APP_PATH", "/app").strip("/")
        result["click"] = (
            base + app_path.rstrip("/") + "/w/" + quote(row["workspace"], safe="") + "/reminders"
        )
    return result


def process_one(notification_id, now):
    with db.connect() as conn:
        identity = conn.execute(
            "SELECT n.assignee_id, r.workspace_id FROM reminder_notifications n "
            "JOIN reminders r ON r.id = n.reminder_id WHERE n.id = %s AND n.status = 'pending'",
            (notification_id,),
        ).fetchone()
        if identity is None:
            return False
        # Same ordering for all workers and settings edits; busy workspaces wait for the next tick.
        if not conn.execute(
            "SELECT pg_try_advisory_xact_lock(%s, %s) AS acquired",
            (USER_LOCK, identity["assignee_id"]),
        ).fetchone()["acquired"]:
            return False
        if not conn.execute(
            "SELECT pg_try_advisory_xact_lock(%s) AS acquired", (identity["workspace_id"],)
        ).fetchone()["acquired"]:
            return False
        row = conn.execute(
            "SELECT n.id AS notification_id, n.reminder_id, n.attempts, r.*, "
            "s.ntfy_url, s.ntfy_token, w.slug AS workspace, w.name AS workspace_name "
            "FROM reminder_notifications n JOIN reminders r ON r.id = n.reminder_id "
            "JOIN notification_settings s ON s.user_id = n.assignee_id "
            "JOIN workspaces w ON w.id = r.workspace_id WHERE n.id = %s "
            "AND n.status = 'pending' AND n.next_attempt_at <= %s "
            "AND n.generation = r.notification_generation AND "
            + _ELIGIBLE
            + " AND "
            + _DUE
            + " <= %s FOR UPDATE OF n, r, s SKIP LOCKED",
            (notification_id, now, now),
        ).fetchone()
        if row is None:
            return False
        ok, error, message_id, retryable = publish(row, _message(conn, row))
        attempts = row["attempts"] + 1
        status = (
            "sent" if ok else ("pending" if retryable and attempts < MAX_ATTEMPTS else "failed")
        )
        retry_at = now + timedelta(seconds=min(30 * 2 ** (attempts - 1), 3600))
        conn.execute(
            "UPDATE reminder_notifications SET status = %s, attempts = %s, last_error = %s, "
            "delivered_at = %s, message_id = %s, next_attempt_at = %s WHERE id = %s",
            (status, attempts, error, now if ok else None, message_id, retry_at, notification_id),
        )
        logger.info(
            "reminder notification=%s status=%s attempts=%s", notification_id, status, attempts
        )
        return True


def drain_once(limit=20, stop=None):
    now = reminders.utc_now()
    enqueue(now)
    with db.connect() as conn:
        ids = conn.execute(
            "SELECT n.id FROM reminder_notifications n JOIN reminders r ON r.id = n.reminder_id "
            "JOIN notification_settings s ON s.user_id = n.assignee_id "
            "WHERE n.status = 'pending' AND n.generation = r.notification_generation AND "
            + _ELIGIBLE
            + " AND n.next_attempt_at <= %s AND "
            + _DUE
            + " <= %s "
            "ORDER BY n.next_attempt_at, n.id LIMIT %s",
            (now, now, limit),
        ).fetchall()
    processed = 0
    for row in ids:
        if stop is not None and stop.is_set():
            break
        processed += process_one(row["id"], now)
    return processed


def delivery_state(conn, row):
    settings = conn.execute(
        "SELECT enabled, date_only_time FROM notification_settings WHERE user_id = %s",
        (row["assignee_id"],),
    ).fetchone()
    delivery = conn.execute(
        "SELECT status, attempts, delivered_at, next_attempt_at, last_error "
        "FROM reminder_notifications "
        "WHERE reminder_id = %s AND generation = %s",
        (row["id"], row["notification_generation"]),
    ).fetchone()
    state = delivery["status"] if delivery else "scheduled"
    if row["status"] != "pending" and state != "sent":
        state = "cancelled"
    elif state != "sent" and (not settings or not settings["enabled"]):
        state = "disabled"
    return {
        "date_only_time": settings["date_only_time"].strftime("%H:%M") if settings else "09:00",
        "state": state,
        "attempts": delivery["attempts"] if delivery else 0,
        "delivered_at": delivery["delivered_at"].isoformat()
        if delivery and delivery["delivered_at"]
        else None,
        "next_attempt_at": delivery["next_attempt_at"].isoformat()
        if delivery and state == "pending"
        else None,
        "last_error": delivery["last_error"] if delivery else None,
    }


async def delivery_worker():
    stop = threading.Event()
    while True:
        task = asyncio.create_task(asyncio.to_thread(drain_once, stop=stop))
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            stop.set()
            # Persist the current HTTP attempt before the database pool closes.
            await task
            raise
        except Exception:
            # Exception text may contain a destination or credential; keep diagnostics fixed.
            logger.error("reminder notification worker failed; retrying next tick")
        await asyncio.sleep(INTERVAL)
