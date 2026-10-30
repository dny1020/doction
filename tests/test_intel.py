"""Tests for the intelligence tools: extract / list_backlinks / related_pages."""

from tests.helpers import get_token, mcp_call, tool_data


def test_extract_by_type_and_tag(client):
    token = get_token(client)
    mcp_call(
        client,
        token,
        "create_page",
        {
            "title": "Migrate SIP",
            "content": "---\ntype: decision\ntags: [sip, kamailio]\n---\nWe migrate.",
        },
    )
    mcp_call(
        client,
        token,
        "create_page",
        {
            "title": "SBC Runbook",
            "content": "---\ntype: runbook\ntags: [sbc]\n---\nFailover steps.",
        },
    )

    decisions = tool_data(mcp_call(client, token, "extract", {"type": "decision"}))
    assert [p["slug"] for p in decisions] == ["migrate-sip"]
    assert decisions[0]["tags"] == ["sip", "kamailio"]

    sip_tagged = tool_data(mcp_call(client, token, "extract", {"tag": "sip"}))
    assert [p["slug"] for p in sip_tagged] == ["migrate-sip"]

    # No filter returns everything in the workspace (seed pages included).
    all_pages = tool_data(mcp_call(client, token, "extract"))
    assert {"migrate-sip", "sbc-runbook"} <= {p["slug"] for p in all_pages}


def test_backlinks_follow_wikilinks(client):
    token = get_token(client)
    mcp_call(client, token, "create_page", {"title": "Failover", "content": "the target page"})
    mcp_call(
        client,
        token,
        "create_page",
        {"title": "Runbook", "content": "see [[failover]] for details"},
    )

    back = tool_data(mcp_call(client, token, "list_backlinks", {"slug": "failover"}))
    assert [p["slug"] for p in back] == ["runbook"]

    # Updating to drop the link removes the backlink (re-indexed on save).
    mcp_call(client, token, "update_page", {"slug": "runbook", "content": "no link now"})
    assert tool_data(mcp_call(client, token, "list_backlinks", {"slug": "failover"})) == []


def test_related_pages_by_shared_tags(client):
    token = get_token(client)
    mcp_call(
        client, token, "create_page", {"title": "A", "content": "---\ntags: [sip, voip]\n---\na"}
    )
    mcp_call(
        client, token, "create_page", {"title": "B", "content": "---\ntags: [sip, voip]\n---\nb"}
    )
    mcp_call(client, token, "create_page", {"title": "C", "content": "---\ntags: [sip]\n---\nc"})

    related = tool_data(mcp_call(client, token, "related_pages", {"slug": "a"}))
    slugs = [p["slug"] for p in related]
    assert slugs[0] == "b"  # shares 2 tags, ranked first
    assert "c" in slugs  # shares 1 tag
    assert related[0]["shared_tags"] == 2


def test_related_pages_missing_is_tool_error(client):
    token = get_token(client)
    result = mcp_call(client, token, "related_pages", {"slug": "nope"})
    assert result["isError"] is True
