"""Shared memory invariants: retries, concurrent writers, provenance and capabilities."""

from concurrent.futures import ThreadPoolExecutor

from app import db, git_repo
from tests.helpers import get_token, mcp_call, tool_data


def create(client, token, title="Servicio", content="# Servicio\n", **kwargs):
    return tool_data(
        mcp_call(
            client,
            token,
            "create_page",
            {
                "title": title,
                "content": content,
                **kwargs,
            },
        )
    )["slug"]


def test_concurrent_sections_preserve_every_writer(client):
    token = get_token(client)
    slug = create(client, token)
    ws = db.list_workspaces(db.get_user_by_email("u@test.com").id)[0]
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = [
            executor.submit(
                db.upsert_page_section, ws.user_id, ws.id, slug, f"Evento {i}", f"Resultado {i}"
            )
            for i in range(12)
        ]
        assert all(f.result() == slug for f in futures)
    page = db.get_page(slug, ws.id)
    assert all(f"Resultado {i}" in page.content for i in range(12))
    assert page.revision == 13


def test_idempotent_creation_conflicts_on_changed_payload(client):
    token = get_token(client)
    args = {"title": "Conversación", "content": "Hechos", "idempotency_key": "session:123"}
    first = tool_data(mcp_call(client, token, "create_page", args))
    assert tool_data(mcp_call(client, token, "create_page", args)) == first
    error = mcp_call(client, token, "create_page", {**args, "content": "Otros hechos"})
    assert error["isError"]
    assert error["structuredContent"]["error"]["code"] == "CONFLICT"


