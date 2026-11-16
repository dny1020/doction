"""Structured memory over existing Markdown pages, without a second content store."""

import json
import re
from datetime import UTC, datetime

from fastapi import HTTPException

from app import access, db, embeddings, meta

TYPES = {
    "Project",
    "Service",
    "Runbook",
    "Incident",
    "Decision",
    "Conversation",
    "Person",
    "Event",
    "Task",
    "Concept",
    "Research",
}
RELATIONS = {"affects", "belongs_to", "derived_from", "supersedes", "decided_by", "related_to"}
STATES = {"active", "archived", "superseded", "draft"}
WRITE_TOOLS = {
    "create_page": "create",
    "update_page": "update",
    "upsert_page_section": "update",
    "move_page": "update",
    "rename_page": "update",
    "delete_page": "delete",
    "set_knowledge_metadata": "update",
    "relate_knowledge": "relate",
    "remove_knowledge_relation": "relate",
    "add_entity_alias": "update",
    "retry_page_version": "update",
}


def authorize_tool(user_id, name, args):
    if access.policy.get() is None:
        return
    if name == "list_workspaces":
        return
    if name == "query_knowledge_context":
        spaces = args.get("workspaces") or [
            w.slug for w in db.list_workspaces(user_id) if access.allowed(w.slug, "read")
        ]
        for workspace in spaces:
            access.require(workspace, "read")
        return
    ws = workspace_for(user_id, args)
    # A workspace-wide read is required for tools exposing related pages.
    page_reads = {"get_page", "read_page_raw", "read_page_sections", "get_page_history"}
    slug = args.get("slug") if name in WRITE_TOOLS or name in page_reads else None
    access.require(ws.slug, WRITE_TOOLS.get(name, "read"), slug)
    # Relationships and hierarchy changes cannot disclose or alter an ungranted target.
    for field in ("target", "parent_slug", "new_slug"):
        if args.get(field):
            access.require(ws.slug, "read", args[field])


def authorize_rest(request):
    path = request.url.path
    if path == "/api/mcp":
        return
    # Management operations cannot be used to mint a stronger token or change membership.
    if path in {"/api/me", "/api/workspaces", "/api/system"} and request.method == "GET":
        return
    match = re.fullmatch(
        r"/api/pages(?:/([^/]+))?(?:/(raw|view|history)(?:/[^/]+(?:/diff)?)?)?", path
    )
    if match:
        ws = request.state.workspace
        if ws is None or request.state.workspace_denied:
            raise PermissionError("Workspace not permitted")
        action = {"GET": "read", "POST": "create", "PUT": "update", "DELETE": "delete"}.get(
            request.method
        )
        if action is None:
            raise PermissionError("Operation not permitted")
        access.require(ws.slug, action, None if match[2] == "view" else match[1])
        return
    if path in {"/api/search", "/api/graph", "/api/insights"} and request.method == "GET":
        ws = request.state.workspace
        if ws is None or request.state.workspace_denied:
            raise PermissionError("Workspace not permitted")
        access.require(ws.slug, "read")
        return
    # Structured-memory REST uses exactly the same authorization as MCP.
    if path.startswith("/api/knowledge/"):
        return
    raise PermissionError("Restricted tokens cannot manage accounts or workspaces")


def workspace_for(user_id, args):
    slug = args.get("workspace")
    if slug:
        ws = db.get_workspace_by_slug(user_id, slug)
        if ws is None:
            raise ValueError(f"Workspace not found: {slug}")
        return ws
    return db.ensure_default_workspace(user_id)


def page_for(user_id, args):
    ws = workspace_for(user_id, args)
    page = db.get_page(args.get("slug", ""), int(ws.id))
    if page is None:
        raise ValueError(f"Page not found: {args.get('slug', '')}")
    return ws, page


def instant(value):
    parsed = datetime.fromisoformat(value)
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def bounded(value, default, maximum):
    result = default if value is None else int(value)
    if not 0 < result <= maximum:
        raise ValueError(f"Value must be between 1 and {maximum}")
    return result


