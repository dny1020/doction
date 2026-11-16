"""Reminder lifecycle, exact temporal queries, workspace isolation and document identity."""

from datetime import UTC, datetime

import pytest

from app import db, reminders
from tests.helpers import get_token, mcp_call, tool_data


def setup_user(client):
    token = get_token(client)
    ws = tool_data(mcp_call(client, token, "list_workspaces"))[0]["slug"]
    return token, ws


def create(client, token, ws, **extra):
    return mcp_call(
        client,
        token,
        "create_reminder",
        {
            "workspace": ws,
            "title": "Revisar backup",
            "due_date": "2026-11-17",
            **extra,
        },
    )


def listing(client, token, **extra):
    return tool_data(mcp_call(client, token, "list_reminders", extra))


def update(client, token, item, **extra):
    return mcp_call(
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


def test_reminder_lifecycle_reschedule_and_history(client):
    token, ws = setup_user(client)
    item = tool_data(create(client, token, ws))
    assert item["status"] == "pending" and item["revision"] == 1
    assert listing(client, token)["items"][0]["id"] == item["id"]
    item = tool_data(
        update(
            client,
            token,
            item,
            due_date=None,
            due_at="2026-11-18T09:00:00",
            timezone="America/Bogota",
        )
    )
    assert item["due_at"].startswith("2026-11-18T14:00:00")
    item = tool_data(update(client, token, item, status="completed"))
    assert listing(client, token)["total"] == 0
    assert listing(client, token, status="completed")["total"] == 1
    item = tool_data(update(client, token, item, status="pending"))
    item = tool_data(update(client, token, item, status="cancelled"))
    assert listing(client, token, status="cancelled")["items"][0]["id"] == item["id"]
    history = tool_data(
        mcp_call(
            client,
            token,
            "get_reminder_history",
            {
                "workspace": ws,
                "id": item["id"],
                "limit": 2,
            },
        )
    )
    assert [r["revision"] for r in history["items"]] == [5, 4]
    assert history["next_offset"] == 2
    first = tool_data(
        mcp_call(
            client,
            token,
            "get_reminder_history",
            {
                "workspace": ws,
                "id": item["id"],
                "offset": 4,
            },
        )
    )["items"][0]
    assert first["due_date"] == "2026-11-17" and first["status"] == "pending"


def test_idempotent_creation_and_conflicting_edits(client):
    token, ws = setup_user(client)
    item = tool_data(create(client, token, ws, idempotency_key="r:1"))
    revised = tool_data(update(client, token, item, title="Otro título"))
    assert tool_data(create(client, token, ws, idempotency_key="r:1")) == item
    conflict = create(client, token, ws, idempotency_key="r:1", title="Cambio")
    assert conflict["structuredContent"]["error"]["code"] == "CONFLICT"
    assert (
        update(client, token, item, status="completed")["structuredContent"]["error"]["code"]
        == "CONFLICT"
    )
    assert listing(client, token)["items"][0]["revision"] == revised["revision"]


def test_exact_date_queries_and_pagination(client, monkeypatch):
    token, ws = setup_user(client)
    monkeypatch.setattr(reminders, "utc_now", lambda: datetime(2026, 11, 16, 17, tzinfo=UTC))
    overdue = tool_data(create(client, token, ws, due_date="2026-11-15"))
    earlier = tool_data(create(client, token, ws, due_date=None, due_at="2026-11-16T09:00:00"))
    today = tool_data(create(client, token, ws, due_date="2026-11-16"))
    future = tool_data(create(client, token, ws))
    assert {i["id"] for i in listing(client, token, period="overdue")["items"]} == {
        overdue["id"],
        earlier["id"],
    }
    assert [i["id"] for i in listing(client, token, period="today")["items"]] == [today["id"]]
    assert [i["id"] for i in listing(client, token, period="upcoming")["items"]] == [future["id"]]
    result = listing(client, token, limit=2)
    assert result["total"] == 4 and result["next_offset"] == 2
    assert [i["id"] for i in result["items"]] == [overdue["id"], earlier["id"]]
    assert listing(client, token, limit=2, offset=2)["next_offset"] is None


def test_date_only_does_not_expire_before_local_day_ends(client, monkeypatch):
    token, ws = setup_user(client)
    tool_data(create(client, token, ws, due_date="2026-11-16"))
    monkeypatch.setattr(reminders, "utc_now", lambda: datetime(2026, 11, 17, 4, 59, tzinfo=UTC))
    assert listing(client, token, period="today")["total"] == 1
    monkeypatch.setattr(reminders, "utc_now", lambda: datetime(2026, 11, 17, 5, tzinfo=UTC))
    assert listing(client, token, period="overdue")["total"] == 1


@pytest.mark.parametrize(
    "fields",
    [
        {"due_date": None},
        {"due_at": "2026-11-16T09:00:00"},
        {"timezone": "Bogota"},
        {"due_date": None, "due_at": "2026-03-08T02:30:00", "timezone": "America/New_York"},
        {"due_date": None, "due_at": "2026-11-01T01:30:00", "timezone": "America/New_York"},
        {"title": "   "},
    ],
)
def test_invalid_schedules_do_not_create_records(client, fields):
    token, ws = setup_user(client)
    assert create(client, token, ws, **fields)["isError"]
    assert listing(client, token)["total"] == 0


def test_explicit_offset_disambiguates_dst():
    _, instant, _ = reminders.schedule(
        None, datetime.fromisoformat("2026-11-01T01:30:00-04:00"), "America/New_York"
    )
    assert instant == datetime(2026, 11, 1, 5, 30, tzinfo=UTC)


def test_document_links_survive_rename_and_trash(client):
    token, ws = setup_user(client)
    page = tool_data(
        mcp_call(client, token, "create_page", {"title": "Backup", "content": "Pasos"})
    )
    item = tool_data(create(client, token, ws, page_slugs=[page["slug"]]))
    tool_data(
        mcp_call(client, token, "rename_page", {"slug": page["slug"], "new_slug": "backup-actual"})
    )
    linked = listing(client, token, workspace=ws, page_slug="backup-actual")["items"][0]
    assert linked["pages"][0]["slug"] == "backup-actual"
    tool_data(mcp_call(client, token, "delete_page", {"slug": "backup-actual"}))
    linked = listing(client, token)["items"][0]
    assert linked["pages"][0]["deleted"]
    tool_data(update(client, token, linked, title="Revisión", page_slugs=["backup-actual"]))
    result = create(client, token, ws, page_slugs=["backup-actual"])
    assert result["isError"]
    assert listing(client, token)["total"] == 1
    assert item["pages"][0]["id"] == linked["pages"][0]["id"]


def test_bad_document_link_rolls_back_reminder_and_key(client):
    token, ws = setup_user(client)
    assert create(client, token, ws, page_slugs=["missing"], idempotency_key="rollback")["isError"]
    tool_data(create(client, token, ws, idempotency_key="rollback"))
    assert listing(client, token)["total"] == 1


def test_assignment_and_authorized_aggregate(client):
    token, ws = setup_user(client)
    owner = db.get_user_by_email("u@test.com")
    other_token = get_token(client, email="other@test.com")
    other = db.get_user_by_email("other@test.com")
    other_ws = tool_data(mcp_call(client, other_token, "list_workspaces"))[0]["slug"]
    assert create(client, token, ws, assignee_id=other.id)["isError"]
    workspace = db.get_workspace_by_slug(owner.id, ws)
    db.add_workspace_member(workspace.id, other.id)
    assigned = tool_data(create(client, token, ws, assignee_id=other.id))
    tool_data(create(client, other_token, other_ws))
    assert listing(client, token)["total"] == 0
    assert listing(client, token, scope="workspace")["items"][0]["id"] == assigned["id"]
    assert listing(client, other_token)["total"] == 2
    assert mcp_call(client, token, "list_reminders", {"workspace": other_ws})["isError"]


def test_restricted_tokens_cannot_write_or_cross_workspace(client):
    token, ws = setup_user(client)
    owner = db.get_user_by_email("u@test.com")
    second = db.create_workspace(owner.id, "Otro")
    item = tool_data(create(client, token, ws))
    tool_data(create(client, token, second))
    pat = client.post(
        "/api/tokens",
        json={
            "name": "reader",
            "policy": {
                "grants": [
                    {"workspace": ws, "actions": ["read"]},
                ]
            },
        },
        headers={"Authorization": f"Bearer {token}"},
    ).json()["token"]
    assert listing(client, pat)["total"] == 1
    assert create(client, pat, ws)["structuredContent"]["error"]["code"] == "FORBIDDEN"
    assert update(client, pat, item, status="completed")["isError"]
    headers = {"Authorization": f"Bearer {pat}"}
    assert client.get("/api/reminders", headers=headers).json()["total"] == 1
    assert (
        client.post(
            "/api/reminders?workspace=" + ws,
            headers=headers,
            json={
                "title": "No",
                "due_date": "2026-11-17",
            },
        ).status_code
        == 403
    )
    assert client.get("/api/reminders?workspace=" + second, headers=headers).status_code == 403


def test_rest_reminders_and_conflict(client):
    token, ws = setup_user(client)
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post(
        "/api/reminders?workspace=" + ws,
        headers=headers,
        json={
            "title": "Desde REST",
            "due_at": "2026-11-17T09:00:00",
            "timezone": "America/Bogota",
        },
    )
    assert response.status_code == 201, response.text
    item = response.json()
    assert (
        client.get(f"/api/reminders/{item['id']}/history?workspace={ws}", headers=headers).json()[
            "items"
        ][0]["title"]
        == "Desde REST"
    )
    route = f"/api/reminders/{item['id']}?workspace={ws}"
    assert (
        client.put(
            route, headers=headers, json={"expected_revision": 1, "status": "completed"}
        ).status_code
        == 200
    )
    assert (
        client.put(
            route, headers=headers, json={"expected_revision": 1, "status": "cancelled"}
        ).status_code
        == 409
    )
