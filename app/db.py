from __future__ import annotations

import json
import os
import re
import sqlite3
import unicodedata
from datetime import UTC, datetime
from pathlib import Path

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

DEFAULT_DB_PATH = "doction.db"
DEFAULT_WORKSPACE_NAME = "Personal"
DEFAULT_WORKSPACE_SLUG = "personal"


def db_path() -> Path:
    return Path(os.environ.get("DATABASE_PATH", DEFAULT_DB_PATH))


def connect() -> sqlite3.Connection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


# ── Conversión de filas a dataclasses ────────────────────────────────────────
# Cada consulta devuelve un `sqlite3.Row`, que funciona como un diccionario. Estas
# funciones lo pasan a un dato con nombre (las clases de app/models.py). Pasamos la
# fila a un dict y usamos `.get(...)` para que, si una consulta no seleccionó cierta
# columna, ese campo quede en None en vez de provocar un error.

def _to_user(row: sqlite3.Row) -> User:
    d = dict(row)
    return User(
        id=d["id"],
        email=d["email"],
        password_hash=d["password_hash"],
        created_at=d["created_at"],
        display_name=d.get("display_name"),
        avatar_color=d.get("avatar_color"),
    )


def _to_workspace(row: sqlite3.Row) -> Workspace:
    d = dict(row)
    return Workspace(
        id=d["id"],
        slug=d["slug"],
        name=d["name"],
        role=d.get("role"),
        user_id=d.get("user_id"),
        created_at=d.get("created_at"),
    )


def _to_page(row: sqlite3.Row) -> Page:
    d = dict(row)
    return Page(
        id=d.get("id"),
        slug=d.get("slug", ""),
        title=d.get("title", ""),
        content=d.get("content", ""),
        user_id=d.get("user_id"),
        workspace_id=d.get("workspace_id"),
        parent_id=d.get("parent_id"),
        created_at=d.get("created_at"),
        updated_at=d.get("updated_at"),
        git_commit=d.get("git_commit"),
        embed_dirty=d.get("embed_dirty"),
        updated_by=d.get("updated_by"),
        deleted_at=d.get("deleted_at"),
        parent_slug=d.get("parent_slug"),
        parent_title=d.get("parent_title"),
        updated_by_email=d.get("updated_by_email"),
        updated_by_name=d.get("updated_by_name"),
    )


def _unique_index_present(conn: sqlite3.Connection, table: str, columns: list[str]) -> bool:
    for idx in conn.execute(f"PRAGMA index_list({table})"):
        if idx["unique"] != 1:
            continue
        idx_cols = [row["name"] for row in conn.execute(f"PRAGMA index_info({idx['name']})")]
        if idx_cols == columns:
            return True
    return False


def _legacy_slug_indexes_present(conn: sqlite3.Connection) -> bool:
    return _unique_index_present(conn, "pages", ["slug"]) or _unique_index_present(
        conn, "pages", ["user_id", "slug"]
    )


def _ensure_pages_indexes(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS pages_workspace_slug_idx ON pages(workspace_id, slug)"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS pages_user_idx ON pages(user_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS pages_parent_idx ON pages(parent_id)")


