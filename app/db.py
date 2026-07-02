from __future__ import annotations

import json
import os
import re
import threading
import unicodedata
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app import meta
from app.models import (
    ApiToken,
    ChunkVector,
    EmbedTarget,
    ExtractedPage,
    Member,
    Page,
    PageMeta,
    PageNode,
    PageRef,
    RelatedPage,
    SearchHit,
    User,
    Workspace,
)

DEFAULT_DATABASE_URL = "postgresql://doction:doction@localhost:5432/doction"
DEFAULT_DATA_DIR = "data"
DEFAULT_WORKSPACE_NAME = "Personal"
DEFAULT_WORKSPACE_SLUG = "personal"

_pool: ConnectionPool | None = None
_pool_lock = threading.Lock()


def database_url() -> str:
    return os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)


def masked_database_url() -> str:
    """`database_url()` sin credenciales — seguro para logs."""
    parts = urlsplit(database_url())
    if parts.password is None:
        return urlunsplit(parts)
    host = f"{parts.hostname or ''}"
    if parts.port:
        host += f":{parts.port}"
    netloc = f"{parts.username}:***@{host}" if parts.username else f"***@{host}"
    return urlunsplit(parts._replace(netloc=netloc))


def data_dir() -> Path:
    """Directorio para el repo git de páginas y los uploads (independiente de la BD)."""
    d = Path(os.environ.get("DATA_DIR", DEFAULT_DATA_DIR))
    d.mkdir(parents=True, exist_ok=True)
    return d


def _get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                _pool = ConnectionPool(
                    database_url(),
                    min_size=1,
                    max_size=10,
                    kwargs={"row_factory": dict_row},
                    open=True,
                )
    return _pool


def connect():
    """Conexión del pool como context manager: commit al salir, rollback si hay excepción."""
    return _get_pool().connection()


def reset_pool() -> None:
    """Cierra el pool actual; el próximo connect() crea uno nuevo. Solo para tests."""
    global _pool
    with _pool_lock:
        if _pool is not None:
            _pool.close()
            _pool = None


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


# ── Conversión de filas a dataclasses ────────────────────────────────────────
# Cada consulta devuelve un dict (row_factory=dict_row). Estas funciones lo pasan
# a un dato con nombre (las clases de app/models.py), usando .get(...) para que si
# una consulta no seleccionó cierta columna, ese campo quede en None.

def _to_user(row: dict) -> User:
    return User(
        id=row["id"],
        email=row["email"],
        password_hash=row["password_hash"],
        created_at=row["created_at"],
        display_name=row.get("display_name"),
        avatar_color=row.get("avatar_color"),
    )


def _to_workspace(row: dict) -> Workspace:
    return Workspace(
        id=row["id"],
        slug=row["slug"],
        name=row["name"],
        role=row.get("role"),
        user_id=row.get("user_id"),
        created_at=row.get("created_at"),
    )


def _to_page(row: dict) -> Page:
    return Page(
        id=row.get("id"),
        slug=row.get("slug", ""),
        title=row.get("title", ""),
        content=row.get("content", ""),
        user_id=row.get("user_id"),
        workspace_id=row.get("workspace_id"),
        parent_id=row.get("parent_id"),
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
        git_commit=row.get("git_commit"),
        embed_dirty=row.get("embed_dirty"),
        updated_by=row.get("updated_by"),
        deleted_at=row.get("deleted_at"),
        parent_slug=row.get("parent_slug"),
        parent_title=row.get("parent_title"),
        updated_by_email=row.get("updated_by_email"),
        updated_by_name=row.get("updated_by_name"),
    )


