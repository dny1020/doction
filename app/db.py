"""SQLite storage with FTS5 full-text search for doction pages and workspaces."""

from __future__ import annotations

import os
import re
import sqlite3
import unicodedata
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

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
    old_columns = {row["name"] for row in conn.execute("PRAGMA table_info(pages)")}
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
            git_commit   TEXT,
            embedding    BLOB
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
    user_id: int,
    ignore_id: int | None = None,
) -> str:
    candidate = base
    suffix = 1
    while True:
        row = conn.execute(
            "SELECT id FROM workspaces WHERE user_id = ? AND slug = ?",
            (user_id, candidate),
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
        slug = _unique_workspace_slug(conn, DEFAULT_WORKSPACE_SLUG, user_id=user_id)
        conn.execute(
            "INSERT INTO workspaces (user_id, slug, name, created_at) VALUES (?, ?, ?, ?)",
            (user_id, slug, DEFAULT_WORKSPACE_NAME, _now()),
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


def init_db() -> None:
    """Create core tables, workspace support, FTS index, and sync triggers."""
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
            "CREATE UNIQUE INDEX IF NOT EXISTS workspaces_user_slug_idx "
            "ON workspaces(user_id, slug)"
        )

        page_columns = {row["name"] for row in conn.execute("PRAGMA table_info(pages)")}
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
        _backfill_page_workspaces(conn)

        page_cols = {r["name"] for r in conn.execute("PRAGMA table_info(pages)")}
        if "git_commit" not in page_cols:
            conn.execute("ALTER TABLE pages ADD COLUMN git_commit TEXT")
        if "embedding" not in page_cols:
            conn.execute("ALTER TABLE pages ADD COLUMN embedding BLOB")


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
    """Return a slug unique inside one workspace, appending -2, -3, ... on collision."""
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


def get_user_by_email(email: str) -> sqlite3.Row | None:
    with connect() as conn:
        return conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()


def get_user_by_id(user_id: int) -> sqlite3.Row | None:
    with connect() as conn:
        return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def list_workspaces(user_id: int) -> list[sqlite3.Row]:
    with connect() as conn:
        return conn.execute(
            "SELECT id, slug, name FROM workspaces WHERE user_id = ? ORDER BY created_at, id",
            (user_id,),
        ).fetchall()


def get_workspace_by_slug(user_id: int, slug: str) -> sqlite3.Row | None:
    with connect() as conn:
        return conn.execute(
            "SELECT id, slug, name FROM workspaces WHERE user_id = ? AND slug = ?",
            (user_id, slug),
        ).fetchone()


def default_workspace(user_id: int) -> sqlite3.Row | None:
    with connect() as conn:
        return conn.execute(
            "SELECT id, slug, name FROM workspaces WHERE user_id = ? ORDER BY id LIMIT 1",
            (user_id,),
        ).fetchone()


def create_workspace(user_id: int, name: str) -> str:
    name = name.strip() or "Workspace"
    base = slugify(name)
    with connect() as conn:
        slug = _unique_workspace_slug(conn, base, user_id=user_id)
        conn.execute(
            "INSERT INTO workspaces (user_id, slug, name, created_at) VALUES (?, ?, ?, ?)",
            (user_id, slug, name, _now()),
        )
        return slug


def ensure_default_workspace(user_id: int) -> sqlite3.Row:
    with connect() as conn:
        workspace = conn.execute(
            "SELECT id, slug, name FROM workspaces WHERE user_id = ? ORDER BY id LIMIT 1",
            (user_id,),
        ).fetchone()
        if workspace is None:
            slug = _unique_workspace_slug(conn, DEFAULT_WORKSPACE_SLUG, user_id=user_id)
            conn.execute(
                "INSERT INTO workspaces (user_id, slug, name, created_at) VALUES (?, ?, ?, ?)",
                (user_id, slug, DEFAULT_WORKSPACE_NAME, _now()),
            )
            workspace = conn.execute(
                "SELECT id, slug, name FROM workspaces WHERE user_id = ? AND slug = ?",
                (user_id, slug),
            ).fetchone()
        assert workspace is not None
        conn.execute(
            "UPDATE pages SET workspace_id = ? WHERE user_id = ? AND workspace_id IS NULL",
            (workspace["id"], user_id),
        )
        return workspace


def claim_unowned_pages(user_id: int, workspace_id: int) -> int:
    with connect() as conn:
        cur = conn.execute(
            "UPDATE pages SET user_id = ?, workspace_id = ? WHERE user_id IS NULL",
            (user_id, workspace_id),
        )
        return cur.rowcount


def list_pages_tree(user_id: int, workspace_id: int) -> list[dict]:
    """Return all pages as a DFS-ordered flat list with a depth field for sidebar tree rendering."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, slug, title, parent_id FROM pages "
            "WHERE user_id = ? AND workspace_id = ? ORDER BY created_at, id",
            (user_id, workspace_id),
        ).fetchall()

    by_id = {r["id"]: r for r in rows}
    children: dict[int, list] = {}
    roots = []
    for r in rows:
        pid = r["parent_id"]
        if pid is None or pid not in by_id:
            roots.append(r)
        else:
            children.setdefault(int(pid), []).append(r)

    result: list[dict] = []

    def _dfs(node, depth: int) -> None:
        result.append({"slug": node["slug"], "title": node["title"], "depth": depth})
        for child in children.get(int(node["id"]), []):
            _dfs(child, depth + 1)

    for root in roots:
        _dfs(root, 0)

    return result


def get_page(slug: str, user_id: int, workspace_id: int) -> sqlite3.Row | None:
    with connect() as conn:
        return conn.execute(
            """
            SELECT p.*, parent.slug AS parent_slug, parent.title AS parent_title
            FROM pages p
            LEFT JOIN pages parent ON parent.id = p.parent_id
            WHERE p.slug = ? AND p.user_id = ? AND p.workspace_id = ?
            """,
            (slug, user_id, workspace_id),
        ).fetchone()


def latest_page(user_id: int, workspace_id: int) -> sqlite3.Row | None:
    with connect() as conn:
        return conn.execute(
            """
            SELECT p.*, parent.slug AS parent_slug, parent.title AS parent_title
            FROM pages p
            LEFT JOIN pages parent ON parent.id = p.parent_id
            WHERE p.user_id = ? AND p.workspace_id = ?
            ORDER BY p.updated_at DESC
            LIMIT 1
            """,
            (user_id, workspace_id),
        ).fetchone()


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
        "SELECT id FROM pages WHERE slug = ? AND user_id = ? AND workspace_id = ?",
        (parent_slug, user_id, workspace_id),
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
        conn.execute(
            """
            INSERT INTO pages (
                user_id, workspace_id, parent_id, slug, title, content, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, workspace_id, parent_id, slug, title, content, now, now),
        )
        return slug