def _ensure_pages_fts(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS pages_fts USING fts5(
            title,
            content,
            content='pages',
            content_rowid='id'
        );

        CREATE TRIGGER IF NOT EXISTS pages_ai AFTER INSERT ON pages BEGIN
            INSERT INTO pages_fts(rowid, title, content)
            VALUES (new.id, new.title, new.content);
        END;

        CREATE TRIGGER IF NOT EXISTS pages_ad AFTER DELETE ON pages BEGIN
            INSERT INTO pages_fts(pages_fts, rowid, title, content)
            VALUES ('delete', old.id, old.title, old.content);
        END;

        CREATE TRIGGER IF NOT EXISTS pages_au AFTER UPDATE ON pages BEGIN
            INSERT INTO pages_fts(pages_fts, rowid, title, content)
            VALUES ('delete', old.id, old.title, old.content);
            INSERT INTO pages_fts(rowid, title, content)
            VALUES (new.id, new.title, new.content);
        END;
        """
    )


def _rebuild_pages_schema(conn: sqlite3.Connection) -> None:
    old_columns = set()
    for row in conn.execute("PRAGMA table_info(pages)"):
        old_columns.add(row["name"])
    select_user_id = "user_id" if "user_id" in old_columns else "NULL AS user_id"
    select_workspace_id = (
        "workspace_id" if "workspace_id" in old_columns else "NULL AS workspace_id"
    )
    select_parent_id = "parent_id" if "parent_id" in old_columns else "NULL AS parent_id"

    conn.executescript(
        """
        DROP TRIGGER IF EXISTS pages_ai;
        DROP TRIGGER IF EXISTS pages_ad;
        DROP TRIGGER IF EXISTS pages_au;
        DROP TABLE IF EXISTS pages_fts;
        ALTER TABLE pages RENAME TO pages_old;

        CREATE TABLE pages (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER REFERENCES users(id) ON DELETE CASCADE,
            workspace_id INTEGER REFERENCES workspaces(id) ON DELETE CASCADE,
            parent_id    INTEGER REFERENCES pages(id)
                         ON DELETE SET NULL DEFERRABLE INITIALLY DEFERRED,
            slug         TEXT NOT NULL,
            title        TEXT NOT NULL,
            content      TEXT NOT NULL,
            created_at   TEXT NOT NULL,
            updated_at   TEXT NOT NULL,
            git_commit   TEXT
        );
        """
    )
    conn.execute(
        f"""
        INSERT INTO pages (
            id, user_id, workspace_id, parent_id, slug, title, content, created_at, updated_at
        )
        SELECT id, {select_user_id}, {select_workspace_id}, {select_parent_id},
               slug, title, content, created_at, updated_at
        FROM pages_old
        """
    )
    conn.execute("DROP TABLE pages_old")
    _ensure_pages_indexes(conn)
    _ensure_pages_fts(conn)
    conn.execute("INSERT INTO pages_fts(pages_fts) VALUES('rebuild')")


def _unique_workspace_slug(
    conn: sqlite3.Connection,
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
            "SELECT id FROM workspaces WHERE slug = ?",
            (candidate,),
        ).fetchone()
        if row is None or row["id"] == ignore_id:
            return candidate
        suffix += 1
        candidate = f"{base}-{suffix}"


def _ensure_default_workspaces(conn: sqlite3.Connection) -> None:
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
            "INSERT INTO workspaces (user_id, slug, name, created_at) VALUES (?, ?, ?, ?)",
            (user_id, slug, DEFAULT_WORKSPACE_NAME, _now()),
        )


def _dedupe_workspace_slugs(conn: sqlite3.Connection) -> None:
    """Hace los slugs de workspace únicos a nivel global antes de imponer el índice único.

    Datos pre-multiusuario podían tener varios "personal" (uno por usuario). Se conserva
    el más antiguo y se renombran los demás a "personal-2", etc. Idempotente.
    """
    dupes = conn.execute(
        "SELECT slug FROM workspaces GROUP BY slug HAVING COUNT(*) > 1"
    ).fetchall()
    for row in dupes:
        rows = conn.execute(
            "SELECT id FROM workspaces WHERE slug = ? ORDER BY id", (row["slug"],)
        ).fetchall()
        for ws in rows[1:]:
            new_slug = _unique_workspace_slug(conn, row["slug"], ignore_id=int(ws["id"]))
            conn.execute(
                "UPDATE workspaces SET slug = ? WHERE id = ?", (new_slug, int(ws["id"]))
            )


def _ensure_member_owners(conn: sqlite3.Connection) -> None:
    """Backfill: el creador de cada workspace es 'owner' en workspace_members.

    Idempotente (INSERT OR IGNORE sobre la PK). Para workspaces creados antes de
    existir la tabla de membresía.
    """
    conn.execute(
        """
        INSERT OR IGNORE INTO workspace_members (workspace_id, user_id, role, created_at)
        SELECT w.id, w.user_id, 'owner', ?
        FROM workspaces w
        """,
        (_now(),),
    )


def _backfill_page_workspaces(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        UPDATE pages
        SET workspace_id = (
            SELECT w.id FROM workspaces w
            WHERE w.user_id = pages.user_id
            ORDER BY w.id ASC
            LIMIT 1
        )
        WHERE workspace_id IS NULL AND user_id IS NOT NULL
        """
    )
    conn.execute(
        """
        UPDATE pages
        SET user_id = (
            SELECT w.user_id FROM workspaces w
            WHERE w.id = pages.workspace_id
        )
        WHERE user_id IS NULL AND workspace_id IS NOT NULL
        """
    )


