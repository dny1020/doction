"""Workspace reminders: exact date queries, document links and shared REST/MCP behavior."""

import hashlib
import json
from datetime import UTC, date, datetime
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field

from app import access, db


class Create(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=200)
    notes: str = Field(default="", max_length=20000)
    due_date: date | None = None
    due_at: datetime | None = None
    timezone: str = "America/Bogota"
    assignee_id: int | None = Field(default=None, gt=0)
    page_slugs: list[str] = Field(default_factory=list, max_length=50)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=200)


class Patch(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    expected_revision: int = Field(gt=0)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    notes: str | None = Field(default=None, max_length=20000)
    due_date: date | None = None
    due_at: datetime | None = None
    timezone: str | None = None
    assignee_id: int | None = Field(default=None, gt=0)
    page_slugs: list[str] | None = Field(default=None, max_length=50)
    status: Literal["pending", "completed", "cancelled"] | None = None


def utc_now():
    return datetime.now(UTC)


def schedule(due_date, due_at, timezone):
    try:
        zone = ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError, TypeError) as exc:
        raise ValueError("Use an IANA timezone such as America/Bogota") from exc
    if (due_date is None) == (due_at is None):
        raise ValueError("Provide exactly one of due_date or due_at")
    if due_at is None:
        return due_date, None, zone
    if due_at.tzinfo is None:
        # Reject clock gaps and repeated hours rather than silently choosing a time.
        candidates = {
            due_at.replace(tzinfo=zone, fold=fold).astimezone(UTC)
            for fold in (0, 1)
            if due_at.replace(tzinfo=zone, fold=fold)
            .astimezone(UTC)
            .astimezone(zone)
            .replace(tzinfo=None)
            == due_at
        }
        if len(candidates) != 1:
            raise ValueError("Ambiguous or nonexistent local time; provide an explicit UTC offset")
        due_at = candidates.pop()
    return None, due_at.astimezone(UTC), zone


def workspace(user_id, slug, action):
    ws = db.get_workspace_by_slug(user_id, slug) if slug else db.ensure_default_workspace(user_id)
    if ws is None:
        raise ValueError("Workspace not found")
    access.require(ws.slug, action)
    if action != "read":
        access.require(ws.slug, "read")
    return ws


def assign(conn, workspace_id, user_id):
    row = conn.execute(
        "SELECT 1 FROM workspace_members WHERE workspace_id = %s AND user_id = %s",
        (workspace_id, user_id),
    ).fetchone()
    if row is None:
        raise ValueError("The responsible person must be a member of the workspace")


def link_pages(conn, reminder_id, workspace_id, slugs):
    page_ids = set()
    for slug in slugs:
        if not isinstance(slug, str) or not slug.strip():
            raise ValueError("Document slugs must be nonempty strings")
        page = db.get_page(slug, workspace_id)
        if page is None:
            previous = conn.execute(
                "SELECT p.id FROM pages p JOIN reminder_pages rp ON rp.page_id = p.id "
                "WHERE rp.reminder_id = %s AND p.workspace_id = %s AND p.slug = %s",
                (reminder_id, workspace_id, slug),
            ).fetchone()
            if previous is None:
                raise ValueError(f"Page not found: {slug}")
            page_ids.add(previous["id"])
        else:
            page_ids.add(page.id)
    conn.execute("DELETE FROM reminder_pages WHERE reminder_id = %s", (reminder_id,))
    for page_id in sorted(page_ids):
        conn.execute(
            "INSERT INTO reminder_pages (reminder_id, page_id) VALUES (%s, %s)",
            (reminder_id, page_id),
        )


def serialize(conn, row, now=None):
    now = now or utc_now()
    zone = ZoneInfo(row["timezone"])
    instant = row["due_at"]
    local_day = instant.astimezone(zone).date() if instant else row["due_date"]
    overdue = instant < now if instant else local_day < now.astimezone(zone).date()
    bucket = (
        "overdue"
        if overdue
        else ("today" if local_day == now.astimezone(zone).date() else "upcoming")
    )
    pages = conn.execute(
        "SELECT p.id, p.slug, p.title, p.deleted_at IS NOT NULL AS deleted FROM reminder_pages rp "
        "JOIN pages p ON p.id = rp.page_id WHERE rp.reminder_id = %s ORDER BY p.title, p.id",
        (row["id"],),
    ).fetchall()
    from app.reminder_notifications import delivery_state

    return {
        "notification": delivery_state(conn, row),
        "id": row["id"],
        "workspace": row["workspace"],
        "workspace_name": row["workspace_name"],
        "title": row["title"],
        "notes": row["notes"],
        "status": row["status"],
        "due_date": row["due_date"].isoformat() if row["due_date"] else None,
        "due_at": instant.isoformat() if instant else None,
        "timezone": row["timezone"],
        "assignee_id": row["assignee_id"],
        "assignee_name": row["assignee_name"],
        "revision": row["revision"],
        "created_at": row["created_at"].isoformat(),
        "updated_at": row["updated_at"].isoformat(),
        "actor": row["actor"],
        "bucket": bucket if row["status"] == "pending" else "closed",
        "pages": pages,
    }