def update_page(user_id: int, workspace_id: int, slug: str, title: str, content: str) -> str | None:
    """Update a page while keeping its slug stable; returns slug, or None if missing."""
    title = title.strip() or "Untitled"
    with connect() as conn:
        row = conn.execute(
            "SELECT id FROM pages WHERE slug = ? AND user_id = ? AND workspace_id = ?",
            (slug, user_id, workspace_id),
        ).fetchone()
        if row is None:
            return None
        conn.execute(
            "UPDATE pages SET title = ?, content = ?, updated_at = ? WHERE id = ?",
            (title, content, _now(), row["id"]),
        )
        return slug


def delete_page(user_id: int, workspace_id: int, slug: str) -> bool:
    with connect() as conn:
        cur = conn.execute(
            "DELETE FROM pages WHERE slug = ? AND user_id = ? AND workspace_id = ?",
            (slug, user_id, workspace_id),
        )
        return cur.rowcount > 0


def list_child_pages(user_id: int, workspace_id: int, parent_id: int) -> list[sqlite3.Row]:
    with connect() as conn:
        return conn.execute(
            "SELECT slug, title, updated_at FROM pages "
            "WHERE user_id = ? AND workspace_id = ? AND parent_id = ? "
            "ORDER BY updated_at DESC",
            (user_id, workspace_id, parent_id),
        ).fetchall()


def _fts_query(raw: str) -> str:
    """Turn arbitrary user input into a safe FTS5 prefix query."""
    terms = re.findall(r"[\w]+", raw, flags=re.UNICODE)
    if not terms:
        return ""
    return " ".join(f'"{term}"*' for term in terms)


