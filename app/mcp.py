"""Servidor MCP nativo: JSON-RPC 2.0 en POST /api/mcp, sin SDK.

Auth Bearer del middleware de app.main; modo stateless (JSON plano, sin SSE).
"""

from __future__ import annotations

import json
import logging
import sqlite3
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, Response

from app import db, embeddings, git_repo

logger = logging.getLogger(__name__)

SERVER_INFO = {"name": "doction", "version": "0.11"}
PROTOCOL_VERSIONS = {"2024-11-05", "2025-03-26", "2025-06-18"}
DEFAULT_PROTOCOL = "2025-03-26"

router = APIRouter(prefix="/api")


# ── Tools ────────────────────────────────────────────────────────────────────

def _workspace(user_id: int, args: dict) -> sqlite3.Row:
    slug = (args.get("workspace") or "").strip()
    if slug:
        ws = db.get_workspace_by_slug(user_id, slug)
        if ws is None:
            raise ValueError(f"Workspace not found: {slug}")
        return ws
    return db.ensure_default_workspace(user_id)


def _require(args: dict, key: str) -> str:
    value = args.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Missing required argument: {key}")
    return value.strip()


def _git_commit(user_id: int, ws: sqlite3.Row, slug: str, title: str, content: str) -> None:
    user = db.get_user_by_id(user_id)
    author = user["email"] if user else "user"
    sha = git_repo.commit_page(ws["slug"], slug, content, author, f"Save: {title}")
    if sha:
        db.set_page_git_commit(user_id, int(ws["id"]), slug, sha)


def _tool_list_workspaces(user_id: int, args: dict) -> Any:
    return [
        {"slug": w["slug"], "name": w["name"], "role": w["role"]}
        for w in db.list_workspaces(user_id)
    ]


def _tool_list_members(user_id: int, args: dict) -> Any:
    ws = _workspace(user_id, args)
    return [
        {"email": m["email"], "display_name": m["display_name"], "role": m["role"]}
        for m in db.list_workspace_members(int(ws["id"]))
    ]


def _tool_list_pages(user_id: int, args: dict) -> Any:
    ws = _workspace(user_id, args)
    return db.list_pages_tree(user_id, int(ws["id"]))


def _tool_get_page(user_id: int, args: dict) -> Any:
    slug = _require(args, "slug")
    ws = _workspace(user_id, args)
    page = db.get_page(slug, user_id, int(ws["id"]))
    if page is None:
        raise ValueError(f"Page not found: {slug}")
    return {
        "slug": page["slug"],
        "title": page["title"],
        "content": page["content"],
        "parent_slug": page["parent_slug"],
        "created_at": page["created_at"],
        "updated_at": page["updated_at"],
    }


def _tool_search_pages(user_id: int, args: dict) -> Any:
    query = _require(args, "query")
    ws = _workspace(user_id, args)
    results = db.search_pages(user_id, int(ws["id"]), query)
    return [{"slug": r["slug"], "title": r["title"], "snippet": r["snippet"]} for r in results]


def _tool_create_page(user_id: int, args: dict) -> Any:
    title = _require(args, "title")
    content = args.get("content") or ""
    ws = _workspace(user_id, args)
    slug = db.create_page(
        user_id, int(ws["id"]), title, content,
        parent_slug=args.get("parent_slug") or None,
        requested_slug=args.get("slug") or None,
    )
    _git_commit(user_id, ws, slug, title, content)
    return {"slug": slug, "title": title}


def _tool_update_page(user_id: int, args: dict) -> Any:
    slug = _require(args, "slug")
    ws = _workspace(user_id, args)
    page = db.get_page(slug, user_id, int(ws["id"]))
    if page is None:
        raise ValueError(f"Page not found: {slug}")
    title = args.get("title") if args.get("title") is not None else page["title"]
    content = args.get("content") if args.get("content") is not None else page["content"]
    db.update_page(user_id, int(ws["id"]), slug, title, content)
    _git_commit(user_id, ws, slug, title, content)
    return {"slug": slug, "title": title, "updated": True}


def _tool_get_page_history(user_id: int, args: dict) -> Any:
    slug = _require(args, "slug")
    limit = int(args.get("limit") or 50)
    ws = _workspace(user_id, args)
    if db.get_page(slug, user_id, int(ws["id"])) is None:
        raise ValueError(f"Page not found: {slug}")
    return git_repo.get_page_history(ws["slug"], slug, limit=limit)


