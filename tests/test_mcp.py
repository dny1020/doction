"""Tests for the native MCP endpoint (JSON-RPC 2.0 over POST /api/mcp)."""

from app.meta import extract_links
from tests.helpers import get_token, mcp_call, tool_data


def _rpc(
    client,
    method: str,
    params: dict | None = None,
    *,
    token: str | None = None,
    msg_id: int | None = 1,
):
    msg: dict = {"jsonrpc": "2.0", "method": method}
    if msg_id is not None:
        msg["id"] = msg_id
    if params is not None:
        msg["params"] = params
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return client.post("/api/mcp", json=msg, headers=headers)


def test_initialize_unauthenticated(client):
    r = _rpc(
        client,
        "initialize",
        {"protocolVersion": "2025-03-26", "clientInfo": {"name": "test", "version": "0"}},
    )
    assert r.status_code == 200
    result = r.json()["result"]
    assert result["protocolVersion"] == "2025-03-26"
    assert result["serverInfo"]["name"] == "doction"
    assert "tools" in result["capabilities"]


def test_initialize_teaches_linking(client):
    # An agent must learn wikilink syntax from the server itself, and the syntax it is
    # taught must be the one the parser reads.
    result = _rpc(client, "initialize", {"protocolVersion": "2025-03-26"}).json()["result"]
    assert "[[slug|label]]" in result["instructions"]
    assert extract_links("see [[slug|label]]") == ["slug"]
    tools = {t["name"]: t for t in _rpc(client, "tools/list").json()["result"]["tools"]}
    for name in ("create_page", "update_page", "upsert_page_section"):
        assert "[[slug]]" in tools[name]["description"]


def test_initialize_unknown_protocol_falls_back(client):
    r = _rpc(client, "initialize", {"protocolVersion": "1999-01-01"})
    assert r.json()["result"]["protocolVersion"] == "2025-03-26"


def test_notification_returns_202(client):
    r = _rpc(client, "notifications/initialized", msg_id=None)
    assert r.status_code == 202
    assert not r.content


def test_ping(client):
    r = _rpc(client, "ping")
    assert r.json()["result"] == {}


def test_tools_list(client):
    r = _rpc(client, "tools/list")
    tools = {t["name"] for t in r.json()["result"]["tools"]}
    assert tools == {
        # The five in the agent contract.
        "search_knowledge",
        "get_rag_context",
        "get_workspace_tree",
        "read_page_raw",
        "upsert_page_section",
        "list_workspaces",
        "list_members",
        "list_pages",
        "get_page",
        "search_pages",
        "create_page",
        "move_page",
        "rename_page",
        "delete_page",
        "list_children",
        "update_page",
        "get_page_history",
        "extract",
        "list_backlinks",
        "get_linked_knowledge",
        "related_pages",
        "suggest_links",
        "suggest_tags",
        "summarize_page",
        "workspace_insights",
    }
    for tool in r.json()["result"]["tools"]:
        assert tool["inputSchema"]["type"] == "object"


def test_unknown_method(client):
    r = _rpc(client, "resources/list")
    assert r.json()["error"]["code"] == -32601


def test_invalid_request(client):
    r = client.post("/api/mcp", json={"hello": "world"})
    assert r.json()["error"]["code"] == -32600


def test_parse_error(client):
    r = client.post("/api/mcp", content=b"not json", headers={"Content-Type": "application/json"})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == -32700


def test_tools_call_requires_auth(client):
    r = _rpc(client, "tools/call", {"name": "list_workspaces", "arguments": {}})
    assert r.status_code == 401


def test_unknown_tool(client):
    token = get_token(client)
    r = _rpc(client, "tools/call", {"name": "drop_tables", "arguments": {}}, token=token)
    assert r.json()["error"]["code"] == -32602


def test_list_workspaces(client):
    token = get_token(client)
    data = tool_data(mcp_call(client, token, "list_workspaces"))
    assert data[0]["slug"] == "personal"


def test_create_get_roundtrip(client):
    token = get_token(client)
    created = tool_data(
        mcp_call(
            client, token, "create_page", {"title": "Runbook SBC", "content": "# Failover\nkamctl"}
        )
    )
    page = tool_data(mcp_call(client, token, "get_page", {"slug": created["slug"]}))
    assert page["title"] == "Runbook SBC"
    assert "kamctl" in page["content"]


def test_create_without_title_derives_it(client):
    """The title is optional: it is derived from the first line of the text."""
    token = get_token(client)
    data = tool_data(mcp_call(client, token, "create_page", {"content": "orphan"}))
    assert data["title"] == "orphan"


def test_search_pages(client):
    token = get_token(client)
    mcp_call(client, token, "create_page", {"title": "Kamailio tips", "content": "dispatcher list"})
    data = tool_data(mcp_call(client, token, "search_pages", {"query": "dispatcher"}))
    assert any(r["slug"] == "kamailio-tips" for r in data)


def test_update_page(client):
    token = get_token(client)
    created = tool_data(mcp_call(client, token, "create_page", {"title": "Draft", "content": "v1"}))
    tool_data(mcp_call(client, token, "update_page", {"slug": created["slug"], "content": "v2"}))
    page = tool_data(mcp_call(client, token, "get_page", {"slug": created["slug"]}))
    assert page["content"] == "v2"
    assert page["title"] == "Draft"


def test_get_page_history(client):
    token = get_token(client)
    created = tool_data(mcp_call(client, token, "create_page", {"title": "Hist", "content": "a"}))
    tool_data(mcp_call(client, token, "update_page", {"slug": created["slug"], "content": "b"}))
    history = tool_data(mcp_call(client, token, "get_page_history", {"slug": created["slug"]}))
    assert len(history) >= 2
    assert {"sha", "timestamp", "message"} <= set(history[0])


def test_page_not_found_is_tool_error(client):
    token = get_token(client)
    result = mcp_call(client, token, "get_page", {"slug": "nope"})
    assert result["isError"] is True


def test_unknown_workspace_is_tool_error(client):
    token = get_token(client)
    result = mcp_call(client, token, "list_pages", {"workspace": "ghost"})
    assert result["isError"] is True


def test_batch_request(client):
    msgs = [
        {"jsonrpc": "2.0", "id": 1, "method": "ping"},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    ]
    r = client.post("/api/mcp", json=msgs)
    assert r.status_code == 200
    out = r.json()
    assert isinstance(out, list) and len(out) == 2
    assert {m["id"] for m in out} == {1, 2}