def _ensure_intel_tables(conn: sqlite3.Connection) -> None:
    """Tablas de "markdown como API": frontmatter, tags y grafo de enlaces.

    Se crean tras el posible rebuild de `pages` para que las FK apunten a la tabla
    final. Son derivadas del contenido: se reconstruyen en cada save.
    """
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS page_meta (
            page_id          INTEGER PRIMARY KEY REFERENCES pages(id) ON DELETE CASCADE,
            type             TEXT,
            frontmatter_json TEXT NOT NULL DEFAULT '{}'
        );

        CREATE TABLE IF NOT EXISTS page_tags (
            page_id INTEGER NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
            tag     TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS page_tags_tag_idx ON page_tags(tag);
        CREATE INDEX IF NOT EXISTS page_tags_page_idx ON page_tags(page_id);

        CREATE TABLE IF NOT EXISTS page_links (
            src_page_id  INTEGER NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
            dst_slug     TEXT NOT NULL,
            workspace_id INTEGER NOT NULL
        );
        CREATE INDEX IF NOT EXISTS page_links_dst_idx ON page_links(workspace_id, dst_slug);
        CREATE INDEX IF NOT EXISTS page_links_src_idx ON page_links(src_page_id);

        CREATE TABLE IF NOT EXISTS page_chunks (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            page_id      INTEGER NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
            workspace_id INTEGER NOT NULL,
            ord          INTEGER NOT NULL,
            text         TEXT NOT NULL,
            vector       BLOB NOT NULL,
            model        TEXT NOT NULL,
            created_at   TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS page_chunks_ws_idx ON page_chunks(workspace_id);
        CREATE INDEX IF NOT EXISTS page_chunks_page_idx ON page_chunks(page_id);
        """
    )


def _index_page_meta(
    conn: sqlite3.Connection, page_id: int, workspace_id: int, content: str
) -> None:
    """Reconstruye frontmatter/tags/enlaces de una página. Idempotente por page_id."""
    fm, _ = meta.parse_frontmatter(content)
    conn.execute("DELETE FROM page_meta WHERE page_id = ?", (page_id,))
    conn.execute(
        "INSERT INTO page_meta (page_id, type, frontmatter_json) VALUES (?, ?, ?)",
        (page_id, meta.page_type(content), json.dumps(fm, ensure_ascii=False)),
    )

    conn.execute("DELETE FROM page_tags WHERE page_id = ?", (page_id,))
    conn.executemany(
        "INSERT INTO page_tags (page_id, tag) VALUES (?, ?)",
        [(page_id, tag) for tag in meta.extract_tags(content)],
    )

    conn.execute("DELETE FROM page_links WHERE src_page_id = ?", (page_id,))
    seen: set[str] = set()
    edges: list[tuple[int, str, int]] = []
    for target in meta.extract_links(content):
        dst = slugify(target)
        if dst not in seen:
            seen.add(dst)
            edges.append((page_id, dst, workspace_id))
    conn.executemany(
        "INSERT INTO page_links (src_page_id, dst_slug, workspace_id) VALUES (?, ?, ?)",
        edges,
    )

    # El contenido cambió: marcar para reembedding (lo procesa el worker async).
    conn.execute("UPDATE pages SET embed_dirty = 1 WHERE id = ?", (page_id,))


def init_db() -> None:
    """Crea tablas, índice FTS5 y triggers de sincronización. Idempotente."""
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                email         TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at    TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS workspaces (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                slug       TEXT NOT NULL,
                name       TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS api_tokens (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name         TEXT NOT NULL,
                token_hash   TEXT NOT NULL UNIQUE,
                created_at   TEXT NOT NULL,
                last_used_at TEXT
            );

            CREATE TABLE IF NOT EXISTS workspace_members (
                workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
                user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                role         TEXT NOT NULL DEFAULT 'member',
                created_at   TEXT NOT NULL,
                PRIMARY KEY (workspace_id, user_id)
            );

            CREATE TABLE IF NOT EXISTS pages (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id      INTEGER REFERENCES users(id) ON DELETE CASCADE,
                workspace_id INTEGER REFERENCES workspaces(id) ON DELETE CASCADE,
                parent_id    INTEGER REFERENCES pages(id)
                             ON DELETE SET NULL DEFERRABLE INITIALLY DEFERRED,
                slug         TEXT NOT NULL,
                title        TEXT NOT NULL,
                content      TEXT NOT NULL,
                created_at   TEXT NOT NULL,
                updated_at   TEXT NOT NULL
            );
            """
        )

        conn.execute(
            "CREATE INDEX IF NOT EXISTS workspace_members_user_idx "
            "ON workspace_members(user_id)"
        )

        page_columns = set()
        for row in conn.execute("PRAGMA table_info(pages)"):
            page_columns.add(row["name"])
        needs_rebuild = (
            "user_id" not in page_columns
            or "workspace_id" not in page_columns
            or "parent_id" not in page_columns
            or _legacy_slug_indexes_present(conn)
            or not _unique_index_present(conn, "pages", ["workspace_id", "slug"])
        )

        if needs_rebuild:
            _rebuild_pages_schema(conn)
        else:
            _ensure_pages_indexes(conn)
            _ensure_pages_fts(conn)

        _ensure_default_workspaces(conn)
        _ensure_member_owners(conn)
        _dedupe_workspace_slugs(conn)
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS workspaces_slug_idx ON workspaces(slug)"
        )
        _backfill_page_workspaces(conn)

        page_cols = set()
        for r in conn.execute("PRAGMA table_info(pages)"):
            page_cols.add(r["name"])
        if "git_commit" not in page_cols:
            conn.execute("ALTER TABLE pages ADD COLUMN git_commit TEXT")
        if "embed_dirty" not in page_cols:
            # Default 1 ⇒ páginas existentes se reindexan al activar SEMANTIC_SEARCH.
            conn.execute("ALTER TABLE pages ADD COLUMN embed_dirty INTEGER NOT NULL DEFAULT 1")
        if "updated_by" not in page_cols:
            # Último editor (FK a users); se muestra como "editado por" en la cabecera.
            conn.execute("ALTER TABLE pages ADD COLUMN updated_by INTEGER REFERENCES users(id)")
        if "deleted_at" not in page_cols:
            # Soft-delete: NULL = viva; un timestamp = en la papelera (recuperable).
            conn.execute("ALTER TABLE pages ADD COLUMN deleted_at TEXT")

        user_cols = set()
        for r in conn.execute("PRAGMA table_info(users)"):
            user_cols.add(r["name"])
        if "display_name" not in user_cols:
            conn.execute("ALTER TABLE users ADD COLUMN display_name TEXT")
        if "avatar_color" not in user_cols:
            conn.execute("ALTER TABLE users ADD COLUMN avatar_color TEXT")

        _ensure_intel_tables(conn)