# ── Esquema ───────────────────────────────────────────────────────────────────
# Esquema final directo (sin el historial de migraciones de la era SQLite: no hay
# datos legacy que reconciliar porque una base Postgres nueva nace ya con esta forma
# — ver scripts/migrate_sqlite_to_postgres.py para la migración única de datos
# existentes). `search_vector` es una columna generada: Postgres la mantiene
# sincronizada solo, sin triggers (a diferencia de los 3 triggers que requería FTS5).
SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS users (
        id            BIGSERIAL PRIMARY KEY,
        email         TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        created_at    TEXT NOT NULL,
        display_name  TEXT,
        avatar_color  TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS workspaces (
        id         BIGSERIAL PRIMARY KEY,
        user_id    BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        slug       TEXT NOT NULL UNIQUE,
        name       TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS workspace_members (
        workspace_id BIGINT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
        user_id      BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        role         TEXT NOT NULL DEFAULT 'member',
        created_at   TEXT NOT NULL,
        PRIMARY KEY (workspace_id, user_id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS workspace_members_user_idx ON workspace_members(user_id)",
    """
    CREATE TABLE IF NOT EXISTS api_tokens (
        id           BIGSERIAL PRIMARY KEY,
        user_id      BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        name         TEXT NOT NULL,
        token_hash   TEXT NOT NULL UNIQUE,
        created_at   TEXT NOT NULL,
        last_used_at TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS pages (
        id            BIGSERIAL PRIMARY KEY,
        user_id       BIGINT REFERENCES users(id) ON DELETE CASCADE,
        workspace_id  BIGINT REFERENCES workspaces(id) ON DELETE CASCADE,
        parent_id     BIGINT REFERENCES pages(id)
                      ON DELETE SET NULL DEFERRABLE INITIALLY DEFERRED,
        slug          TEXT NOT NULL,
        title         TEXT NOT NULL,
        content       TEXT NOT NULL,
        created_at    TEXT NOT NULL,
        updated_at    TEXT NOT NULL,
        git_commit    TEXT,
        embed_dirty   INTEGER NOT NULL DEFAULT 1,
        updated_by    BIGINT REFERENCES users(id),
        deleted_at    TEXT,
        search_vector tsvector GENERATED ALWAYS AS (
            setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
            setweight(to_tsvector('english', coalesce(content, '')), 'B')
        ) STORED
    )
    """,
    "CREATE UNIQUE INDEX IF NOT EXISTS pages_workspace_slug_idx ON pages(workspace_id, slug)",
    "CREATE INDEX IF NOT EXISTS pages_user_idx ON pages(user_id)",
    "CREATE INDEX IF NOT EXISTS pages_parent_idx ON pages(parent_id)",
    "CREATE INDEX IF NOT EXISTS pages_search_idx ON pages USING GIN(search_vector)",
    """
    CREATE TABLE IF NOT EXISTS page_meta (
        page_id          BIGINT PRIMARY KEY REFERENCES pages(id) ON DELETE CASCADE,
        type             TEXT,
        frontmatter_json TEXT NOT NULL DEFAULT '{}'
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS page_tags (
        id      BIGSERIAL PRIMARY KEY,
        page_id BIGINT NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
        tag     TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS page_tags_tag_idx ON page_tags(tag)",
    "CREATE INDEX IF NOT EXISTS page_tags_page_idx ON page_tags(page_id)",
    """
    CREATE TABLE IF NOT EXISTS page_links (
        id           BIGSERIAL PRIMARY KEY,
        src_page_id  BIGINT NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
        dst_slug     TEXT NOT NULL,
        workspace_id BIGINT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS page_links_dst_idx ON page_links(workspace_id, dst_slug)",
    "CREATE INDEX IF NOT EXISTS page_links_src_idx ON page_links(src_page_id)",
    """
    CREATE TABLE IF NOT EXISTS page_chunks (
        id           BIGSERIAL PRIMARY KEY,
        page_id      BIGINT NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
        workspace_id BIGINT NOT NULL,
        ord          INTEGER NOT NULL,
        text         TEXT NOT NULL,
        vector       BYTEA NOT NULL,
        model        TEXT NOT NULL,
        created_at   TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS page_chunks_ws_idx ON page_chunks(workspace_id)",
    "CREATE INDEX IF NOT EXISTS page_chunks_page_idx ON page_chunks(page_id)",
]


def _unique_workspace_slug(
    conn,
    base: str,
    *,
    ignore_id: int | None = None,
) -> str:
    """Slug único a nivel global (los workspaces se comparten entre usuarios, y el slug
    es además el nombre de carpeta en el repo git, así que no puede colisionar)."""
    candidate = base
    suffix = 1
    while True:
        row = conn.execute(
            "SELECT id FROM workspaces WHERE slug = %s",
            (candidate,),
        ).fetchone()
        if row is None or row["id"] == ignore_id:
            return candidate
        suffix += 1
        candidate = f"{base}-{suffix}"


def _ensure_default_workspaces(conn) -> None:
    missing = conn.execute(
        """
        SELECT u.id
        FROM users u
        LEFT JOIN workspaces w ON w.user_id = u.id
        GROUP BY u.id
        HAVING COUNT(w.id) = 0
        """
    ).fetchall()
    for row in missing:
        user_id = int(row["id"])
        slug = _unique_workspace_slug(conn, DEFAULT_WORKSPACE_SLUG)
        conn.execute(
            "INSERT INTO workspaces (user_id, slug, name, created_at) VALUES (%s, %s, %s, %s)",
            (user_id, slug, DEFAULT_WORKSPACE_NAME, _now()),
        )


def _ensure_member_owners(conn) -> None:
    """Backfill: el creador de cada workspace es 'owner' en workspace_members. Idempotente."""
    conn.execute(
        """
        INSERT INTO workspace_members (workspace_id, user_id, role, created_at)
        SELECT w.id, w.user_id, 'owner', %s
        FROM workspaces w
        ON CONFLICT (workspace_id, user_id) DO NOTHING
        """,
        (_now(),),
    )


def _index_page_meta(conn, page_id: int, workspace_id: int, content: str) -> None:
    """Reconstruye frontmatter/tags/enlaces de una página. Idempotente por page_id."""
    fm, _ = meta.parse_frontmatter(content)
    conn.execute("DELETE FROM page_meta WHERE page_id = %s", (page_id,))
    conn.execute(
        "INSERT INTO page_meta (page_id, type, frontmatter_json) VALUES (%s, %s, %s)",
        (page_id, meta.page_type(content), json.dumps(fm, ensure_ascii=False)),
    )

    conn.execute("DELETE FROM page_tags WHERE page_id = %s", (page_id,))
    tags = [(page_id, tag) for tag in meta.extract_tags(content)]
    if tags:
        conn.cursor().executemany(
            "INSERT INTO page_tags (page_id, tag) VALUES (%s, %s)", tags
        )

    conn.execute("DELETE FROM page_links WHERE src_page_id = %s", (page_id,))
    seen: set[str] = set()
    edges: list[tuple[int, str, int]] = []
    for target in meta.extract_links(content):
        dst = slugify(target)
        if dst not in seen:
            seen.add(dst)
            edges.append((page_id, dst, workspace_id))
    if edges:
        conn.cursor().executemany(
            "INSERT INTO page_links (src_page_id, dst_slug, workspace_id) VALUES (%s, %s, %s)",
            edges,
        )

    # El contenido cambió: marcar para reembedding (lo procesa el worker async).
    conn.execute("UPDATE pages SET embed_dirty = 1 WHERE id = %s", (page_id,))


def init_db() -> None:
    """Crea el esquema (idempotente) y corre los backfills defensivos."""
    with connect() as conn:
        for stmt in SCHEMA_STATEMENTS:
            conn.execute(stmt)
        _ensure_default_workspaces(conn)
        _ensure_member_owners(conn)


def slugify(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_text).strip("-").lower()
    return slug or "page"


def unique_slug(
    conn,
    base: str,
    *,
    workspace_id: int,
    ignore_id: int | None = None,
) -> str:
    """Slug único en el workspace; en colisión agrega -2, -3, …"""
    candidate = base
    suffix = 1
    while True:
        row = conn.execute(
            "SELECT id FROM pages WHERE slug = %s AND workspace_id = %s",
            (candidate, workspace_id),
        ).fetchone()
        if row is None or row["id"] == ignore_id:
            return candidate
        suffix += 1
        candidate = f"{base}-{suffix}"


def create_user(email: str, password_hash: str) -> int:
    with connect() as conn:
        row = conn.execute(
            "INSERT INTO users (email, password_hash, created_at) VALUES (%s, %s, %s) "
            "RETURNING id",
            (email, password_hash, _now()),
        ).fetchone()
        return int(row["id"])


def has_users() -> bool:
    """True si ya existe al menos un usuario (para el flujo de primer arranque)."""
    with connect() as conn:
        return conn.execute("SELECT 1 FROM users LIMIT 1").fetchone() is not None


def get_user_by_email(email: str) -> User | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = %s", (email,)).fetchone()
        return _to_user(row) if row else None


def get_user_by_id(user_id: int) -> User | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = %s", (user_id,)).fetchone()
        return _to_user(row) if row else None


def update_user_profile(user_id: int, display_name: str | None, avatar_color: str | None) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE users SET display_name = %s, avatar_color = %s WHERE id = %s",
            (display_name or None, avatar_color or None, user_id),
        )


def update_user_password(user_id: int, password_hash: str) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE users SET password_hash = %s WHERE id = %s",
            (password_hash, user_id),
        )


def list_workspaces(user_id: int) -> list[Workspace]:
    """Workspaces de los que el usuario es miembro (propios y compartidos), con su rol."""
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT w.id, w.slug, w.name, m.role
            FROM workspaces w
            JOIN workspace_members m ON m.workspace_id = w.id
            WHERE m.user_id = %s
            ORDER BY w.created_at, w.id
            """,
            (user_id,),
        ).fetchall()
        return [_to_workspace(row) for row in rows]


def get_workspace_by_slug(user_id: int, slug: str) -> Workspace | None:
    """Resuelve un workspace por slug solo si el usuario es miembro."""
    with connect() as conn:
        row = conn.execute(
            """
            SELECT w.id, w.slug, w.name, m.role
            FROM workspaces w
            JOIN workspace_members m ON m.workspace_id = w.id
            WHERE m.user_id = %s AND w.slug = %s
            """,
            (user_id, slug),
        ).fetchone()
        return _to_workspace(row) if row else None


def create_workspace(user_id: int, name: str) -> str:
    name = name.strip() or "Workspace"
    base = slugify(name)
    now = _now()
    with connect() as conn:
        slug = _unique_workspace_slug(conn, base)
        row = conn.execute(
            "INSERT INTO workspaces (user_id, slug, name, created_at) VALUES (%s, %s, %s, %s) "
            "RETURNING id",
            (user_id, slug, name, now),
        ).fetchone()
        conn.execute(
            "INSERT INTO workspace_members (workspace_id, user_id, role, created_at) "
            "VALUES (%s, %s, 'owner', %s) ON CONFLICT (workspace_id, user_id) DO NOTHING",
            (int(row["id"]), user_id, now),
        )
        return slug


def rename_workspace(user_id: int, slug: str, name: str) -> bool:
    name = name.strip()
    if not name:
        return False
    with connect() as conn:
        cur = conn.execute(
            "UPDATE workspaces SET name = %s WHERE user_id = %s AND slug = %s",
            (name, user_id, slug),
        )
        return cur.rowcount > 0


def delete_workspace(user_id: int, slug: str) -> bool:
    """Borra el workspace y sus páginas. No borra el último que quede."""
    with connect() as conn:
        count = conn.execute(
            "SELECT COUNT(*) AS n FROM workspaces WHERE user_id = %s", (user_id,)
        ).fetchone()["n"]
        if count <= 1:
            return False
        ws = conn.execute(
            "SELECT id FROM workspaces WHERE user_id = %s AND slug = %s",
            (user_id, slug),
        ).fetchone()
        if ws is None:
            return False
        conn.execute("DELETE FROM pages WHERE workspace_id = %s", (ws["id"],))
        conn.execute("DELETE FROM workspaces WHERE id = %s", (ws["id"],))
        return True


def get_member_role(user_id: int, workspace_id: int) -> str | None:
    """Rol del usuario en el workspace ('owner'|'member'), o None si no es miembro."""
    with connect() as conn:
        row = conn.execute(
            "SELECT role FROM workspace_members WHERE workspace_id = %s AND user_id = %s",
            (workspace_id, user_id),
        ).fetchone()
        return row["role"] if row else None


def add_workspace_member(workspace_id: int, user_id: int, role: str = "member") -> None:
    role = role if role in ("owner", "member") else "member"
    with connect() as conn:
        conn.execute(
            "INSERT INTO workspace_members (workspace_id, user_id, role, created_at) "
            "VALUES (%s, %s, %s, %s) ON CONFLICT (workspace_id, user_id) DO NOTHING",
            (workspace_id, user_id, role, _now()),
        )


def remove_workspace_member(workspace_id: int, user_id: int) -> bool:
    with connect() as conn:
        cur = conn.execute(
            "DELETE FROM workspace_members WHERE workspace_id = %s AND user_id = %s",
            (workspace_id, user_id),
        )
        return cur.rowcount > 0


def list_workspace_members(workspace_id: int) -> list[Member]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT u.id AS user_id, u.email, u.display_name, m.role, m.created_at
            FROM workspace_members m
            JOIN users u ON u.id = m.user_id
            WHERE m.workspace_id = %s
            ORDER BY (m.role = 'owner') DESC, m.created_at, u.id
            """,
            (workspace_id,),
        ).fetchall()
        return [
            Member(
                user_id=row["user_id"],
                email=row["email"],
                display_name=row["display_name"],
                role=row["role"],
                created_at=row["created_at"],
            )
            for row in rows
        ]


def ensure_default_workspace(user_id: int) -> Workspace:
    with connect() as conn:
        workspace = conn.execute(
            "SELECT id, slug, name FROM workspaces WHERE user_id = %s ORDER BY id LIMIT 1",
            (user_id,),
        ).fetchone()
        if workspace is None:
            now = _now()
            slug = _unique_workspace_slug(conn, DEFAULT_WORKSPACE_SLUG)
            row = conn.execute(
                "INSERT INTO workspaces (user_id, slug, name, created_at) "
                "VALUES (%s, %s, %s, %s) RETURNING id",
                (user_id, slug, DEFAULT_WORKSPACE_NAME, now),
            ).fetchone()
            conn.execute(
                "INSERT INTO workspace_members (workspace_id, user_id, role, created_at) "
                "VALUES (%s, %s, 'owner', %s) ON CONFLICT (workspace_id, user_id) DO NOTHING",
                (int(row["id"]), user_id, now),
            )
            workspace = conn.execute(
                "SELECT id, slug, name FROM workspaces WHERE user_id = %s AND slug = %s",
                (user_id, slug),
            ).fetchone()
        if workspace is None:
            raise RuntimeError("Failed to create default workspace")
        conn.execute(
            "UPDATE pages SET workspace_id = %s WHERE user_id = %s AND workspace_id IS NULL",
            (workspace["id"], user_id),
        )
        return _to_workspace(workspace)


def claim_unowned_pages(user_id: int, workspace_id: int) -> int:
    with connect() as conn:
        cur = conn.execute(
            "UPDATE pages SET user_id = %s, workspace_id = %s WHERE user_id IS NULL",
            (user_id, workspace_id),
        )
        return cur.rowcount


def list_pages_tree(user_id: int, workspace_id: int) -> list[PageNode]:
    """Lista plana en orden DFS con campo depth para renderizar el árbol en la sidebar."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, slug, title, parent_id FROM pages "
            "WHERE workspace_id = %s AND deleted_at IS NULL ORDER BY created_at, id",
            (workspace_id,),
        ).fetchall()

    by_id = {}
    for r in rows:
        by_id[r["id"]] = r
    children: dict[int, list] = {}
    roots = []
    for r in rows:
        pid = r["parent_id"]
        if pid is None or pid not in by_id:
            roots.append(r)
        else:
            children.setdefault(int(pid), []).append(r)

    result: list[PageNode] = []

    def _dfs(node, depth: int) -> None:
        result.append(PageNode(slug=node["slug"], title=node["title"], depth=depth))
        for child in children.get(int(node["id"]), []):
            _dfs(child, depth + 1)

    for root in roots:
        _dfs(root, 0)

    return result


def get_page(slug: str, user_id: int, workspace_id: int) -> Page | None:
    # El acceso lo garantiza la membresía al resolver el workspace; aquí basta workspace_id.
    with connect() as conn:
        row = conn.execute(
            """
            SELECT p.*, parent.slug AS parent_slug, parent.title AS parent_title,
                   editor.email AS updated_by_email, editor.display_name AS updated_by_name
            FROM pages p
            LEFT JOIN pages parent ON parent.id = p.parent_id
            LEFT JOIN users editor ON editor.id = p.updated_by
            WHERE p.slug = %s AND p.workspace_id = %s AND p.deleted_at IS NULL
            """,
            (slug, workspace_id),
        ).fetchone()
        return _to_page(row) if row else None


def get_ancestors(page_id: int, user_id: int, workspace_id: int) -> list[PageRef]:
    """Cadena de ancestros desde la raíz hasta el padre directo (sin incluir la página)."""
    chain: list[PageRef] = []
    with connect() as conn:
        row = conn.execute(
            "SELECT parent_id FROM pages WHERE id = %s AND workspace_id = %s",
            (page_id, workspace_id),
        ).fetchone()
        parent_id = row["parent_id"] if row else None
        seen: set[int] = set()
        while parent_id is not None and parent_id not in seen:
            seen.add(parent_id)
            parent = conn.execute(
                "SELECT id, slug, title, parent_id FROM pages "
                "WHERE id = %s AND workspace_id = %s AND deleted_at IS NULL",
                (parent_id, workspace_id),
            ).fetchone()
            if parent is None:
                break
            chain.append(PageRef(slug=parent["slug"], title=parent["title"]))
            parent_id = parent["parent_id"]
    chain.reverse()
    return chain


def _resolve_parent_id(
    conn,
    parent_slug: str | None,
    *,
    user_id: int,
    workspace_id: int,
    ignore_id: int | None = None,
) -> int | None:
    if not parent_slug:
        return None
    row = conn.execute(
        "SELECT id FROM pages WHERE slug = %s AND workspace_id = %s AND deleted_at IS NULL",
        (parent_slug, workspace_id),
    ).fetchone()
    if row is None:
        return None
    parent_id = int(row["id"])
    if ignore_id is not None and parent_id == ignore_id:
        return None
    return parent_id


def create_page(
    user_id: int,
    workspace_id: int,
    title: str,
    content: str,
    *,
    parent_slug: str | None = None,
    requested_slug: str | None = None,
) -> str:
    title = title.strip() or "Untitled"
    base_source = requested_slug.strip() if requested_slug else title
    base_slug = slugify(base_source)
    now = _now()

    with connect() as conn:
        parent_id = _resolve_parent_id(
            conn,
            parent_slug,
            user_id=user_id,
            workspace_id=workspace_id,
        )
        slug = unique_slug(conn, base_slug, workspace_id=workspace_id)
        row = conn.execute(
            """
            INSERT INTO pages (
                user_id, workspace_id, parent_id, slug, title, content,
                created_at, updated_at, updated_by
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (user_id, workspace_id, parent_id, slug, title, content, now, now, user_id),
        ).fetchone()
        _index_page_meta(conn, int(row["id"]), workspace_id, content)
        return slug


def update_page(user_id: int, workspace_id: int, slug: str, title: str, content: str) -> str | None:
    """Actualiza una página manteniendo el slug estable; devuelve slug o None si no existe."""
    title = title.strip() or "Untitled"
    with connect() as conn:
        row = conn.execute(
            "SELECT id FROM pages WHERE slug = %s AND workspace_id = %s AND deleted_at IS NULL",
            (slug, workspace_id),
        ).fetchone()
        if row is None:
            return None
        conn.execute(
            "UPDATE pages SET title = %s, content = %s, updated_at = %s, updated_by = %s "
            "WHERE id = %s",
            (title, content, _now(), user_id, row["id"]),
        )
        _index_page_meta(conn, int(row["id"]), workspace_id, content)
        return slug


def delete_page(user_id: int, workspace_id: int, slug: str) -> bool:
    """Soft-delete: mueve la página a la papelera (deleted_at = now). Recuperable.

    No se borra el archivo del repo git ni los datos derivados: solo se marca para que
    deje de aparecer en listados, búsqueda y enlaces. El contenido sigue en la fila."""
    with connect() as conn:
        cur = conn.execute(
            "UPDATE pages SET deleted_at = %s WHERE slug = %s AND workspace_id = %s "
            "AND deleted_at IS NULL",
            (_now(), slug, workspace_id),
        )
        return cur.rowcount > 0


def list_deleted_pages(user_id: int, workspace_id: int) -> list[Page]:
    """Páginas en la papelera del workspace, más recientes primero."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT slug, title, deleted_at FROM pages "
            "WHERE workspace_id = %s AND deleted_at IS NOT NULL "
            "ORDER BY deleted_at DESC",
            (workspace_id,),
        ).fetchall()
        return [_to_page(row) for row in rows]


def restore_page(user_id: int, workspace_id: int, slug: str) -> bool:
    """Saca una página de la papelera (deleted_at = NULL)."""
    with connect() as conn:
        cur = conn.execute(
            "UPDATE pages SET deleted_at = NULL WHERE slug = %s AND workspace_id = %s "
            "AND deleted_at IS NOT NULL",
            (slug, workspace_id),
        )
        return cur.rowcount > 0


def purge_page(user_id: int, workspace_id: int, slug: str) -> bool:
    """Borra definitivamente una página que ya está en la papelera (hard delete).

    El CASCADE limpia meta/tags/links/chunks."""
    with connect() as conn:
        cur = conn.execute(
            "DELETE FROM pages WHERE slug = %s AND workspace_id = %s AND deleted_at IS NOT NULL",
            (slug, workspace_id),
        )
        return cur.rowcount > 0


def pages_for_export(workspace_id: int) -> list[Page]:
    """Páginas vivas de un workspace (slug, title, content) para exportar a markdown."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT slug, title, content FROM pages "
            "WHERE workspace_id = %s AND deleted_at IS NULL ORDER BY slug",
            (workspace_id,),
        ).fetchall()
        return [_to_page(row) for row in rows]


def list_child_pages(user_id: int, workspace_id: int, parent_id: int) -> list[Page]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT slug, title, updated_at FROM pages "
            "WHERE workspace_id = %s AND parent_id = %s AND deleted_at IS NULL "
            "ORDER BY updated_at DESC",
            (workspace_id, parent_id),
        ).fetchall()
        return [_to_page(row) for row in rows]


def _fts_query(raw: str) -> str:
    """Convierte input de usuario en un tsquery de prefijos seguro (equivalente al MATCH
    de prefijos de FTS5). Los términos ya vienen filtrados a \\w+, así que `term:*` es
    siempre sintaxis válida de tsquery — no hay riesgo de inyección."""
    terms = re.findall(r"[\w]+", raw, flags=re.UNICODE)
    if not terms:
        return ""
    return " & ".join(f"{term}:*" for term in terms)


def search_pages(
    user_id: int,
    workspace_id: int,
    query: str,
    limit: int = 20,
) -> list[SearchHit]:
    match = _fts_query(query)
    if not match:
        return []
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT p.slug, p.title,
                   ts_headline(
                       'english', p.title || ' ' || p.content, to_tsquery(%s),
                       'StartSel=<mark>, StopSel=</mark>, MaxWords=12, MinWords=1, '
                       'MaxFragments=1'
                   ) AS snippet
            FROM pages p
            WHERE p.search_vector @@ to_tsquery(%s) AND p.workspace_id = %s
              AND p.deleted_at IS NULL
            ORDER BY ts_rank(p.search_vector, to_tsquery(%s)) DESC
            LIMIT %s
            """,
            (match, match, workspace_id, match, limit),
        ).fetchall()
        return [
            SearchHit(slug=row["slug"], title=row["title"], snippet=row["snippet"])
            for row in rows
        ]


def _page_tags(conn, page_id: int) -> list[str]:
    rows = conn.execute(
        "SELECT tag FROM page_tags WHERE page_id = %s ORDER BY id", (page_id,)
    ).fetchall()
    return [r["tag"] for r in rows]


def get_page_meta(user_id: int, workspace_id: int, slug: str) -> PageMeta | None:
    """Frontmatter + tags de una página, o None si no existe."""
    with connect() as conn:
        row = conn.execute(
            "SELECT id FROM pages WHERE slug = %s AND workspace_id = %s AND deleted_at IS NULL",
            (slug, workspace_id),
        ).fetchone()
        if row is None:
            return None
        meta_row = conn.execute(
            "SELECT type, frontmatter_json FROM page_meta WHERE page_id = %s", (row["id"],)
        ).fetchone()
        fm = json.loads(meta_row["frontmatter_json"]) if meta_row else {}
        return PageMeta(
            slug=slug,
            type=meta_row["type"] if meta_row else None,
            tags=_page_tags(conn, int(row["id"])),
            frontmatter=fm,
        )


def extract_pages(
    user_id: int,
    workspace_id: int,
    *,
    page_type: str | None = None,
    tag: str | None = None,
    limit: int = 200,
) -> list[ExtractedPage]:
    """Filtra páginas por `type` y/o `tag` del frontmatter; estructura sin LLM."""
    joins = ""
    params: list = []
    if tag:
        joins = "JOIN page_tags t ON t.page_id = p.id AND t.tag = %s"
        params.append(meta.normalize_tag(tag))
    where = ["p.workspace_id = %s", "p.deleted_at IS NULL"]
    params.append(workspace_id)
    if page_type:
        where.append("m.type = %s")
        params.append(page_type)
    params.append(limit)
    sql = f"""
        SELECT p.id, p.slug, p.title, p.updated_at,
               m.type AS type, m.frontmatter_json
        FROM pages p
        LEFT JOIN page_meta m ON m.page_id = p.id
        {joins}
        WHERE {" AND ".join(where)}
        ORDER BY p.updated_at DESC
        LIMIT %s
    """
    with connect() as conn:
        rows = conn.execute(sql, params).fetchall()
        return [
            ExtractedPage(
                slug=r["slug"],
                title=r["title"],
                type=r["type"],
                tags=_page_tags(conn, int(r["id"])),
                frontmatter=json.loads(r["frontmatter_json"] or "{}"),
                updated_at=r["updated_at"],
            )
            for r in rows
        ]


def backlinks(user_id: int, workspace_id: int, slug: str) -> list[PageRef]:
    """Páginas que enlazan a `slug` vía wikilink [[slug]]."""
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT p.slug, p.title
            FROM page_links l
            JOIN pages p ON p.id = l.src_page_id
            WHERE l.workspace_id = %s AND l.dst_slug = %s AND p.deleted_at IS NULL
            ORDER BY p.title
            """,
            (workspace_id, slug),
        ).fetchall()
        return [PageRef(slug=r["slug"], title=r["title"]) for r in rows]


def related_pages(
    user_id: int, workspace_id: int, slug: str, limit: int = 10
) -> list[RelatedPage] | None:
    """Vecinos por solape de tags (desc), o None si la página no existe."""
    with connect() as conn:
        page = conn.execute(
            "SELECT id FROM pages WHERE slug = %s AND workspace_id = %s AND deleted_at IS NULL",
            (slug, workspace_id),
        ).fetchone()
        if page is None:
            return None
        rows = conn.execute(
            """
            SELECT p.slug, p.title, COUNT(*) AS shared
            FROM page_tags t1
            JOIN page_tags t2 ON t2.tag = t1.tag AND t2.page_id != t1.page_id
            JOIN pages p ON p.id = t2.page_id
            WHERE t1.page_id = %s AND p.workspace_id = %s AND p.deleted_at IS NULL
            GROUP BY p.id, p.slug, p.title, p.updated_at
            ORDER BY shared DESC, p.updated_at DESC
            LIMIT %s
            """,
            (int(page["id"]), workspace_id, limit),
        ).fetchall()
        return [
            RelatedPage(slug=r["slug"], title=r["title"], shared_tags=int(r["shared"]))
            for r in rows
        ]


def pages_to_embed(limit: int = 10) -> list[EmbedTarget]:
    """Páginas marcadas como sucias (embed_dirty=1) pendientes de embedding."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, workspace_id, content FROM pages "
            "WHERE embed_dirty = 1 AND workspace_id IS NOT NULL AND deleted_at IS NULL "
            "ORDER BY id LIMIT %s",
            (limit,),
        ).fetchall()
        return [
            EmbedTarget(id=r["id"], workspace_id=r["workspace_id"], content=r["content"])
            for r in rows
        ]


def store_page_chunks(
    page_id: int,
    workspace_id: int,
    chunks: list[tuple[int, str, bytes]],
    model: str,
) -> None:
    """Reemplaza los chunks/vectores de una página y limpia embed_dirty (atómico)."""
    now = _now()
    with connect() as conn:
        conn.execute("DELETE FROM page_chunks WHERE page_id = %s", (page_id,))
        if chunks:
            conn.cursor().executemany(
                "INSERT INTO page_chunks "
                "(page_id, workspace_id, ord, text, vector, model, created_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                [
                    (page_id, workspace_id, ord_, text, vec, model, now)
                    for ord_, text, vec in chunks
                ],
            )
        conn.execute("UPDATE pages SET embed_dirty = 0 WHERE id = %s", (page_id,))