def relations(workspace_id, page_id):
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT r.id, s.id AS source_id, s.slug AS source, r.kind, t.id AS target_id, "
            "t.slug AS target, r.evidence, r.created_at, r.actor FROM knowledge_relations r "
            "JOIN pages s ON s.id = r.source_id JOIN pages t ON t.id = r.target_id "
            "WHERE s.workspace_id = %s AND (s.id = %s OR t.id = %s) "
            "AND s.deleted_at IS NULL AND t.deleted_at IS NULL ORDER BY r.id",
            (workspace_id, page_id, page_id),
        ).fetchall()

        if access.policy.get() is None:
            return rows
        ws = conn.execute("SELECT slug FROM workspaces WHERE id = %s", (workspace_id,)).fetchone()
        return [
            r
            for r in rows
            if access.allowed(ws["slug"], "read", r["source"])
            and access.allowed(ws["slug"], "read", r["target"])
        ]


def get_object(user_id, args):
    ws, page = page_for(user_id, args)
    front, _ = meta.parse_frontmatter(page.content)
    with db.connect() as conn:
        aliases = conn.execute(
            "SELECT slug FROM page_aliases WHERE page_id = %s ORDER BY slug", (page.id,)
        ).fetchall()
    return {
        "id": str(page.id),
        "workspace": ws.slug,
        "slug": page.slug,
        "title": page.title,
        "markdown": page.content,
        "properties": front,
        "revision": page.revision,
        "updated_at": page.updated_at,
        "aliases": [r["slug"] for r in aliases],
        "relations": relations(int(ws.id), page.id),
        "git_status": "synced" if page.git_revision == page.revision else "pending",
    }


def read_sections(user_id, args):
    _, page = page_for(user_id, args)
    offset = int(args.get("offset", 0))
    if offset < 0:
        raise ValueError("offset must be nonnegative")
    limit = bounded(args.get("limit"), 10, 100)
    chunks = meta.chunk_markdown(page.content)
    if args.get("heading"):
        chunks = [
            c for c in chunks if args["heading"].casefold() in [h.casefold() for h in c.headings]
        ]
    if args.get("newest_first"):
        chunks.reverse()
    selected = chunks[offset : offset + limit]
    return {
        "slug": page.slug,
        "revision": page.revision,
        "sections": [{"headings": c.headings, "text": c.text} for c in selected],
        "next_offset": offset + limit if offset + limit < len(chunks) else None,
    }


def set_metadata(user_id, args):
    ws, page = page_for(user_id, args)
    properties = args.get("properties")
    if not isinstance(properties, dict) or not properties:
        raise ValueError("properties must be a nonempty object")
    permitted = {
        "type",
        "status",
        "source",
        "source_revision",
        "observed_at",
        "valid_from",
        "valid_until",
        "reviewed_at",
        "external_id",
    }
    if properties.keys() - permitted:
        raise ValueError("Unsupported knowledge property")
    if "type" in properties and properties["type"] not in TYPES:
        raise ValueError("Unsupported knowledge type")
    if "status" in properties and properties["status"] not in STATES:
        raise ValueError("Unsupported knowledge status")
    for key, value in properties.items():
        if not isinstance(value, str) or "\n" in value or "\r" in value:
            raise ValueError("Knowledge properties must be single-line strings")
        if key.endswith("_at") or key in {"valid_from", "valid_until"}:
            datetime.fromisoformat(value)
    front, body = meta.parse_frontmatter(page.content)
    front.update(properties)
    if front.get("valid_from") and front.get("valid_until"):
        if datetime.fromisoformat(front["valid_from"]) > datetime.fromisoformat(
            front["valid_until"]
        ):
            raise ValueError("valid_until precedes valid_from")
    # Preserve unrelated frontmatter byte-for-byte, including fields unknown to this feature.
    raw_front, _ = meta._split_frontmatter(page.content)
    lines = raw_front.splitlines()[1:-1] if raw_front else []
    lines = [line for line in lines if line.partition(":")[0].strip().lower() not in properties]
    lines += [
        f"{key}: {json.dumps(value, ensure_ascii=False)}" for key, value in properties.items()
    ]
    content = "---\n" + "\n".join(lines) + "\n---\n" + body
    db.update_page(
        user_id,
        int(ws.id),
        page.slug,
        page.title,
        content,
        expected_revision=args.get("expected_revision", page.revision),
    )
    commit_current(user_id, ws, page.slug)
    return get_object(user_id, args)


