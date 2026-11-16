"""Graph contracts must survive retries, edits and deletion through either interface."""

import pytest

from app import db
from tests.helpers import get_token, mcp_call, tool_data


def create(client, token, title, kind=None, **extra):
    content = f"---\ntype: {kind}\n---\n{title}" if kind else title
    return mcp_call(client, token, "create_page", {"title": title, "content": content, **extra})


def error_code(result):
    assert result["isError"], result
    return result["structuredContent"]["error"]["code"]


@pytest.mark.parametrize("kind", ["Decision", "decision", "Incident", "incident"])
def test_required_relation_is_enforced_and_failure_is_atomic(client, kind):
    token = get_token(client)
    result = create(client, token, "Incompleto", kind)
    assert error_code(result) == "RELATION_REQUIRED"
    with db.connect() as conn:
        assert conn.execute("SELECT id FROM pages WHERE slug = 'incompleto'").fetchone() is None
    assert "relations" in result["content"][0]["text"]


def test_atomic_relations_and_retry_are_available_on_rest_and_mcp(client):
    token = get_token(client)
    project = tool_data(create(client, token, "Proyecto", "Project"))["slug"]
    service = tool_data(create(client, token, "Servicio", "Service"))["slug"]
    args = {"relations": [{"kind": "belongs_to", "target": project}], "idempotency_key": "d:1"}
    result = tool_data(create(client, token, "Decisión", "Decision", **args))
    assert tool_data(create(client, token, "Decisión", "Decision", **args)) == result
    read = tool_data(mcp_call(client, token, "get_page", {"slug": result["slug"]}))
    assert read["graph_context"]["enforced"]
    assert read["graph_context"]["relations"][0]["target"] == project
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post(
        "/api/pages",
        headers=headers,
        json={
            "title": "Incidente",
            "content": "---\ntype: Incident\n---\nFallo",
            "relations": [{"kind": "affects", "target": service, "evidence": "Logs"}],
        },
    )
    assert response.status_code == 201, response.text
    page = client.get(f"/api/pages/{response.json()['slug']}", headers=headers).json()
    assert page["graph_context"]["required_relation"] == {
        "kind": "affects",
        "target_type": "Service",
    }
    assert "query_knowledge_context" in page["graph_context"]["guidance"]


def test_wrong_target_type_and_parenting_do_not_satisfy_contract(client):
    token = get_token(client)
    project = tool_data(create(client, token, "Proyecto", "Project"))["slug"]
    assert (
        error_code(
            create(
                client,
                token,
                "Incidente",
                "Incident",
                relations=[
                    {
                        "kind": "affects",
                        "target": project,
                    }
                ],
            )
        )
        == "RELATION_REQUIRED"
    )
    assert (
        error_code(
            create(
                client,
                token,
                "Decisión",
                "Decision",
                parent_slug=project,
                content=f"---\ntype: Decision\n---\n[[{project}]]",
            )
        )
        == "RELATION_REQUIRED"
    )


def test_legacy_pages_remain_editable_and_promotion_is_checked(client):
    token = get_token(client)
    legacy = tool_data(create(client, token, "Antigua"))["slug"]
    # Simulate a typed page that existed before this schema change.
    with db.connect() as conn:
        conn.execute(
            "UPDATE pages SET content = %s, graph_required = FALSE WHERE slug = %s",
            ("---\ntype: Decision\n---\nDecisión antigua", legacy),
        )
    tool_data(
        mcp_call(
            client,
            token,
            "update_page",
            {
                "slug": legacy,
                "content": "---\ntype: Decision\n---\nEdición compatible",
            },
        )
    )
    assert not tool_data(
        mcp_call(
            client,
            token,
            "get_page",
            {
                "slug": legacy,
            },
        )
    )["graph_context"]["enforced"]
    new = tool_data(create(client, token, "Nueva"))["slug"]
    result = mcp_call(
        client,
        token,
        "set_knowledge_metadata",
        {
            "slug": new,
            "properties": {"type": "Decision"},
        },
    )
    assert error_code(result) == "RELATION_REQUIRED"
    project = tool_data(create(client, token, "Proyecto", "Project"))["slug"]
    tool_data(
        mcp_call(
            client,
            token,
            "relate_knowledge",
            {
                "slug": new,
                "kind": "belongs_to",
                "target": project,
            },
        )
    )
    promoted = tool_data(
        mcp_call(
            client,
            token,
            "set_knowledge_metadata",
            {
                "slug": new,
                "properties": {"type": "Decision"},
            },
        )
    )
    assert promoted["graph_context"]["enforced"]