def _tool_extract(user_id: int, args: dict) -> Any:
    ws = _workspace(user_id, args)
    return db.extract_pages(
        user_id,
        int(ws["id"]),
        page_type=(args.get("type") or None),
        tag=(args.get("tag") or None),
    )


def _tool_list_backlinks(user_id: int, args: dict) -> Any:
    slug = _require(args, "slug")
    ws = _workspace(user_id, args)
    if db.get_page(slug, user_id, int(ws["id"])) is None:
        raise ValueError(f"Page not found: {slug}")
    return db.backlinks(user_id, int(ws["id"]), slug)


def _tool_related_pages(user_id: int, args: dict) -> Any:
    slug = _require(args, "slug")
    ws = _workspace(user_id, args)
    related = db.related_pages(user_id, int(ws["id"]), slug)
    if related is None:
        raise ValueError(f"Page not found: {slug}")
    return related


def _tool_sgrep(user_id: int, args: dict) -> Any:
    query = _require(args, "query")
    ws = _workspace(user_id, args)
    limit = int(args.get("limit") or 10)
    return embeddings.semantic_search(user_id, int(ws["id"]), query, k=limit)


def _tool_rag(user_id: int, args: dict) -> Any:
    query = _require(args, "query")
    ws = _workspace(user_id, args)
    limit = int(args.get("limit") or 6)
    return embeddings.rag_context(user_id, int(ws["id"]), query, k=limit)


_WORKSPACE_PROP = {
    "workspace": {
        "type": "string",
        "description": "Workspace slug; defaults to the user's default workspace.",
    }
}

TOOLS: list[dict] = [
    {
        "name": "list_workspaces",
        "description": "List the user's workspaces (slug, name, role).",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "list_members",
        "description": "List the members of a workspace (email, display name, role).",
        "inputSchema": {"type": "object", "properties": {**_WORKSPACE_PROP}},
    },
    {
        "name": "list_pages",
        "description": "List all pages in a workspace as a flat tree (slug, title, depth).",
        "inputSchema": {"type": "object", "properties": {**_WORKSPACE_PROP}},
    },
    {
        "name": "get_page",
        "description": "Read a page: title, markdown content and metadata.",
        "inputSchema": {
            "type": "object",
            "properties": {"slug": {"type": "string"}, **_WORKSPACE_PROP},
            "required": ["slug"],
        },
    },
    {
        "name": "search_pages",
        "description": "Full-text search (SQLite FTS5/BM25) over titles and content.",
        "inputSchema": {
            "type": "object",
            "properties": {"query": {"type": "string"}, **_WORKSPACE_PROP},
            "required": ["query"],
        },
    },
    {
        "name": "create_page",
        "description": "Create a markdown page. Returns the generated slug.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "content": {"type": "string", "description": "Markdown body."},
                "parent_slug": {"type": "string", "description": "Optional parent page slug."},
                "slug": {"type": "string", "description": "Optional explicit slug."},
                **_WORKSPACE_PROP,
            },
            "required": ["title"],
        },
    },
    {
        "name": "update_page",
        "description": "Update a page's title and/or content. Slug stays stable.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "slug": {"type": "string"},
                "title": {"type": "string"},
                "content": {"type": "string", "description": "Full markdown body (replaces)."},
                **_WORKSPACE_PROP,
            },
            "required": ["slug"],
        },
    },
    {
        "name": "get_page_history",
        "description": "Git commit history for a page (sha, timestamp, author, message).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "slug": {"type": "string"},
                "limit": {"type": "integer", "default": 50},
                **_WORKSPACE_PROP,
            },
            "required": ["slug"],
        },
    },
    {
        "name": "extract",
        "description": (
            "Structured query over page frontmatter/tags (no LLM). Filter a workspace "
            "by `type` (e.g. decision, runbook) and/or `tag`; returns slug, title, type, "
            "tags and frontmatter."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "type": {"type": "string", "description": "Filter by frontmatter `type:`."},
                "tag": {"type": "string", "description": "Filter by tag (frontmatter or #tag)."},
                **_WORKSPACE_PROP,
            },
        },
    },
    {
        "name": "list_backlinks",
        "description": "Pages that link to this page via [[wikilink]] (incoming edges).",
        "inputSchema": {
            "type": "object",
            "properties": {"slug": {"type": "string"}, **_WORKSPACE_PROP},
            "required": ["slug"],
        },
    },
    {
        "name": "related_pages",
        "description": "Neighbor pages ranked by shared-tag overlap (knowledge graph).",
        "inputSchema": {
            "type": "object",
            "properties": {"slug": {"type": "string"}, **_WORKSPACE_PROP},
            "required": ["slug"],
        },
    },
    {
        "name": "sgrep",
        "description": (
            "Semantic grep: meaning-based search (local embeddings) blended with BM25 "
            "keyword boost. Returns slug, title, score, matched chunk. Degrades to "
            "full-text search when semantic search is disabled or not yet indexed."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Natural-language query."},
                "limit": {"type": "integer", "default": 10},
                **_WORKSPACE_PROP,
            },
            "required": ["query"],
        },
    },
    {
        "name": "rag",
        "description": (
            "Retrieval pipe: returns the top-k most relevant chunks with provenance "
            "(slug, ord, score, text) for the agent to synthesize an answer. Does NOT "
            "generate text itself."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "default": 6},
                **_WORKSPACE_PROP,
            },
            "required": ["query"],
        },
    },
]