def slugify(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_text).strip("-").lower()
    return slug or "page"


def unique_slug(
    conn: sqlite3.Connection,
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
            "SELECT id FROM pages WHERE slug = ? AND workspace_id = ?",
            (candidate, workspace_id),
        ).fetchone()
        if row is None or row["id"] == ignore_id:
            return candidate
        suffix += 1
        candidate = f"{base}-{suffix}"


def create_user(email: str, password_hash: str) -> int:
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO users (email, password_hash, created_at) VALUES (?, ?, ?)",
            (email, password_hash, _now()),
        )
        return int(cur.lastrowid)


def has_users() -> bool:
    """True si ya existe al menos un usuario (para el flujo de primer arranque)."""
    with connect() as conn:
        return conn.execute("SELECT 1 FROM users LIMIT 1").fetchone() is not None


def get_user_by_email(email: str) -> User | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        return _to_user(row) if row else None


def get_user_by_id(user_id: int) -> User | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return _to_user(row) if row else None


def update_user_profile(user_id: int, display_name: str | None, avatar_color: str | None) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE users SET display_name = ?, avatar_color = ? WHERE id = ?",
            (display_name or None, avatar_color or None, user_id),
        )


def update_user_password(user_id: int, password_hash: str) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
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
            WHERE m.user_id = ?
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
            WHERE m.user_id = ? AND w.slug = ?
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
        cur = conn.execute(
            "INSERT INTO workspaces (user_id, slug, name, created_at) VALUES (?, ?, ?, ?)",
            (user_id, slug, name, now),
        )
        conn.execute(
            "INSERT OR IGNORE INTO workspace_members (workspace_id, user_id, role, created_at) "
            "VALUES (?, ?, 'owner', ?)",
            (int(cur.lastrowid), user_id, now),
        )
        return slug


