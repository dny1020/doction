"""Minimal graph requirements for newly typed knowledge; legacy pages stay editable."""

from app import access, meta

REQUIRED = {"Decision": ("belongs_to", "Project"), "Incident": ("affects", "Service")}
KINDS = {"affects", "belongs_to", "derived_from", "supersedes", "decided_by", "related_to"}


def page_type(content):
    value = meta.page_type(content)
    return (
        {
            "decision": "Decision",
            "incident": "Incident",
            "project": "Project",
            "service": "Service",
        }.get(value.casefold(), value)
        if value
        else None
    )


def normalize(relations):
    if relations is None:
        return []
    if not isinstance(relations, list) or len(relations) > 100:
        raise ValueError("relations must be an array of at most 100 objects")
    result = {}
    for relation in relations:
        if not isinstance(relation, dict) or relation.keys() - {"kind", "target", "evidence"}:
            raise ValueError("Each relation needs kind, target and optional evidence")
        kind, target, evidence = (relation.get(k, "") for k in ("kind", "target", "evidence"))
        if not isinstance(kind, str) or kind not in KINDS:
            raise ValueError("Unsupported relation kind")
        if not isinstance(target, str) or not target.strip():
            raise ValueError("Relation target must be an existing page slug")
        if not isinstance(evidence, str) or len(evidence) > 4000:
            raise ValueError("Evidence must be text of at most 4000 characters")
        key = kind, target.strip()
        if key in result and result[key]["evidence"] != evidence:
            raise ValueError("Conflicting evidence for the same relation")
        result[key] = {"kind": kind, "target": target.strip(), "evidence": evidence}
    return [result[key] for key in sorted(result)]


def attach(conn, workspace_id, source_id, slug, relations, user_id, now):
    if not relations:
        return
    workspace = conn.execute(
        "SELECT slug FROM workspaces WHERE id = %s", (workspace_id,)
    ).fetchone()["slug"]
    access.require(workspace, "relate", slug)
    for relation in relations:
        access.require(workspace, "read", relation["target"])
        target = conn.execute(
            "SELECT p.id FROM pages p WHERE p.workspace_id = %s AND p.deleted_at IS NULL "
            "AND (p.slug = %s OR EXISTS (SELECT 1 FROM page_aliases a "
            "WHERE a.page_id = p.id AND a.workspace_id = %s AND a.slug = %s))",
            (workspace_id, relation["target"], workspace_id, relation["target"]),
        ).fetchone()
        if target is None:
            raise ValueError(f"Target page not found: {relation['target']}")
        conn.execute(
            "INSERT INTO knowledge_relations "
            "(source_id, target_id, kind, evidence, actor, created_at) "
            "VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
            (
                source_id,
                target["id"],
                relation["kind"],
                relation["evidence"],
                access.actor.get() or f"user:{user_id}",
                now,
            ),
        )
    validate(conn, source_id)


def validate(conn, page_id):
    from app import db

    page = conn.execute(
        "SELECT content, graph_required FROM pages WHERE id = %s AND deleted_at IS NULL", (page_id,)
    ).fetchone()
    if page is None or not page["graph_required"]:
        return
    requirement = REQUIRED.get(page_type(page["content"]))
    if requirement is None:
        return
    kind, target_type = requirement
    targets = conn.execute(
        "SELECT t.content FROM knowledge_relations r JOIN pages t ON t.id = r.target_id "
        "WHERE r.source_id = %s AND r.kind = %s AND t.deleted_at IS NULL",
        (page_id, kind),
    ).fetchall()
    if not any(page_type(t["content"]) == target_type for t in targets):
        raise db.RelationRequired(
            f"{meta.page_type(page['content'])} requires {kind} -> {target_type}. "
            "Create it with create_page relations=[{kind, target}], using an existing "
            f"{target_type} page. For an existing page, add the relation with "
            "relate_knowledge before setting its type. Parenting and [[wikilinks]] do not count."
        )


def validate_dependents(conn, page_id):
    sources = conn.execute(
        "SELECT DISTINCT source_id FROM knowledge_relations WHERE target_id = %s", (page_id,)
    ).fetchall()
    for source in sources:
        validate(conn, source["source_id"])


def read_context(workspace_id, page):
    from app import db, knowledge

    with db.connect() as conn:
        required = conn.execute(
            "SELECT graph_required FROM pages WHERE id = %s", (page.id,)
        ).fetchone()["graph_required"]
    edges = knowledge.relations(workspace_id, page.id)
    requirement = REQUIRED.get(page_type(page.content))
    return {
        "relations": edges[:20],
        "truncated": len(edges) > 20,
        "enforced": bool(required and requirement),
        "required_relation": {"kind": requirement[0], "target_type": requirement[1]}
        if requirement
        else None,
        "guidance": "Use get_linked_knowledge for wikilinks; query_knowledge_context with entity="
        f"'{page.slug}' for typed neighbors and evidence. "
        "Create typed objects with explicit relations; nesting is hierarchy only.",
    }