TOOL_HANDLERS: dict[str, Callable[[int, dict], Any]] = {
    "list_workspaces": _tool_list_workspaces,
    "list_members": _tool_list_members,
    "list_pages": _tool_list_pages,
    "get_page": _tool_get_page,
    "search_pages": _tool_search_pages,
    "create_page": _tool_create_page,
    "update_page": _tool_update_page,
    "get_page_history": _tool_get_page_history,
    "extract": _tool_extract,
    "list_backlinks": _tool_list_backlinks,
    "related_pages": _tool_related_pages,
    "sgrep": _tool_sgrep,
    "rag": _tool_rag,
}


# ── JSON-RPC dispatch ────────────────────────────────────────────────────────

def _result(msg_id: Any, result: dict | list) -> dict:
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def _error(msg_id: Any, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}


def _tool_text(data: Any, *, is_error: bool = False) -> dict:
    text = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False, indent=2)
    result: dict = {"content": [{"type": "text", "text": text}]}
    if is_error:
        result["isError"] = True
    return result


def _call_tool(request: Request, msg_id: Any, params: dict) -> dict:
    user_id = getattr(request.state, "user_id", None)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    name = params.get("name")
    handler = TOOL_HANDLERS.get(name)
    if handler is None:
        return _error(msg_id, -32602, f"Unknown tool: {name}")
    arguments = params.get("arguments") or {}
    try:
        return _result(msg_id, _tool_text(handler(int(user_id), arguments)))
    except ValueError as exc:
        return _result(msg_id, _tool_text(str(exc), is_error=True))
    except Exception:
        logger.exception("mcp: tool %s failed", name)
        return _result(msg_id, _tool_text(f"Tool {name} failed unexpectedly", is_error=True))


def _handle_message(request: Request, msg: Any) -> dict | None:
    """Despacha un mensaje JSON-RPC; None si es notificación (sin id)."""
    if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0" or "method" not in msg:
        return _error(msg.get("id") if isinstance(msg, dict) else None, -32600, "Invalid Request")
    method = msg["method"]
    msg_id = msg.get("id")
    if msg_id is None:
        return None
    params = msg.get("params") or {}

    if method == "initialize":
        requested = params.get("protocolVersion")
        version = requested if requested in PROTOCOL_VERSIONS else DEFAULT_PROTOCOL
        return _result(msg_id, {
            "protocolVersion": version,
            "capabilities": {"tools": {}},
            "serverInfo": SERVER_INFO,
        })
    if method == "ping":
        return _result(msg_id, {})
    if method == "tools/list":
        return _result(msg_id, {"tools": TOOLS})
    if method == "tools/call":
        return _call_tool(request, msg_id, params)
    return _error(msg_id, -32601, f"Method not found: {method}")


@router.post("/mcp")
async def mcp_endpoint(request: Request) -> Response:
    try:
        body = await request.json()
    except (ValueError, UnicodeDecodeError):
        return JSONResponse(_error(None, -32700, "Parse error"), status_code=400)

    messages = body if isinstance(body, list) else [body]
    if not messages:
        return JSONResponse(_error(None, -32600, "Invalid Request"), status_code=400)

    responses = [r for m in messages if (r := _handle_message(request, m)) is not None]
    if not responses:
        return Response(status_code=202)
    return JSONResponse(responses if isinstance(body, list) else responses[0])