_SELECT = """SELECT r.*, w.slug AS workspace, w.name AS workspace_name,
    COALESCE(u.display_name, u.email) AS assignee_name FROM reminders r
    JOIN workspaces w ON w.id = r.workspace_id LEFT JOIN users u ON u.id = r.assignee_id"""


def create(user_id, args):
    args = dict(args)
    ws = workspace(user_id, args.pop("workspace", None), "create")
    body = Create.model_validate(args)
    due_date, due_at, _ = schedule(body.due_date, body.due_at, body.timezone)
    assignee = body.assignee_id or user_id
    canonical = {
        **body.model_dump(mode="json", exclude={"idempotency_key"}),
        "assignee_id": assignee,
        "due_at": due_at.isoformat() if due_at else None,
        "page_slugs": sorted(set(body.page_slugs)),
    }
    fingerprint = hashlib.sha256(json.dumps(canonical, sort_keys=True).encode()).hexdigest()
    with db.connect() as conn:
        conn.execute("SELECT pg_advisory_xact_lock(%s)", (int(ws.id),))
        assign(conn, ws.id, assignee)
        if body.idempotency_key:
            old = conn.execute(
                "SELECT id, request_hash FROM reminders WHERE workspace_id = %s "
                "AND idempotency_key = %s",
                (ws.id, body.idempotency_key),
            ).fetchone()
            if old:
                if old["request_hash"] != fingerprint:
                    raise db.RevisionConflict("Idempotency key already used for another reminder")
                first = conn.execute(
                    "SELECT payload_json FROM reminder_revisions "
                    "WHERE reminder_id = %s ORDER BY revision LIMIT 1",
                    (old["id"],),
                ).fetchone()
                return json.loads(first["payload_json"])
        row = conn.execute(
            "INSERT INTO reminders (workspace_id, title, notes, due_date, due_at, timezone, "
            "assignee_id, created_by, actor, idempotency_key, request_hash) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
            (
                ws.id,
                body.title,
                body.notes,
                due_date,
                due_at,
                body.timezone,
                assignee,
                user_id,
                access.actor.get() or f"user:{user_id}",
                body.idempotency_key,
                fingerprint,
            ),
        ).fetchone()
        link_pages(conn, row["id"], ws.id, body.page_slugs)
        db.emit_event(
            conn, ws.id, "reminder.created", {"reminder": {"id": row["id"], "title": body.title}}
        )
        return snapshot(
            conn,
            serialize(conn, conn.execute(_SELECT + " WHERE r.id = %s", (row["id"],)).fetchone()),
        )


def update(user_id, args):
    args = dict(args)
    reminder_id = int(args.pop("id"))
    ws = workspace(user_id, args.pop("workspace", None), "update")
    body = Patch.model_validate(args)
    patch = body.model_dump(exclude_unset=True, exclude={"expected_revision"})
    for field, value in patch.items():
        if value is None and field not in {"due_date", "due_at"}:
            raise ValueError(f"{field} cannot be null")
    with db.connect() as conn:
        conn.execute("SELECT pg_advisory_xact_lock(%s)", (int(ws.id),))
        old = conn.execute(
            "SELECT * FROM reminders WHERE id = %s AND workspace_id = %s FOR UPDATE",
            (reminder_id, ws.id),
        ).fetchone()
        if old is None:
            raise ValueError("Reminder not found")
        if body.expected_revision != old["revision"]:
            raise db.RevisionConflict("Reminder changed: reload it before updating")
        values = {**old, **patch}
        due_date, due_at, _ = schedule(values["due_date"], values["due_at"], values["timezone"])
        if "assignee_id" in patch:
            assign(conn, ws.id, body.assignee_id)
        rearm = (due_date, due_at, values["timezone"], values["assignee_id"]) != (
            old["due_date"],
            old["due_at"],
            old["timezone"],
            old["assignee_id"],
        ) or (old["status"] != "pending" and values["status"] == "pending")
        generation = old["notification_generation"] + int(rearm)
        if rearm or values["status"] != "pending":
            conn.execute(
                "UPDATE reminder_notifications SET status = 'cancelled' "
                "WHERE reminder_id = %s AND status = 'pending'",
                (reminder_id,),
            )
        conn.execute(
            "UPDATE reminders SET title = %s, notes = %s, due_date = %s, due_at = %s, "
            "timezone = %s, "
            "assignee_id = %s, status = %s, revision = revision + 1, "
            "updated_at = NOW(), actor = %s, notification_generation = %s "
            "WHERE id = %s",
            (
                values["title"],
                values["notes"],
                due_date,
                due_at,
                values["timezone"],
                values["assignee_id"],
                values["status"],
                access.actor.get() or f"user:{user_id}",
                generation,
                reminder_id,
            ),
        )
        if "page_slugs" in patch:
            link_pages(conn, reminder_id, ws.id, body.page_slugs)
        db.emit_event(conn, ws.id, "reminder.updated", {"reminder": {"id": reminder_id}})
        return snapshot(
            conn,
            serialize(conn, conn.execute(_SELECT + " WHERE r.id = %s", (reminder_id,)).fetchone()),
        )