def rename_workspace(user_id: int, slug: str, name: str) -> bool:
    name = name.strip()
    if not name:
        return False
    with connect() as conn:
        cur = conn.execute(
            "UPDATE workspaces SET name = ? WHERE user_id = ? AND slug = ?",
            (name, user_id, slug),
        )
        return cur.rowcount > 0


def delete_workspace(user_id: int, slug: str) -> bool:
    """Borra el workspace y sus páginas. No borra el último que quede.

    Las páginas se borran explícitamente (no por cascada) para que los triggers
    del índice FTS se disparen y no queden entradas huérfanas en la búsqueda.
    """
    with connect() as conn:
        count = conn.execute(
            "SELECT COUNT(*) AS n FROM workspaces WHERE user_id = ?", (user_id,)
        ).fetchone()["n"]
        if count <= 1:
            return False
        ws = conn.execute(
            "SELECT id FROM workspaces WHERE user_id = ? AND slug = ?",
            (user_id, slug),
        ).fetchone()
        if ws is None:
            return False
        conn.execute("DELETE FROM pages WHERE workspace_id = ?", (ws["id"],))
        conn.execute("DELETE FROM workspaces WHERE id = ?", (ws["id"],))
        return True


def get_member_role(user_id: int, workspace_id: int) -> str | None:
    """Rol del usuario en el workspace ('owner'|'member'), o None si no es miembro."""
    with connect() as conn:
        row = conn.execute(
            "SELECT role FROM workspace_members WHERE workspace_id = ? AND user_id = ?",
            (workspace_id, user_id),
        ).fetchone()
        return row["role"] if row else None


def add_workspace_member(workspace_id: int, user_id: int, role: str = "member") -> None:
    role = role if role in ("owner", "member") else "member"
    with connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO workspace_members (workspace_id, user_id, role, created_at) "
            "VALUES (?, ?, ?, ?)",
            (workspace_id, user_id, role, _now()),
        )


