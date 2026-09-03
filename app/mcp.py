"""Servidor MCP nativo: JSON-RPC 2.0 en POST /api/mcp, sin SDK.

Auth Bearer del middleware de app.main; modo stateless (JSON plano, sin SSE).
"""

import dataclasses
import json
import logging
from collections.abc import Callable

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, Response

from app import db, embeddings, git_repo, meta, suggest
from app.models import Workspace
from app.version import VERSION

logger = logging.getLogger(__name__)

SERVER_INFO = {"name": "doction", "version": VERSION}
PROTOCOL_VERSIONS = {"2024-11-05", "2025-03-26", "2025-06-18"}
DEFAULT_PROTOCOL = "2025-03-26"

router = APIRouter(prefix="/api")


# ── Tools ────────────────────────────────────────────────────────────────────


def _workspace(user_id: int, args: dict) -> Workspace:
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


def _git_commit(user_id: int, ws: Workspace, slug: str, title: str, content: str) -> None:
    user = db.get_user_by_id(user_id)
    author = user.email if user else "user"
    git_repo.commit_and_record(int(ws.id), ws.slug, slug, title, content, author)


def _tool_list_workspaces(user_id: int, _args: dict) -> list[dict]:
    return [{"slug": w.slug, "name": w.name, "role": w.role} for w in db.list_workspaces(user_id)]


def _tool_list_members(user_id: int, args: dict) -> list[dict]:
    ws = _workspace(user_id, args)
    return [
        {"email": m.email, "display_name": m.display_name, "role": m.role}
        for m in db.list_workspace_members(int(ws.id))
    ]


def _tool_list_pages(user_id: int, args: dict) -> list[dict]:
    ws = _workspace(user_id, args)
    nodes = db.list_pages_tree(int(ws.id))
    return [dataclasses.asdict(node) for node in nodes]


def _tool_get_page(user_id: int, args: dict) -> dict:
    slug = _require(args, "slug")
    ws = _workspace(user_id, args)
    page = db.get_page(slug, int(ws.id))
    if page is None:
        raise ValueError(f"Page not found: {slug}")
    return {
        "slug": page.slug,
        "title": page.title,
        "content": page.content,
        "parent_slug": page.parent_slug,
        "created_at": page.created_at,
        "updated_at": page.updated_at,
    }


def _tool_search_pages(user_id: int, args: dict) -> list[dict]:
    query = _require(args, "query")
    ws = _workspace(user_id, args)
    results = db.search_pages(int(ws.id), query)
    out: list[dict] = [{"slug": r.slug, "title": r.title, "snippet": r.snippet} for r in results]
    # Uploads con texto OCR indexado (OCR_UPLOADS): items extra con type="upload".
    out += [
        {"type": "upload", "name": h.name, "url": f"/uploads/{h.name}", "snippet": h.snippet}
        for h in db.search_uploads(int(ws.id), query)
    ]
    return out


def _tool_create_page(user_id: int, args: dict) -> dict:
    # title opcional: db.create_page lo deriva de la primera línea del contenido.
    title = str(args.get("title") or "")
    content = args.get("content") or ""
    ws = _workspace(user_id, args)
    slug = db.create_page(
        user_id,
        int(ws.id),
        title,
        content,
        parent_slug=args.get("parent_slug") or None,
        requested_slug=args.get("slug") or None,
    )
    page = db.get_page(slug, int(ws.id))
    final_title = page.title if page else title
    _git_commit(user_id, ws, slug, final_title, content)
    return {"slug": slug, "title": final_title}


def _tool_move_page(user_id: int, args: dict) -> dict:
    slug = _require(args, "slug")
    ws = _workspace(user_id, args)
    moved = db.move_page(int(ws.id), slug, args.get("parent_slug") or None)
    if moved is None:
        raise ValueError(f"Page not found: {slug}")
    return {"slug": moved, "parent_slug": args.get("parent_slug") or None, "moved": True}


def _tool_rename_page(user_id: int, args: dict) -> dict:
    slug = _require(args, "slug")
    new_slug = _require(args, "new_slug")
    ws = _workspace(user_id, args)
    renamed = db.rename_page(int(ws.id), slug, new_slug)
    if renamed is None:
        raise ValueError(f"Page not found: {slug}")
    if renamed != slug:
        user = db.get_user_by_id(user_id)
        git_repo.rename_page_file(ws.slug, slug, renamed, user.email if user else "user")
    return {"slug": renamed, "previous_slug": slug}