def list_items(user_id, args):
    status = args.get("status", "pending")
    period = args.get("period", "all")
    scope = args.get("scope", "mine")
    if status not in {"pending", "completed", "cancelled", "all"}:
        raise ValueError("Invalid reminder status")
    if period not in {"overdue", "today", "upcoming", "all"} or scope not in {"mine", "workspace"}:
        raise ValueError("Invalid reminder period or scope")
    limit, offset = int(args.get("limit", 50)), int(args.get("offset", 0))
    if not 1 <= limit <= 100 or offset < 0:
        raise ValueError("Use limit 1..100 and a nonnegative offset")
    slug = args.get("workspace")
    if slug and slug != "all":
        workspaces = [workspace(user_id, slug, "read")]
    else:
        workspaces = [w for w in db.list_workspaces(user_id) if access.allowed(w.slug, "read")]
    workspace_ids = [w.id for w in workspaces]
    now = utc_now()
    where = " WHERE r.workspace_id = ANY(%s)"
    params = [workspace_ids]
    if status != "all":
        where += " AND r.status = %s"
        params.append(status)
    if scope == "mine":
        where += " AND r.assignee_id = %s"
        params.append(user_id)
    if args.get("page_slug"):
        if len(workspaces) != 1:
            raise ValueError("Select one workspace when filtering by document")
        page = db.get_page(args["page_slug"], workspaces[0].id)
        if page is None:
            raise ValueError("Page not found")
        where += (
            " AND EXISTS (SELECT 1 FROM reminder_pages rp "
            "WHERE rp.reminder_id = r.id AND rp.page_id = %s)"
        )
        params.append(page.id)
    overdue = (
        "CASE WHEN r.due_at IS NOT NULL THEN r.due_at < %s "
        "ELSE r.due_date < (%s AT TIME ZONE r.timezone)::date END"
    )
    today = (
        "COALESCE((r.due_at AT TIME ZONE r.timezone)::date, r.due_date) "
        "= (%s AT TIME ZONE r.timezone)::date"
    )
    if period != "all":
        where += " AND r.status = 'pending' AND "
        if period == "overdue":
            where += "(" + overdue + ")"
            params += [now, now]
        else:
            where += (
                "NOT (" + overdue + ") AND " + ("(" if period == "today" else "NOT (") + today + ")"
            )
            params += [now, now, now]
    order = (
        " ORDER BY COALESCE(r.due_at, (r.due_date + 1)::timestamp "
        "AT TIME ZONE r.timezone), r.id LIMIT %s OFFSET %s"
    )
    with db.connect() as conn:
        total = conn.execute("SELECT count(*) AS n FROM reminders r" + where, params).fetchone()[
            "n"
        ]
        rows = conn.execute(_SELECT + where + order, [*params, limit, offset]).fetchall()
        items = [serialize(conn, row, now) for row in rows]
    return {
        "items": items,
        "total": total,
        "next_offset": offset + limit if offset + limit < total else None,
        "now": now.isoformat(),
    }


def snapshot(conn, item):
    conn.execute(
        "INSERT INTO reminder_revisions (reminder_id, revision, payload_json) VALUES (%s, %s, %s)",
        (item["id"], item["revision"], json.dumps(item, ensure_ascii=False)),
    )
    return item


def history(user_id, args):
    ws = workspace(user_id, args.get("workspace"), "read")
    limit, offset = int(args.get("limit", 20)), int(args.get("offset", 0))
    if not 1 <= limit <= 100 or offset < 0:
        raise ValueError("Use limit 1..100 and a nonnegative offset")
    reminder_id = int(args["id"])
    with db.connect() as conn:
        exists = conn.execute(
            "SELECT 1 FROM reminders WHERE id = %s AND workspace_id = %s", (reminder_id, ws.id)
        ).fetchone()
        if exists is None:
            raise ValueError("Reminder not found")
        rows = conn.execute(
            "SELECT payload_json FROM reminder_revisions WHERE reminder_id = %s "
            "ORDER BY revision DESC LIMIT %s OFFSET %s",
            (reminder_id, limit + 1, offset),
        ).fetchall()
    return {
        "items": [json.loads(row["payload_json"]) for row in rows[:limit]],
        "next_offset": offset + limit if len(rows) > limit else None,
    }


HANDLERS = {
    "create_reminder": create,
    "list_reminders": list_items,
    "update_reminder": update,
    "get_reminder_history": history,
}