def remove_workspace_member(workspace_id: int, user_id: int) -> bool:
    with connect() as conn:
        cur = conn.execute(
            "DELETE FROM workspace_members WHERE workspace_id = ? AND user_id = ?",
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
            WHERE m.workspace_id = ?
            ORDER BY (m.role = 'owner') DESC, m.created_at, u.id
            """,
            (workspace_id,),
        ).fetchall()
        members = []
        for row in rows:
            members.append(
                Member(
                    user_id=row["user_id"],
                    email=row["email"],
                    display_name=row["display_name"],
                    role=row["role"],
                    created_at=row["created_at"],
                )
            )
        return members


def ensure_default_workspace(user_id: int) -> Workspace:
    with connect() as conn:
        workspace = conn.execute(
            "SELECT id, slug, name FROM workspaces WHERE user_id = ? ORDER BY id LIMIT 1",
            (user_id,),
        ).fetchone()
        if workspace is None:
            now = _now()
            slug = _unique_workspace_slug(conn, DEFAULT_WORKSPACE_SLUG)
            cur = conn.execute(
                "INSERT INTO workspaces (user_id, slug, name, created_at) VALUES (?, ?, ?, ?)",
                (user_id, slug, DEFAULT_WORKSPACE_NAME, now),
            )
            conn.execute(
                "INSERT OR IGNORE INTO workspace_members (workspace_id, user_id, role, created_at) "
                "VALUES (?, ?, 'owner', ?)",
                (int(cur.lastrowid), user_id, now),
            )
            workspace = conn.execute(
                "SELECT id, slug, name FROM workspaces WHERE user_id = ? AND slug = ?",
                (user_id, slug),
            ).fetchone()
        if workspace is None:
            raise RuntimeError("Failed to create default workspace")
        conn.execute(
            "UPDATE pages SET workspace_id = ? WHERE user_id = ? AND workspace_id IS NULL",
            (workspace["id"], user_id),
        )
        return _to_workspace(workspace)


def claim_unowned_pages(user_id: int, workspace_id: int) -> int:
    with connect() as conn:
        cur = conn.execute(
            "UPDATE pages SET user_id = ?, workspace_id = ? WHERE user_id IS NULL",
            (user_id, workspace_id),
        )
        return cur.rowcount


def list_pages_tree(user_id: int, workspace_id: int) -> list[PageNode]:
    """Lista plana en orden DFS con campo depth para renderizar el árbol en la sidebar."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, slug, title, parent_id FROM pages "
            "WHERE workspace_id = ? AND deleted_at IS NULL ORDER BY created_at, id",
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
            WHERE p.slug = ? AND p.workspace_id = ? AND p.deleted_at IS NULL
            """,
            (slug, workspace_id),
        ).fetchone()
        return _to_page(row) if row else None


def get_ancestors(page_id: int, user_id: int, workspace_id: int) -> list[PageRef]:
    """Cadena de ancestros desde la raíz hasta el padre directo (sin incluir la página)."""
    chain: list[PageRef] = []
    with connect() as conn:
        row = conn.execute(
            "SELECT parent_id FROM pages WHERE id = ? AND workspace_id = ?",
            (page_id, workspace_id),
        ).fetchone()
        parent_id = row["parent_id"] if row else None
        seen: set[int] = set()
        while parent_id is not None and parent_id not in seen:
            seen.add(parent_id)
            parent = conn.execute(
                "SELECT id, slug, title, parent_id FROM pages "
                "WHERE id = ? AND workspace_id = ? AND deleted_at IS NULL",
                (parent_id, workspace_id),
            ).fetchone()
            if parent is None:
                break
            chain.append(PageRef(slug=parent["slug"], title=parent["title"]))
            parent_id = parent["parent_id"]
    chain.reverse()
    return chain


def _resolve_parent_id(
    conn: sqlite3.Connection,
    parent_slug: str | None,
    *,
    user_id: int,
    workspace_id: int,
    ignore_id: int | None = None,
) -> int | None:
    if not parent_slug:
        return None
    row = conn.execute(
        "SELECT id FROM pages WHERE slug = ? AND workspace_id = ? AND deleted_at IS NULL",
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
        cur = conn.execute(
            """
            INSERT INTO pages (
                user_id, workspace_id, parent_id, slug, title, content,
                created_at, updated_at, updated_by
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, workspace_id, parent_id, slug, title, content, now, now, user_id),
        )
        _index_page_meta(conn, int(cur.lastrowid), workspace_id, content)
        return slug


