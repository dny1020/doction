"""doction MCP server — exposes pages and workspaces to AI agents via stdio transport.

Usage:
    DATABASE_PATH=/data/doction.db \\
    DOCTION_EMAIL=you@example.com \\
    DOCTION_PASSWORD=yourpass \\
    uv run python -m app.mcp_server

Claude Code config (.claude/mcp.json):
    {
      "mcpServers": {
        "doction": {
          "command": "uv",
          "args": ["run", "python", "-m", "app.mcp_server"],
          "cwd": "/path/to/doction",
          "env": {
            "DATABASE_PATH": "/data/doction.db",
            "DOCTION_EMAIL": "you@example.com",
            "DOCTION_PASSWORD": "yourpass"
          }
        }
      }
    }
"""

from __future__ import annotations

import os
import sys

import app.db as db
from app.auth import verify_password

_user_id: int = 0
_workspace_id: int = 0


def _resolve_workspace(workspace_slug: str | None) -> int:
    if workspace_slug is None:
        return _workspace_id
    ws = db.get_workspace_by_slug(_user_id, workspace_slug)
    if ws is None:
        raise ValueError(f"Workspace not found: {workspace_slug}")
    return int(ws["id"])


# ── Tool implementations (module-level for direct testing) ──────────────────

def list_workspaces() -> list[dict]:
    """List all workspaces for the authenticated user."""
    rows = db.list_workspaces(_user_id)
    return [{"id": r["id"], "slug": r["slug"], "name": r["name"]} for r in rows]


def list_pages(workspace_slug: str | None = None) -> list[dict]:
    """List all pages in the workspace as a tree (depth-first, with depth field)."""
    wid = _resolve_workspace(workspace_slug)
    return db.list_pages_tree(_user_id, wid)


def get_page(slug: str, workspace_slug: str | None = None) -> dict:
    """Get the full markdown content of a page by slug."""
    wid = _resolve_workspace(workspace_slug)
    page = db.get_page(slug, _user_id, wid)
    if page is None:
        raise ValueError(f"Page not found: {slug}")
    children = db.list_child_pages(_user_id, wid, int(page["id"]))
    return {
        "slug": page["slug"],
        "title": page["title"],
        "content": page["content"],
        "parent_slug": page["parent_slug"],
        "children": [{"slug": c["slug"], "title": c["title"]} for c in children],
        "created_at": page["created_at"],
        "updated_at": page["updated_at"],
    }


def search_pages(query: str, workspace_slug: str | None = None) -> list[dict]:
    """Full-text search pages. Returns slug, title, and a highlighted snippet."""
    wid = _resolve_workspace(workspace_slug)
    results = db.search_pages(_user_id, wid, query)
    return [{"slug": r["slug"], "title": r["title"], "snippet": r["snippet"]} for r in results]


def create_page(
    title: str,
    content: str,
    parent_slug: str | None = None,
    workspace_slug: str | None = None,
) -> dict:
    """Create a new page. Returns the assigned slug."""
    wid = _resolve_workspace(workspace_slug)
    slug = db.create_page(_user_id, wid, title, content, parent_slug=parent_slug)
    return {"slug": slug, "title": title.strip() or "Untitled"}


def update_page(
    slug: str,
    title: str | None = None,
    content: str | None = None,
    workspace_slug: str | None = None,
) -> dict:
    """Update a page's title and/or content. Returns the slug and confirmation."""
    wid = _resolve_workspace(workspace_slug)
    page = db.get_page(slug, _user_id, wid)
    if page is None:
        raise ValueError(f"Page not found: {slug}")
    new_title = title if title is not None else page["title"]
    new_content = content if content is not None else page["content"]
    db.update_page(_user_id, wid, slug, new_title, new_content)
    return {"slug": slug, "updated": True}


# ── Server wiring ───────────────────────────────────────────────────────────

def _make_server():
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("doction")
    for fn in (list_workspaces, list_pages, get_page, search_pages, create_page, update_page):
        mcp.tool()(fn)
    return mcp


def _authenticate() -> None:
    global _user_id, _workspace_id
    email = os.environ.get("DOCTION_EMAIL", "").strip()
    password = os.environ.get("DOCTION_PASSWORD", "")
    if not email or not password:
        print("DOCTION_EMAIL and DOCTION_PASSWORD env vars are required.", file=sys.stderr)
        sys.exit(1)
    db.init_db()
    user = db.get_user_by_email(email)
    if user is None or not verify_password(password, user["password_hash"]):
        print("Invalid credentials.", file=sys.stderr)
        sys.exit(1)
    _user_id = int(user["id"])
    ws = db.ensure_default_workspace(_user_id)
    _workspace_id = int(ws["id"])


def main() -> None:
    _authenticate()
    mcp = _make_server()
    mcp.run()


if __name__ == "__main__":
    main()