def test_revision_conflict_rest_and_mcp(client):
    token = get_token(client)
    slug = create(client, token)
    tool_data(
        mcp_call(
            client,
            token,
            "update_page",
            {
                "slug": slug,
                "content": "Nueva",
                "expected_revision": 1,
            },
        )
    )
    result = mcp_call(
        client,
        token,
        "update_page",
        {
            "slug": slug,
            "content": "Perdida",
            "expected_revision": 1,
        },
    )
    assert result["structuredContent"]["error"]["code"] == "CONFLICT"
    response = client.put(
        f"/api/pages/{slug}",
        json={
            "content": "Perdida",
            "expected_revision": 1,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 409
    assert tool_data(mcp_call(client, token, "get_page", {"slug": slug}))["content"] == "Nueva"


def test_relations_identity_archive_and_sections(client):
    token = get_token(client)
    service = create(client, token, content="---\ntype: Service\n---\nServicio")
    event = create(client, token, "Incidente", "## Primero\nViejo\n\n## Segundo\nReciente\n")
    related = tool_data(
        mcp_call(
            client,
            token,
            "relate_knowledge",
            {
                "slug": event,
                "target": service,
                "kind": "affects",
                "evidence": "Fallo comprobado",
            },
        )
    )
    assert len(related["relations"]) == 1
    assert (
        tool_data(
            mcp_call(
                client,
                token,
                "relate_knowledge",
                {
                    "slug": event,
                    "target": service,
                    "kind": "affects",
                },
            )
        )
        == related
    )
    tool_data(
        mcp_call(
            client,
            token,
            "set_knowledge_metadata",
            {
                "slug": event,
                "properties": {"type": "Incident", "source": "conversation:123"},
            },
        )
    )
    original = tool_data(mcp_call(client, token, "get_knowledge_object", {"slug": service}))
    tool_data(
        mcp_call(client, token, "add_entity_alias", {"slug": service, "alias": "Otro nombre"})
    )
    assert (
        tool_data(
            mcp_call(
                client,
                token,
                "get_knowledge_object",
                {
                    "slug": "otro-nombre",
                },
            )
        )["id"]
        == original["id"]
    )
    sections = tool_data(
        mcp_call(
            client,
            token,
            "read_page_sections",
            {
                "slug": event,
                "newest_first": True,
                "limit": 1,
            },
        )
    )
    assert sections["sections"][0]["text"] == "Reciente"
    assert sections["next_offset"] == 1
    tool_data(
        mcp_call(
            client,
            token,
            "set_knowledge_metadata",
            {
                "slug": event,
                "properties": {"status": "archived"},
            },
        )
    )
    assert (
        tool_data(
            mcp_call(
                client,
                token,
                "get_knowledge_object",
                {
                    "slug": event,
                },
            )
        )["properties"]["status"]
        == "archived"
    )


def restricted_token(client, token, grants):
    response = client.post(
        "/api/tokens",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "infra",
            "policy": {"grants": grants},
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["token"]


def test_token_permissions_apply_to_rest_and_mcp_even_with_session_cookie(client):
    token = get_token(client)
    slug = create(client, token)
    ws = tool_data(mcp_call(client, token, "list_workspaces"))[0]["slug"]
    limited = restricted_token(client, token, [{"workspace": ws, "actions": ["read"]}])
    assert tool_data(mcp_call(client, limited, "get_page", {"slug": slug}))["slug"] == slug
    assert (
        mcp_call(
            client,
            limited,
            "update_page",
            {
                "slug": slug,
                "content": "forbidden",
            },
        )["structuredContent"]["error"]["code"]
        == "FORBIDDEN"
    )
    headers = {"Authorization": f"Bearer {limited}"}
    assert (
        client.put(f"/api/pages/{slug}", json={"content": "forbidden"}, headers=headers).status_code
        == 403
    )
    assert client.post("/api/tokens", json={"name": "escape"}, headers=headers).status_code == 403
    assert (
        client.post(
            "/api/knowledge/set_knowledge_metadata",
            json={
                "slug": slug,
                "properties": {"status": "archived"},
            },
            headers=headers,
        ).status_code
        == 403
    )


def test_page_write_grants_do_not_allow_other_pages(client):
    token = get_token(client)
    inbox = create(client, token, "Inbox")
    other = create(client, token, "Proyecto")
    ws = tool_data(mcp_call(client, token, "list_workspaces"))[0]["slug"]
    limited = restricted_token(
        client,
        token,
        [
            {"workspace": ws, "actions": ["read"]},
            {"workspace": ws, "actions": ["update"], "pages": [inbox]},
        ],
    )
    tool_data(
        mcp_call(
            client,
            limited,
            "upsert_page_section",
            {
                "slug": inbox,
                "heading": "Nota",
                "body": "Permitida",
            },
        )
    )
    assert mcp_call(
        client,
        limited,
        "upsert_page_section",
        {
            "slug": other,
            "heading": "Nota",
            "body": "No permitida",
        },
    )["isError"]
    with db.connect() as conn:
        row = conn.execute(
            "SELECT actor FROM knowledge_revisions WHERE content LIKE %s "
            "ORDER BY revision DESC LIMIT 1",
            ("%Permitida%",),
        ).fetchone()
    assert row["actor"].startswith("token:")


def test_git_failure_is_pending_and_retryable(client, monkeypatch):
    token = get_token(client)
    original = git_repo.commit_page
    monkeypatch.setattr(git_repo, "commit_page", lambda *a, **kw: None)
    slug = create(client, token)
    assert tool_data(mcp_call(client, token, "get_page", {"slug": slug}))["git_status"] == "pending"
    monkeypatch.setattr(git_repo, "commit_page", original)
    assert (
        tool_data(
            mcp_call(
                client,
                token,
                "retry_page_version",
                {
                    "slug": slug,
                },
            )
        )["git_status"]
        == "synced"
    )


def test_context_filters_archive_type_and_relation(client):
    token = get_token(client)
    service = create(client, token)
    active = create(client, token, "Actual", "Certbot renovación actual")
    old = create(client, token, "Vieja", "Certbot renovación obsoleta")
    for slug, status in [(active, "active"), (old, "archived")]:
        tool_data(
            mcp_call(
                client,
                token,
                "set_knowledge_metadata",
                {
                    "slug": slug,
                    "properties": {"type": "Runbook", "status": status},
                },
            )
        )
        tool_data(
            mcp_call(
                client,
                token,
                "relate_knowledge",
                {
                    "slug": slug,
                    "target": service,
                    "kind": "affects",
                },
            )
        )
    result = tool_data(
        mcp_call(
            client,
            token,
            "query_knowledge_context",
            {
                "query": "certbot",
                "type": "Runbook",
                "entity": service,
                "budget": 1000,
            },
        )
    )
    assert {chunk["slug"] for chunk in result["chunks"]} == {active}
    assert sum(len(c["text"]) for c in result["chunks"]) <= 1000


def test_idempotent_concurrent_creates_and_durable_history(client):
    token = get_token(client)
    user = db.get_user_by_email("u@test.com")
    ws = db.list_workspaces(user.id)[0]
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [
            executor.submit(
                db.create_page,
                user.id,
                ws.id,
                "Evento",
                "Una sola fuente",
                idempotency_key="event:concurrent",
            )
            for _ in range(8)
        ]
        slugs = {f.result() for f in futures}
    assert len(slugs) == 1
    slug = slugs.pop()
    tool_data(
        mcp_call(
            client,
            token,
            "update_page",
            {
                "slug": slug,
                "content": "Evidencia actualizada",
                "expected_revision": 1,
            },
        )
    )
    history = tool_data(
        mcp_call(
            client,
            token,
            "get_knowledge_history",
            {
                "slug": slug,
                "limit": 1,
            },
        )
    )
    assert history["next_offset"] == 1
    assert history["revisions"][0]["revision"] == 2
    assert history["revisions"][0]["markdown"] == "Evidencia actualizada"
    previous = tool_data(
        mcp_call(
            client,
            token,
            "get_knowledge_history",
            {
                "slug": slug,
                "offset": 1,
            },
        )
    )
    assert previous["revisions"][0]["markdown"] == "Una sola fuente"


def test_context_filters_before_candidate_limit_and_across_workspaces(client):
    token = get_token(client)
    user = db.get_user_by_email("u@test.com")
    ws = db.list_workspaces(user.id)[0]
    second = db.create_workspace(user.id, "Segundo")
    for i in range(25):
        db.create_page(
            user.id,
            ws.id,
            f"Viejo {i}",
            "---\ntype: Runbook\nstatus: archived\n---\nCertbot certbot certbot antiguo",
        )
    wanted = db.create_page(user.id, ws.id, "Actual", "---\ntype: Runbook\n---\nCertbot vigente")
    second_ws = db.get_workspace_by_slug(user.id, second)
    other = db.create_page(
        user.id, second_ws.id, "Otro", "---\ntype: Runbook\n---\nCertbot externo"
    )
    result = tool_data(
        mcp_call(
            client,
            token,
            "query_knowledge_context",
            {
                "query": "certbot",
                "type": "Runbook",
                "budget": 2000,
                "workspaces": [ws.slug, second],
            },
        )
    )
    assert {(c["workspace"], c["slug"]) for c in result["chunks"]} == {
        (ws.slug, wanted),
        (second, other),
    }
    assert all(c["revision"] == 1 for c in result["chunks"])
    assert all(c["text"] for c in result["chunks"])


def test_type_filter_and_metadata_round_trip(client):
    token = get_token(client)
    project = create(client, token, "Proyecto", "---\ntype: Project\n---\nProyecto")
    slug = create(client, token, "Decisión", "Certbot seleccionado")
    tool_data(
        mcp_call(
            client,
            token,
            "relate_knowledge",
            {"slug": slug, "target": project, "kind": "belongs_to"},
        )
    )
    source = '"Evidencia" de Danilo \\ original'
    obj = tool_data(
        mcp_call(
            client,
            token,
            "set_knowledge_metadata",
            {
                "slug": slug,
                "properties": {"type": "Decision", "source": source},
            },
        )
    )
    assert obj["properties"]["source"] == source
    assert [
        r["slug"]
        for r in tool_data(
            mcp_call(
                client,
                token,
                "search_knowledge",
                {
                    "query": "certbot",
                    "type": "Decision",
                },
            )
        )
    ] == [slug]
    assert (
        tool_data(
            mcp_call(
                client,
                token,
                "search_knowledge",
                {
                    "query": "certbot",
                    "type": "Incident",
                },
            )
        )
        == []
    )


def test_temporal_filter_normalizes_timezone_offsets(client):
    token = get_token(client)
    slug = create(client, token, "Temporal", "Certbot vigente")
    tool_data(
        mcp_call(
            client,
            token,
            "set_knowledge_metadata",
            {
                "slug": slug,
                "properties": {
                    "valid_from": "2026-11-16T12:00:00+02:00",
                    "valid_until": "2026-11-16T12:00:00Z",
                },
            },
        )
    )
    result = tool_data(
        mcp_call(
            client,
            token,
            "query_knowledge_context",
            {
                "query": "certbot",
                "as_of": "2026-11-16T10:30:00Z",
            },
        )
    )
    assert [c["slug"] for c in result["chunks"]] == [slug]
    assert (
        tool_data(
            mcp_call(
                client,
                token,
                "query_knowledge_context",
                {
                    "query": "certbot",
                    "as_of": "2026-11-16T09:00:00Z",
                },
            )
        )["chunks"]
        == []
    )


def test_empty_grants_and_workspace_membership_cannot_be_bypassed(client):
    token = get_token(client)
    slug = create(client, token)
    empty = restricted_token(client, token, [])
    assert tool_data(mcp_call(client, empty, "list_workspaces")) == []
    assert mcp_call(client, empty, "get_page", {"slug": slug})["isError"]
    assert client.get("/api/pages", headers={"Authorization": f"Bearer {empty}"}).status_code == 403
    other = get_token(client, email="other@test.com")
    other_ws = tool_data(mcp_call(client, other, "list_workspaces"))[0]["slug"]
    limited = restricted_token(client, token, [{"workspace": other_ws, "actions": ["read"]}])
    assert mcp_call(
        client,
        limited,
        "get_page",
        {
            "slug": slug,
            "workspace": other_ws,
        },
    )["isError"]