def update_page(user_id: int, workspace_id: int, slug: str, title: str, content: str) -> str | None:
    """Actualiza una página manteniendo el slug estable; devuelve slug o None si no existe."""
    title = title.strip() or "Untitled"
    with connect() as conn:
        row = conn.execute(
            "SELECT id FROM pages WHERE slug = ? AND workspace_id = ? AND deleted_at IS NULL",
            (slug, workspace_id),
        ).fetchone()
        if row is None:
            return None
        conn.execute(
            "UPDATE pages SET title = ?, content = ?, updated_at = ?, updated_by = ? WHERE id = ?",
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
            "UPDATE pages SET deleted_at = ? WHERE slug = ? AND workspace_id = ? "
            "AND deleted_at IS NULL",
            (_now(), slug, workspace_id),
        )
        return cur.rowcount > 0


def list_deleted_pages(user_id: int, workspace_id: int) -> list[Page]:
    """Páginas en la papelera del workspace, más recientes primero.

    Cada Page trae solo slug, title y deleted_at (lo que se muestra en la papelera).
    """
    with connect() as conn:
        rows = conn.execute(
            "SELECT slug, title, deleted_at FROM pages "
            "WHERE workspace_id = ? AND deleted_at IS NOT NULL "
            "ORDER BY deleted_at DESC",
            (workspace_id,),
        ).fetchall()
        return [_to_page(row) for row in rows]


def restore_page(user_id: int, workspace_id: int, slug: str) -> bool:
    """Saca una página de la papelera (deleted_at = NULL)."""
    with connect() as conn:
        cur = conn.execute(
            "UPDATE pages SET deleted_at = NULL WHERE slug = ? AND workspace_id = ? "
            "AND deleted_at IS NOT NULL",
            (slug, workspace_id),
        )
        return cur.rowcount > 0


def purge_page(user_id: int, workspace_id: int, slug: str) -> bool:
    """Borra definitivamente una página que ya está en la papelera (hard delete).

    El CASCADE limpia meta/tags/links/chunks y el trigger pages_ad limpia el índice FTS."""
    with connect() as conn:
        cur = conn.execute(
            "DELETE FROM pages WHERE slug = ? AND workspace_id = ? AND deleted_at IS NOT NULL",
            (slug, workspace_id),
        )
        return cur.rowcount > 0


def pages_for_export(workspace_id: int) -> list[Page]:
    """Páginas vivas de un workspace (slug, title, content) para exportar a markdown."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT slug, title, content FROM pages "
            "WHERE workspace_id = ? AND deleted_at IS NULL ORDER BY slug",
            (workspace_id,),
        ).fetchall()
        return [_to_page(row) for row in rows]


def list_child_pages(user_id: int, workspace_id: int, parent_id: int) -> list[Page]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT slug, title, updated_at FROM pages "
            "WHERE workspace_id = ? AND parent_id = ? AND deleted_at IS NULL "
            "ORDER BY updated_at DESC",
            (workspace_id, parent_id),
        ).fetchall()
        return [_to_page(row) for row in rows]


def _fts_query(raw: str) -> str:
    """Convierte input de usuario en una consulta FTS5 de prefijos segura."""
    terms = re.findall(r"[\w]+", raw, flags=re.UNICODE)
    if not terms:
        return ""
    return " ".join(f'"{term}"*' for term in terms)


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
                   snippet(pages_fts, 1, '<mark>', '</mark>', '…', 12) AS snippet
            FROM pages_fts
            JOIN pages p ON p.id = pages_fts.rowid
            WHERE pages_fts MATCH ? AND p.workspace_id = ? AND p.deleted_at IS NULL
            ORDER BY rank
            LIMIT ?
            """,
            (match, workspace_id, limit),
        ).fetchall()
        return [
            SearchHit(slug=row["slug"], title=row["title"], snippet=row["snippet"])
            for row in rows
        ]


def _page_tags(conn: sqlite3.Connection, page_id: int) -> list[str]:
    rows = conn.execute(
        "SELECT tag FROM page_tags WHERE page_id = ? ORDER BY rowid", (page_id,)
    ).fetchall()
    return [r["tag"] for r in rows]