def commit_current(user_id, ws, slug):
    from app import git_repo

    page = db.get_page(slug, int(ws.id))
    user = db.get_user_by_id(user_id)
    git_repo.commit_and_record(
        int(ws.id), ws.slug, page.slug, page.title, page.content, user.email if user else "user"
    )


def relate(user_id, args):
    ws, source = page_for(user_id, args)
    target = db.get_page(args.get("target", ""), int(ws.id))
    if target is None:
        raise ValueError("Target page not found")
    kind = args.get("kind")
    if kind not in RELATIONS:
        raise ValueError("Unsupported relation kind")
    evidence = args.get("evidence", "")
    if not isinstance(evidence, str) or len(evidence) > 4000:
        raise ValueError("Evidence must be text of at most 4000 characters")
    with db.connect() as conn:
        # Serialize relation changes with deletion of either endpoint.
        rows = conn.execute(
            "SELECT id FROM pages WHERE id = ANY(%s) AND deleted_at IS NULL ORDER BY id FOR UPDATE",
            ([source.id, target.id],),
        ).fetchall()
        if len(rows) != len({source.id, target.id}):
            raise ValueError("Page not found")
        conn.execute(
            "INSERT INTO knowledge_relations "
            "(source_id, target_id, kind, evidence, actor, created_at) "
            "VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (source_id, target_id, kind) DO NOTHING",
            (
                source.id,
                target.id,
                kind,
                evidence,
                access.actor.get() or f"user:{user_id}",
                db._now(),
            ),
        )
    return {"relations": relations(int(ws.id), source.id)}


def remove_relation(user_id, args):
    ws, page = page_for(user_id, args)
    with db.connect() as conn:
        row = conn.execute(
            "SELECT t.slug FROM knowledge_relations r JOIN pages t "
            "ON t.id = r.target_id WHERE r.id = %s AND r.source_id = %s",
            (int(args["relation_id"]), page.id),
        ).fetchone()
        if row is None:
            raise ValueError("Relation not found")
        access.require(ws.slug, "read", row["slug"])
        conn.execute(
            "DELETE FROM knowledge_relations WHERE id = %s AND source_id = %s",
            (int(args["relation_id"]), page.id),
        )
    return {"removed": True}


def add_alias(user_id, args):
    ws, page = page_for(user_id, args)
    alias = db.slugify(str(args.get("alias", "")))
    if not alias:
        raise ValueError("alias is required")
    with db.connect() as conn:
        conn.execute("SELECT pg_advisory_xact_lock(%s)", (int(ws.id),))
        existing = conn.execute(
            "SELECT id AS page_id FROM pages WHERE workspace_id = %s AND slug = %s UNION ALL "
            "SELECT page_id FROM page_aliases WHERE workspace_id = %s AND slug = %s",
            (ws.id, alias, ws.id, alias),
        ).fetchall()
        if any(r["page_id"] != page.id for r in existing):
            raise db.RevisionConflict("Alias already identifies a different entity")
        conn.execute(
            "INSERT INTO page_aliases (workspace_id, slug, page_id, created_at) "
            "VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING",
            (ws.id, alias, page.id, db._now()),
        )
        conn.execute(
            "UPDATE page_links SET dst_page_id = %s WHERE workspace_id = %s "
            "AND dst_slug = %s AND dst_page_id IS NULL",
            (page.id, ws.id, alias),
        )
    return {"id": str(page.id), "alias": alias, "slug": page.slug}