def _tool_delete_page(user_id: int, args: dict) -> dict:
    slug = _require(args, "slug")
    ws = _workspace(user_id, args)
    if not db.delete_page(int(ws.id), slug):
        raise ValueError(f"Page not found: {slug}")
    return {"slug": slug, "deleted": True}


def _tool_list_children(user_id: int, args: dict) -> list:
    slug = _require(args, "slug")
    ws = _workspace(user_id, args)
    children = db.list_children(int(ws.id), slug)
    if children is None:
        raise ValueError(f"Page not found: {slug}")
    return [{"slug": c.slug, "title": c.title} for c in children]


def _tool_update_page(user_id: int, args: dict) -> dict:
    slug = _require(args, "slug")
    ws = _workspace(user_id, args)
    page = db.get_page(slug, int(ws.id))
    if page is None:
        raise ValueError(f"Page not found: {slug}")
    title = str(args["title"]) if args.get("title") is not None else page.title
    content = str(args["content"]) if args.get("content") is not None else page.content
    db.update_page(user_id, int(ws.id), slug, title, content)
    _git_commit(user_id, ws, slug, title, content)
    return {"slug": slug, "title": title, "updated": True}


def _tool_get_page_history(user_id: int, args: dict) -> list[dict]:
    slug = _require(args, "slug")
    limit = int(args.get("limit") or 50)
    ws = _workspace(user_id, args)
    if db.get_page(slug, int(ws.id)) is None:
        raise ValueError(f"Page not found: {slug}")
    history = git_repo.get_page_history(ws.slug, slug, limit=limit)
    return [dataclasses.asdict(entry) for entry in history]


def _tool_extract(user_id: int, args: dict) -> list[dict]:
    ws = _workspace(user_id, args)
    pages = db.extract_pages(
        int(ws.id),
        page_type=(args.get("type") or None),
        tag=(args.get("tag") or None),
    )
    return [dataclasses.asdict(page) for page in pages]


def _tool_list_backlinks(user_id: int, args: dict) -> list[dict]:
    slug = _require(args, "slug")
    ws = _workspace(user_id, args)
    if db.get_page(slug, int(ws.id)) is None:
        raise ValueError(f"Page not found: {slug}")
    return [dataclasses.asdict(ref) for ref in db.backlinks(int(ws.id), slug)]


def _tool_related_pages(user_id: int, args: dict) -> list[dict]:
    slug = _require(args, "slug")
    ws = _workspace(user_id, args)
    related = db.related_pages(int(ws.id), slug)
    if related is None:
        raise ValueError(f"Page not found: {slug}")
    return [dataclasses.asdict(page) for page in related]


def _tool_search_knowledge(user_id: int, args: dict) -> list[dict]:
    """Búsqueda híbrida con filtros. El orden es el mismo que sirve la interfaz."""
    query = _require(args, "query")
    ws = _workspace(user_id, args)
    limit = int(args.get("limit") or 10)
    tags = args.get("tags") or None
    if isinstance(tags, str):
        tags = [tags]
    hits = embeddings.search(int(ws.id), query, mode="hybrid", tags=tags)[:limit]
    # `parts` es el troceado del extracto para pintar el resaltado en la interfaz.
    # Un agente lee texto, no <mark>, y además son dataclasses que json.dumps no
    # serializa: fuera.
    return [{k: v for k, v in hit.items() if k != "parts"} for hit in hits]


def _tool_get_workspace_tree(user_id: int, args: dict) -> dict:
    """El árbol de verdad, anidado. `list_pages` devolvía la lista plana con `depth`."""
    ws = _workspace(user_id, args)
    flat = db.list_pages_tree(int(ws.id))

    roots: list[dict] = []
    ancestors: list[dict] = []
    for node in flat:
        entry = {"slug": node.slug, "title": node.title, "children": []}
        del ancestors[node.depth :]
        if ancestors:
            ancestors[-1]["children"].append(entry)
        else:
            roots.append(entry)
        ancestors.append(entry)
    return {"workspace": {"slug": ws.slug, "name": ws.name}, "pages": roots}