def get_page_meta(user_id: int, workspace_id: int, slug: str) -> PageMeta | None:
    """Frontmatter + tags de una página, o None si no existe."""
    with connect() as conn:
        row = conn.execute(
            "SELECT id FROM pages WHERE slug = ? AND workspace_id = ? AND deleted_at IS NULL",
            (slug, workspace_id),
        ).fetchone()
        if row is None:
            return None
        meta_row = conn.execute(
            "SELECT type, frontmatter_json FROM page_meta WHERE page_id = ?", (row["id"],)
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
        joins = "JOIN page_tags t ON t.page_id = p.id AND t.tag = ?"
        params.append(meta.normalize_tag(tag))
    where = ["p.workspace_id = ?", "p.deleted_at IS NULL"]
    params.append(workspace_id)
    if page_type:
        where.append("m.type = ?")
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
        LIMIT ?
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
            WHERE l.workspace_id = ? AND l.dst_slug = ? AND p.deleted_at IS NULL
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
            "SELECT id FROM pages WHERE slug = ? AND workspace_id = ? AND deleted_at IS NULL",
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
            WHERE t1.page_id = ? AND p.workspace_id = ? AND p.deleted_at IS NULL
            GROUP BY p.id
            ORDER BY shared DESC, p.updated_at DESC
            LIMIT ?
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
            "ORDER BY id LIMIT ?",
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
        conn.execute("DELETE FROM page_chunks WHERE page_id = ?", (page_id,))
        conn.executemany(
            "INSERT INTO page_chunks (page_id, workspace_id, ord, text, vector, model, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [(page_id, workspace_id, ord_, text, vec, model, now) for ord_, text, vec in chunks],
        )
        conn.execute("UPDATE pages SET embed_dirty = 0 WHERE id = ?", (page_id,))


def workspace_chunk_vectors(user_id: int, workspace_id: int) -> list[ChunkVector]:
    """Chunks + vectores de un workspace para la búsqueda semántica (KNN en memoria)."""
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT c.page_id, c.ord, c.text, c.vector, p.slug, p.title
            FROM page_chunks c
            JOIN pages p ON p.id = c.page_id
            WHERE c.workspace_id = ? AND p.deleted_at IS NULL
            """,
            (workspace_id,),
        ).fetchall()
        return [
            ChunkVector(
                page_id=r["page_id"],
                ord=r["ord"],
                text=r["text"],
                vector=r["vector"],
                slug=r["slug"],
                title=r["title"],
            )
            for r in rows
        ]


def get_workspace_by_id(workspace_id: int) -> Workspace | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT id, slug, name FROM workspaces WHERE id = ?",
            (workspace_id,),
        ).fetchone()
        return _to_workspace(row) if row else None


def set_page_git_commit(user_id: int, workspace_id: int, slug: str, sha: str) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE pages SET git_commit = ? WHERE slug = ? AND workspace_id = ?",
            (sha, slug, workspace_id),
        )


def create_api_token(user_id: int, name: str, token_hash: str) -> int:
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO api_tokens (user_id, name, token_hash, created_at) VALUES (?, ?, ?, ?)",
            (user_id, name.strip() or "token", token_hash, _now()),
        )
        return int(cur.lastrowid)


def list_api_tokens(user_id: int) -> list[ApiToken]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, name, created_at, last_used_at FROM api_tokens "
            "WHERE user_id = ? ORDER BY created_at, id",
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
            "DELETE FROM api_tokens WHERE id = ? AND user_id = ?",
            (token_id, user_id),
        )
        return cur.rowcount > 0


def resolve_api_token(token_hash: str) -> int | None:
    """Devuelve el user_id propietario y actualiza last_used_at; None si no existe."""
    with connect() as conn:
        row = conn.execute(
            "SELECT id, user_id FROM api_tokens WHERE token_hash = ?",
            (token_hash,),
        ).fetchone()
        if row is None:
            return None
        conn.execute(
            "UPDATE api_tokens SET last_used_at = ? WHERE id = ?",
            (_now(), row["id"]),
        )
        return int(row["user_id"])