def eligible_slugs(workspace_id, args):
    """Apply metadata and graph constraints before either retriever ranks or limits."""
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT p.id, p.slug, m.frontmatter_json FROM pages p LEFT JOIN page_meta m "
            "ON m.page_id = p.id WHERE p.workspace_id = %s AND p.deleted_at IS NULL",
            (workspace_id,),
        ).fetchall()
        entity_ids = None
        if args.get("entity"):
            entity = db.get_page(args["entity"], workspace_id)
            if entity is None:
                return set()
            related = relations(workspace_id, entity.id)
            entity_ids = (
                {entity.id} | {r["source_id"] for r in related} | {r["target_id"] for r in related}
            )
    at = args.get("as_of")
    if at:
        at = instant(at)
    result = set()
    for row in rows:
        front = json.loads(row["frontmatter_json"] or "{}")
        if args.get("type") and str(front.get("type", "")).casefold() != args["type"].casefold():
            continue
        status = args.get("status")
        if status and front.get("status", "active") != status:
            continue
        if at and (
            front.get("valid_from")
            and instant(front["valid_from"]) > at
            or front.get("valid_until")
            and instant(front["valid_until"]) < at
        ):
            continue
        if entity_ids is not None and row["id"] not in entity_ids:
            continue
        result.add(row["slug"])
    return result


def query_context(user_id, args):
    query = str(args.get("query", "")).strip()
    if not query:
        raise ValueError("query is required")
    budget = bounded(args.get("budget"), 6000, 50000)
    limit = bounded(args.get("limit"), 100, 100)
    workspaces = args.get("workspaces") or [
        w.slug for w in db.list_workspaces(user_id) if access.allowed(w.slug, "read")
    ]
    if not isinstance(workspaces, list) or len(workspaces) > 20:
        raise ValueError("workspaces must be an array of at most 20 slugs")
    candidates = []
    modes = {}
    filters = {"status": "active", **args}
    for slug in dict.fromkeys(workspaces):
        ws = workspace_for(user_id, {"workspace": slug})
        access.require(ws.slug, "read")
        allowed = eligible_slugs(int(ws.id), filters)
        result = embeddings.rag_context(int(ws.id), query, budget=budget, allowed_slugs=allowed)
        modes[ws.slug] = result["mode"]
        for rank, chunk in enumerate(result["chunks"], 1):
            page = db.get_page(chunk["slug"], int(ws.id))
            if page is None or chunk["text"] not in page.content:
                continue
            front, _ = meta.parse_frontmatter(page.content)
            candidates.append(
                {
                    **chunk,
                    "workspace": ws.slug,
                    "revision": page.revision,
                    "properties": front,
                    "relations": relations(int(ws.id), page.id),
                    "rank": rank,
                }
            )
    candidates.sort(key=lambda c: (c["rank"], c["workspace"], c["slug"]))
    chunks, truncated = embeddings._pack_context(candidates, budget, limit)
    return {"query": query, "modes": modes, "chunks": chunks, "truncated": truncated}


def retry_version(user_id, args):
    ws, page = page_for(user_id, args)
    commit_current(user_id, ws, page.slug)
    return get_object(user_id, args)


def knowledge_history(user_id, args):
    _, page = page_for(user_id, args)
    offset = int(args.get("offset", 0))
    if offset < 0:
        raise ValueError("offset must be nonnegative")
    limit = bounded(args.get("limit"), 20, 100)
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT revision, title, content AS markdown, actor, recorded_at "
            "FROM knowledge_revisions WHERE page_id = %s ORDER BY revision DESC "
            "LIMIT %s OFFSET %s",
            (page.id, limit + 1, offset),
        ).fetchall()
    return {
        "id": str(page.id),
        "revisions": rows[:limit],
        "next_offset": offset + limit if len(rows) > limit else None,
    }


HANDLERS = {
    "get_knowledge_history": knowledge_history,
    "get_knowledge_object": get_object,
    "read_page_sections": read_sections,
    "set_knowledge_metadata": set_metadata,
    "relate_knowledge": relate,
    "remove_knowledge_relation": remove_relation,
    "add_entity_alias": add_alias,
    "query_knowledge_context": query_context,
    "retry_page_version": retry_version,
}


def rest_call(request, name, arguments):
    uid = getattr(request.state, "user_id", None)
    if uid is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    if name not in HANDLERS:
        raise HTTPException(status_code=404, detail="Unknown knowledge operation")
    try:
        authorize_tool(uid, name, arguments)
        return HANDLERS[name](uid, arguments)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except db.RevisionConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