def _tool_read_page_raw(user_id: int, args: dict) -> dict:
    """El markdown tal cual está guardado, frontmatter incluido.

    Sin renderizar, sin sanear y sin recortar: quien pide la página cruda va a
    editarla, y necesita ver exactamente lo que tendrá que preservar. El frontmatter
    va además parseado aparte, para no obligar a analizarlo dos veces.
    """
    slug = _require(args, "slug")
    ws = _workspace(user_id, args)
    page = db.get_page(slug, int(ws.id))
    if page is None:
        raise ValueError(f"Page not found: {slug}")
    front, _ = meta.parse_frontmatter(page.content)
    return {
        "slug": page.slug,
        "title": page.title,
        "parent_slug": page.parent_slug,
        "updated_at": page.updated_at,
        "content": page.content,
        "frontmatter": front,
        "tags": meta.extract_tags(page.content),
    }


def _tool_upsert_page_section(user_id: int, args: dict) -> dict:
    """Escribe una sección sin reescribir la página."""
    slug = _require(args, "slug")
    heading = _require(args, "heading")
    body = str(args.get("body") or "")
    ws = _workspace(user_id, args)
    level = int(args.get("level") or 2)
    parent = args.get("parent") or None

    try:
        written = db.upsert_page_section(
            user_id, int(ws.id), slug, heading, body, level=level, parent=parent
        )
    except meta.AmbiguousSection as exc:
        # Se sube como error del tool, no se resuelve por el llamante: elegir cuál de
        # dos encabezados idénticos quería es adivinar sobre su documentación.
        raise ValueError(str(exc)) from exc
    if written is None:
        raise ValueError(f"Page not found: {slug}")

    page = db.get_page(slug, int(ws.id))
    if page is not None:
        _git_commit(user_id, ws, slug, page.title, page.content)
    return {"slug": slug, "heading": heading, "updated": True}


def _tool_sgrep(user_id: int, args: dict) -> list[dict]:
    query = _require(args, "query")
    ws = _workspace(user_id, args)
    limit = int(args.get("limit") or 10)
    # La misma búsqueda que sirve la barra lateral y /api/search. Antes esto llamaba
    # a la lista vectorial con su propio boost, así que un agente por MCP y una
    # persona mirando la interfaz veían dos órdenes distintos para la misma consulta.
    hits = embeddings.search(int(ws.id), query, mode="hybrid")[:limit]
    # `parts` es el troceado del extracto para pintar el resaltado en la interfaz.
    # Un agente lee texto, no <mark>, y además son dataclasses que json.dumps no
    # serializa: fuera.
    return [{k: v for k, v in hit.items() if k != "parts"} for hit in hits]


def _tool_rag(user_id: int, args: dict) -> dict:
    query = _require(args, "query")
    ws = _workspace(user_id, args)
    limit = int(args.get("limit") or 6)
    return embeddings.rag_context(int(ws.id), query, k=limit)


def _tool_suggest_links(user_id: int, args: dict) -> dict:
    slug = _require(args, "slug")
    ws = _workspace(user_id, args)
    result = suggest.suggest_links(int(ws.id), slug)
    if result is None:
        raise ValueError(f"Page not found: {slug}")
    return result


def _tool_suggest_tags(user_id: int, args: dict) -> dict:
    slug = _require(args, "slug")
    ws = _workspace(user_id, args)
    result = suggest.suggest_tags(int(ws.id), slug)
    if result is None:
        raise ValueError(f"Page not found: {slug}")
    return result


def _tool_summarize_page(user_id: int, args: dict) -> dict:
    slug = _require(args, "slug")
    ws = _workspace(user_id, args)
    page = db.get_page(slug, int(ws.id))
    if page is None:
        raise ValueError(f"Page not found: {slug}")
    k = max(1, min(int(args.get("sentences") or 3), 10))
    return {"slug": slug, **suggest.summarize(page.content, k=k)}