def search_pages(
    user_id: int,
    workspace_id: int,
    query: str,
    limit: int = 20,
) -> list[sqlite3.Row]:
    match = _fts_query(query)
    if not match:
        return []
    with connect() as conn:
        return conn.execute(
            """
            SELECT p.slug, p.title,
                   snippet(pages_fts, 1, '<mark>', '</mark>', '…', 12) AS snippet
            FROM pages_fts
            JOIN pages p ON p.id = pages_fts.rowid
            WHERE pages_fts MATCH ? AND p.user_id = ? AND p.workspace_id = ?
            ORDER BY rank
            LIMIT ?
            """,
            (match, user_id, workspace_id, limit),
        ).fetchall()


def get_workspace_by_id(workspace_id: int) -> sqlite3.Row | None:
    with connect() as conn:
        return conn.execute(
            "SELECT id, slug, name FROM workspaces WHERE id = ?",
            (workspace_id,),
        ).fetchone()


def set_page_git_commit(user_id: int, workspace_id: int, slug: str, sha: str) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE pages SET git_commit = ? WHERE slug = ? AND user_id = ? AND workspace_id = ?",
            (sha, slug, user_id, workspace_id),
        )


def update_page_embedding(user_id: int, workspace_id: int, slug: str, embedding: bytes) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE pages SET embedding = ? WHERE slug = ? AND user_id = ? AND workspace_id = ?",
            (embedding, slug, user_id, workspace_id),
        )


def get_all_embeddings(user_id: int, workspace_id: int) -> list[sqlite3.Row]:
    with connect() as conn:
        return conn.execute(
            "SELECT slug, title, embedding FROM pages "
            "WHERE user_id = ? AND workspace_id = ? AND embedding IS NOT NULL",
            (user_id, workspace_id),
        ).fetchall()


def semantic_search_pages(
    user_id: int,
    workspace_id: int,
    query_embedding: bytes,
    limit: int = 20,
) -> list[dict]:
    """Cosine similarity search using stored float32 embeddings (normalized → dot product)."""
    rows = get_all_embeddings(user_id, workspace_id)
    if not rows:
        return []
    q_vec = np.frombuffer(query_embedding, dtype=np.float32)
    scored = []
    for row in rows:
        d_vec = np.frombuffer(bytes(row["embedding"]), dtype=np.float32)
        score = float(np.dot(q_vec, d_vec))
        scored.append({"slug": row["slug"], "title": row["title"], "score": score, "snippet": ""})
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:limit]


def _search_pages_with_rank(
    user_id: int,
    workspace_id: int,
    query: str,
    limit: int = 40,
) -> list[dict]:
    match = _fts_query(query)
    if not match:
        return []
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT p.slug, p.title,
                   snippet(pages_fts, 1, '<mark>', '</mark>', '…', 12) AS snippet,
                   pages_fts.rank AS rank
            FROM pages_fts
            JOIN pages p ON p.id = pages_fts.rowid
            WHERE pages_fts MATCH ? AND p.user_id = ? AND p.workspace_id = ?
            ORDER BY rank
            LIMIT ?
            """,
            (match, user_id, workspace_id, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def hybrid_search_pages(
    user_id: int,
    workspace_id: int,
    query: str,
    query_embedding: bytes,
    limit: int = 20,
) -> list[dict]:
    """Combine BM25 (FTS5) and cosine similarity with equal weighting."""
    fts_results = {
        r["slug"]: r for r in _search_pages_with_rank(user_id, workspace_id, query, limit * 2)
    }
    sem_results = {
        r["slug"]: r
        for r in semantic_search_pages(user_id, workspace_id, query_embedding, limit * 2)
    }

    all_slugs = set(fts_results) | set(sem_results)
    scored = []
    for slug in all_slugs:
        fts_score = 0.0
        snippet = ""
        if slug in fts_results:
            rank = fts_results[slug]["rank"]  # negative BM25
            fts_score = 1.0 / (1.0 + abs(rank))
            snippet = fts_results[slug]["snippet"]
        sem_score = sem_results[slug]["score"] if slug in sem_results else 0.0
        title = (fts_results.get(slug) or sem_results.get(slug))["title"]  # type: ignore[index]
        scored.append({
            "slug": slug,
            "title": title,
            "score": 0.5 * sem_score + 0.5 * fts_score,
            "snippet": snippet,
        })
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:limit]