def test_required_relation_cannot_be_broken_by_removal_retyping_or_trash(client):
    token = get_token(client)
    project = tool_data(create(client, token, "Proyecto", "Project"))["slug"]
    decision = tool_data(
        create(
            client,
            token,
            "Decisión",
            "Decision",
            relations=[
                {
                    "kind": "belongs_to",
                    "target": project,
                }
            ],
        )
    )["slug"]
    obj = tool_data(mcp_call(client, token, "get_knowledge_object", {"slug": decision}))
    edge_id = obj["relations"][0]["id"]
    assert (
        error_code(
            mcp_call(
                client,
                token,
                "remove_knowledge_relation",
                {
                    "slug": decision,
                    "relation_id": edge_id,
                },
            )
        )
        == "RELATION_REQUIRED"
    )
    assert (
        error_code(
            mcp_call(
                client,
                token,
                "update_page",
                {
                    "slug": project,
                    "content": "---\ntype: Service\n---\nAhora un servicio",
                },
            )
        )
        == "RELATION_REQUIRED"
    )
    assert (
        error_code(mcp_call(client, token, "delete_page", {"slug": project})) == "RELATION_REQUIRED"
    )
    response = client.delete(f"/api/pages/{project}", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 400
    assert response.json()["code"] == "RELATION_REQUIRED"
    assert (
        tool_data(
            mcp_call(
                client,
                token,
                "get_knowledge_object",
                {
                    "slug": decision,
                },
            )
        )["relations"][0]["id"]
        == edge_id
    )


def test_missing_target_rolls_back_all_edges_and_idempotency_key(client):
    token = get_token(client)
    project = tool_data(create(client, token, "Proyecto", "Project"))["slug"]
    extra = {
        "idempotency_key": "retry:atomic",
        "relations": [
            {"kind": "belongs_to", "target": project},
            {"kind": "related_to", "target": "missing"},
        ],
    }
    assert error_code(create(client, token, "Decisión", "Decision", **extra)) == "NOT_FOUND"
    tool_data(
        create(
            client,
            token,
            "Decisión",
            "Decision",
            idempotency_key="retry:atomic",
            relations=[{"kind": "belongs_to", "target": project}],
        )
    )
    with db.connect() as conn:
        assert conn.execute("SELECT count(*) AS n FROM knowledge_relations").fetchone()["n"] == 1


def test_atomic_create_checks_relate_permission_and_plain_pages_remain_free(client):
    token = get_token(client)
    project = tool_data(create(client, token, "Proyecto", "Project"))["slug"]
    ws = tool_data(mcp_call(client, token, "list_workspaces"))[0]["slug"]
    limited = client.post(
        "/api/tokens",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "creator",
            "policy": {"grants": [{"workspace": ws, "actions": ["read", "create"]}]},
        },
    ).json()["token"]
    assert (
        error_code(
            create(
                client,
                limited,
                "Decisión",
                "Decision",
                relations=[
                    {
                        "kind": "belongs_to",
                        "target": project,
                    }
                ],
            )
        )
        == "FORBIDDEN"
    )
    response = client.post(
        "/api/pages",
        headers={"Authorization": f"Bearer {limited}"},
        json={
            "title": "REST forbidden",
            "content": "---\ntype: Decision\n---\nNo permiso",
            "relations": [{"kind": "belongs_to", "target": project}],
        },
    )
    assert response.status_code == 403
    assert tool_data(create(client, limited, "Nota libre"))["slug"] == "nota-libre"
    assert (
        tool_data(create(client, limited, "Subpágina", parent_slug=project))["slug"] == "subpagina"
    )


def test_tool_instructions_explain_the_contract(client):
    def rpc(method):
        return client.post("/api/mcp", json={"jsonrpc": "2.0", "id": 1, "method": method}).json()[
            "result"
        ]

    assert "belongs_to -> Project" in rpc("initialize")["instructions"]
    tools = {t["name"]: t for t in rpc("tools/list")["tools"]}
    assert "atomically" in tools["create_page"]["description"]
    assert "relations" in tools["create_page"]["inputSchema"]["properties"]
    assert "graph_context" in tools["get_page"]["description"]


def test_replace_required_target_then_restore_checks_contract(client):
    token = get_token(client)
    old = tool_data(create(client, token, "Anterior", "Project"))["slug"]
    new = tool_data(create(client, token, "Nuevo", "Project"))["slug"]
    decision = tool_data(
        create(
            client, token, "Decisión", "Decision", relations=[{"kind": "belongs_to", "target": old}]
        )
    )["slug"]
    edges = tool_data(
        mcp_call(
            client,
            token,
            "relate_knowledge",
            {"slug": decision, "kind": "belongs_to", "target": new},
        )
    )["relations"]
    old_edge = next(edge for edge in edges if edge["target"] == old)
    tool_data(
        mcp_call(
            client,
            token,
            "remove_knowledge_relation",
            {"slug": decision, "relation_id": old_edge["id"]},
        )
    )
    tool_data(mcp_call(client, token, "delete_page", {"slug": old}))
    tool_data(mcp_call(client, token, "delete_page", {"slug": decision}))
    tool_data(mcp_call(client, token, "delete_page", {"slug": new}))
    ws = db.list_workspaces(db.get_user_by_email("u@test.com").id)[0]
    with pytest.raises(db.RelationRequired):
        db.restore_page(ws.id, decision)
    assert db.get_page(decision, ws.id) is None
    assert db.restore_page(ws.id, new)
    assert db.restore_page(ws.id, decision)


def test_atomic_relations_cannot_cross_workspaces(client):
    token = get_token(client)
    user = db.get_user_by_email("u@test.com")
    other = db.create_workspace(user.id, "Otro")
    project = tool_data(
        mcp_call(
            client,
            token,
            "create_page",
            {"workspace": other, "title": "Remoto", "content": "---\ntype: Project\n---\nOtro"},
        )
    )["slug"]
    assert (
        error_code(
            create(
                client,
                token,
                "Decisión",
                "Decision",
                relations=[{"kind": "belongs_to", "target": project}],
            )
        )
        == "NOT_FOUND"
    )