def _tool_workspace_insights(user_id: int, args: dict) -> dict:
    ws = _workspace(user_id, args)
    return suggest.workspace_insights(int(ws.id))


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
        "description": (
            "Full-text search (PostgreSQL tsvector/ts_rank) over titles and content. "
            'Also returns OCR-indexed upload matches (items with type="upload") when '
            "the server has OCR_UPLOADS enabled."
        ),
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
            # Nada obligatorio: sin título se deriva del contenido, y sin
            # contenido queda una página vacía que se rellena después. Mismo
            # contrato que POST /api/pages, para que no diverjan.
            "required": [],
        },
    },
    {
        "name": "move_page",
        "description": (
            "Reparent a page. Cheap: the git repo is flat, so no file moves. "
            "Omit parent_slug to move it to the root."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "slug": {"type": "string"},
                "parent_slug": {"type": "string", "description": "New parent, or omit for root."},
                **_WORKSPACE_PROP,
            },
            "required": ["slug"],
        },
    },
    {
        "name": "rename_page",
        "description": (
            "Change a page's slug. The old slug keeps resolving through an alias, "
            "so existing [[wikilinks]] do not break."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "slug": {"type": "string"},
                "new_slug": {"type": "string"},
                **_WORKSPACE_PROP,
            },
            "required": ["slug", "new_slug"],
        },
    },
    {
        "name": "delete_page",
        "description": "Soft-delete a page; it goes to the trash and can be restored.",
        "inputSchema": {
            "type": "object",
            "properties": {"slug": {"type": "string"}, **_WORKSPACE_PROP},
            "required": ["slug"],
        },
    },
    {
        "name": "list_children",
        "description": "Direct children of a page.",
        "inputSchema": {
            "type": "object",
            "properties": {"slug": {"type": "string"}, **_WORKSPACE_PROP},
            "required": ["slug"],
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
        "name": "search_knowledge",
        "description": (
            "Find pages. Hybrid search: the lexical and the vector rankings fused by "
            "reciprocal rank, filterable by tag. Returns one entry per page with its "
            "best matching passage and which retrievers found it — use this to pick "
            "what to read, and get_rag_context to read it. Read-only."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Natural language or exact terms."},
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Only pages carrying one of these tags. Applied during "
                    "retrieval, so a page below the cut can surface once others are filtered.",
                },
                "limit": {"type": "integer", "default": 10},
                **_WORKSPACE_PROP,
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_rag_context",
        "description": (
            "Gather passages to answer from. Returns the top-k chunks with provenance "
            "(workspace > page > section, slug, score) so an answer can cite them. "
            "doction does NOT generate text: every passage is verbatim from a stored "
            "page and the synthesis is yours. Read-only."
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
    {
        "name": "get_workspace_tree",
        "description": (
            "How the workspace is organised: pages and their subpages, nested. Use it "
            "to find where a topic belongs before writing. Read-only."
        ),
        "inputSchema": {"type": "object", "properties": {**_WORKSPACE_PROP}},
    },
    {
        "name": "read_page_raw",
        "description": (
            "A page's markdown exactly as stored, frontmatter block included and "
            "unmodified, plus its parsed frontmatter and tags. Read this before "
            "editing — it is what a write has to preserve. Read-only."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"slug": {"type": "string"}, **_WORKSPACE_PROP},
            "required": ["slug"],
        },
    },
    {
        "name": "upsert_page_section",
        "description": (
            "WRITE. Replace one section of a page, or add it if absent, leaving every "
            "other byte untouched — no need to send the whole body back, so two agents "
            "editing different sections do not overwrite each other. Refuses when the "
            "page has more than one heading with that text; pass `level` to "
            "disambiguate. Records a version and re-indexes like any other write."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "slug": {"type": "string"},
                "heading": {"type": "string", "description": "Section heading text, no #."},
                "body": {"type": "string", "description": "Markdown for the section body."},
                "level": {
                    "type": "integer",
                    "default": 2,
                    "description": "Heading level when creating the section (1-6).",
                },
                "parent": {
                    "type": "string",
                    "description": "Heading to place a new section under. Appended at the "
                    "end of the page when absent or not found.",
                },
                **_WORKSPACE_PROP,
            },
            "required": ["slug", "heading"],
        },
    },
    {
        "name": "sgrep",
        "description": (
            "Hybrid search: the lexical and the vector rankings fused by reciprocal "
            "rank. Returns slug, title, score, matched chunk, and which retrievers "
            "found it. Identical ordering to the web UI and /api/search. Degrades to "
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
        "name": "suggest_links",
        "description": (
            "Pages this page should probably link to but doesn't yet: cosine similarity "
            "over local page embeddings, or literal title mentions when semantic search "
            "is off. Returns slug, title, score and a `mode` field."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"slug": {"type": "string"}, **_WORKSPACE_PROP},
            "required": ["slug"],
        },
    },
    {
        "name": "suggest_tags",
        "description": (
            "Candidate tags for a page: TF-IDF terms that are characteristic of it vs "
            "the rest of the workspace, boosting terms already used as tags elsewhere. "
            "No embeddings needed."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"slug": {"type": "string"}, **_WORKSPACE_PROP},
            "required": ["slug"],
        },
    },
    {
        "name": "summarize_page",
        "description": (
            "Extractive summary (TextRank over local sentence embeddings, no LLM): the "
            "k most central sentences in document order. Falls back to the leading "
            "sentences when semantic search is disabled."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "slug": {"type": "string"},
                "sentences": {"type": "integer", "default": 3},
                **_WORKSPACE_PROP,
            },
            "required": ["slug"],
        },
    },
    {
        "name": "workspace_insights",
        "description": (
            "Workspace health report from the wikilink graph: central pages (PageRank), "
            "orphans, hubs, authorities, broken wikilinks, near-duplicate pairs and "
            "semantic topic clusters (the last two only when semantic search is on)."
        ),
        "inputSchema": {"type": "object", "properties": {**_WORKSPACE_PROP}},
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

# Nombre de la tool → función que la implementa. Cada función recibe
# (user_id, args) y devuelve un dict o una lista de dicts listos para JSON.
#
# Los nombres viejos —`sgrep`, `rag`, `list_pages`, `get_page`— siguen aquí y siguen
# funcionando. Un agente configurado contra ellos se rompería en mitad de una
# conversación, con un error sobre el que no puede hacer nada. Se mantienen una
# versión; `tools/list` ya solo anuncia los nuevos.
TOOL_HANDLERS: dict[str, Callable[[int, dict], dict | list | str]] = {
    # Las cinco herramientas del contrato con los agentes.
    "search_knowledge": _tool_search_knowledge,
    "get_rag_context": _tool_rag,
    "get_workspace_tree": _tool_get_workspace_tree,
    "read_page_raw": _tool_read_page_raw,
    "upsert_page_section": _tool_upsert_page_section,
    "list_workspaces": _tool_list_workspaces,
    "list_members": _tool_list_members,
    "list_pages": _tool_list_pages,
    "get_page": _tool_get_page,
    "search_pages": _tool_search_pages,
    "create_page": _tool_create_page,
    "move_page": _tool_move_page,
    "rename_page": _tool_rename_page,
    "delete_page": _tool_delete_page,
    "list_children": _tool_list_children,
    "update_page": _tool_update_page,
    "get_page_history": _tool_get_page_history,
    "extract": _tool_extract,
    "list_backlinks": _tool_list_backlinks,
    "related_pages": _tool_related_pages,
    "sgrep": _tool_sgrep,
    "rag": _tool_rag,
    "suggest_links": _tool_suggest_links,
    "suggest_tags": _tool_suggest_tags,
    "summarize_page": _tool_summarize_page,
    "workspace_insights": _tool_workspace_insights,
}


# ── JSON-RPC dispatch ────────────────────────────────────────────────────────


def _result(msg_id: str | int | None, result: dict | list) -> dict:
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def _error(msg_id: str | int | None, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}


def _tool_text(data: dict | list | str, *, is_error: bool = False) -> dict:
    text = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False, indent=2)
    result: dict = {"content": [{"type": "text", "text": text}]}
    if is_error:
        result["isError"] = True
    return result


def _call_tool(request: Request, msg_id: str | int | None, params: dict) -> dict:
    user_id = getattr(request.state, "user_id", None)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    name = str(params.get("name") or "")
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


def _handle_message(request: Request, msg) -> dict | None:
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
        return _result(
            msg_id,
            {
                "protocolVersion": version,
                "capabilities": {"tools": {}},
                "serverInfo": SERVER_INFO,
            },
        )
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

    responses = []
    for message in messages:
        response = _handle_message(request, message)
        if response is not None:
            responses.append(response)
    if not responses:
        return Response(status_code=202)
    return JSONResponse(responses if isinstance(body, list) else responses[0])
