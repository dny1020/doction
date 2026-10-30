import json


def get_token(client, email: str = "u@test.com", password: str = "password123") -> str:
    client.post("/api/auth/register", json={"email": email, "password": password})
    r = client.post("/api/token", json={"email": email, "password": password})
    return r.json()["token"]


def mcp_call(client, token: str, tool: str, arguments: dict | None = None) -> dict:
    msg = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": tool, "arguments": arguments or {}},
    }
    r = client.post("/api/mcp", json=msg, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    return r.json()["result"]


def tool_data(result: dict):
    assert not result.get("isError"), result
    return json.loads(result["content"][0]["text"])