def workspace_chunk_vectors(user_id: int, workspace_id: int) -> list[ChunkVector]:
    """Chunks + vectores de un workspace para la búsqueda semántica (KNN en memoria)."""
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT c.page_id, c.ord, c.text, c.vector, p.slug, p.title
            FROM page_chunks c
            JOIN pages p ON p.id = c.page_id
            WHERE c.workspace_id = %s AND p.deleted_at IS NULL
            """,
            (workspace_id,),
        ).fetchall()
        return [
            ChunkVector(
                page_id=r["page_id"],
                ord=r["ord"],
                text=r["text"],
                vector=bytes(r["vector"]),
                slug=r["slug"],
                title=r["title"],
            )
            for r in rows
        ]


def get_workspace_by_id(workspace_id: int) -> Workspace | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT id, slug, name FROM workspaces WHERE id = %s",
            (workspace_id,),
        ).fetchone()
        return _to_workspace(row) if row else None


def set_page_git_commit(user_id: int, workspace_id: int, slug: str, sha: str) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE pages SET git_commit = %s WHERE slug = %s AND workspace_id = %s",
            (sha, slug, workspace_id),
        )


def create_api_token(user_id: int, name: str, token_hash: str) -> int:
    with connect() as conn:
        row = conn.execute(
            "INSERT INTO api_tokens (user_id, name, token_hash, created_at) "
            "VALUES (%s, %s, %s, %s) RETURNING id",
            (user_id, name.strip() or "token", token_hash, _now()),
        ).fetchone()
        return int(row["id"])


def list_api_tokens(user_id: int) -> list[ApiToken]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, name, created_at, last_used_at FROM api_tokens "
            "WHERE user_id = %s ORDER BY created_at, id",
            (user_id,),
        ).fetchall()
        return [
            ApiToken(
                id=r["id"],
                name=r["name"],
                created_at=r["created_at"],
                last_used_at=r["last_used_at"],
            )
            for r in rows
        ]


def revoke_api_token(user_id: int, token_id: int) -> bool:
    with connect() as conn:
        cur = conn.execute(
            "DELETE FROM api_tokens WHERE id = %s AND user_id = %s",
            (token_id, user_id),
        )
        return cur.rowcount > 0


def resolve_api_token(token_hash: str) -> int | None:
    """Devuelve el user_id propietario y actualiza last_used_at; None si no existe."""
    with connect() as conn:
        row = conn.execute(
            "SELECT id, user_id FROM api_tokens WHERE token_hash = %s",
            (token_hash,),
        ).fetchone()
        if row is None:
            return None
        conn.execute(
            "UPDATE api_tokens SET last_used_at = %s WHERE id = %s",
            (_now(), row["id"]),
        )
        return int(row["user_id"])
