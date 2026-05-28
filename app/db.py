"""SQLite storage with FTS5 full-text search for MiniDocMost pages."""

from __future__ import annotations

import os
import re
import sqlite3
import unicodedata
from datetime import UTC, datetime
from pathlib import Path

DEFAULT_DB_PATH = "minidocmost.db"


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


def _slug_unique_index_present(conn: sqlite3.Connection) -> bool:
    for idx in conn.execute("PRAGMA index_list(pages)"):
        if idx["unique"] != 1:
            continue
        cols = [row["name"] for row in conn.execute(f"PRAGMA index_info({idx['name']})")]
        if cols == ["slug"]:
            return True
    return False


def _user_slug_index_present(conn: sqlite3.Connection) -> bool:
    for idx in conn.execute("PRAGMA index_list(pages)"):
        if idx["unique"] != 1:
            continue
        cols = [row["name"] for row in conn.execute(f"PRAGMA index_info({idx['name']})")]
        if cols == ["user_id", "slug"]:
            return True
    return False


def _rebuild_pages_schema(conn: sqlite3.Connection) -> None:
    old_columns = {row["name"] for row in conn.execute("PRAGMA table_info(pages)")}
    select_user_id = "user_id" if "user_id" in old_columns else "NULL AS user_id"
    conn.executescript(
        """
        DROP TRIGGER IF EXISTS pages_ai;
        DROP TRIGGER IF EXISTS pages_ad;
        DROP TRIGGER IF EXISTS pages_au;
        DROP TABLE IF EXISTS pages_fts;
        ALTER TABLE pages RENAME TO pages_old;

        CREATE TABLE pages (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER REFERENCES users(id) ON DELETE CASCADE,
            slug       TEXT NOT NULL,
            title      TEXT NOT NULL,
            content    TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """
    )
    conn.execute(
        "INSERT INTO pages (id, user_id, slug, title, content, created_at, updated_at) "
        f"SELECT id, {select_user_id}, slug, title, content, created_at, updated_at FROM pages_old"
    )
    conn.executescript(
        """
        DROP TABLE pages_old;
        CREATE UNIQUE INDEX IF NOT EXISTS pages_user_slug_idx ON pages(user_id, slug);
        CREATE VIRTUAL TABLE pages_fts USING fts5(
            title,
            content,
            content='pages',
            content_rowid='id'
        );
        CREATE TRIGGER pages_ai AFTER INSERT ON pages BEGIN
            INSERT INTO pages_fts(rowid, title, content)
            VALUES (new.id, new.title, new.content);
        END;
        CREATE TRIGGER pages_ad AFTER DELETE ON pages BEGIN
            INSERT INTO pages_fts(pages_fts, rowid, title, content)
            VALUES ('delete', old.id, old.title, old.content);
        END;
        CREATE TRIGGER pages_au AFTER UPDATE ON pages BEGIN
            INSERT INTO pages_fts(pages_fts, rowid, title, content)
            VALUES ('delete', old.id, old.title, old.content);
            INSERT INTO pages_fts(rowid, title, content)
            VALUES (new.id, new.title, new.content);
        END;
        """
    )
    conn.execute("INSERT INTO pages_fts(pages_fts) VALUES('rebuild')")


def init_db() -> None:
    """Create core tables, the FTS5 index, and sync triggers (idempotent)."""
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                email         TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at    TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS pages (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER REFERENCES users(id) ON DELETE CASCADE,
                slug       TEXT NOT NULL,
                title      TEXT NOT NULL,
                content    TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(pages)")}
        if (
            "user_id" not in columns
            or _slug_unique_index_present(conn)
            or not _user_slug_index_present(conn)
        ):
            _rebuild_pages_schema(conn)
            return
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS pages_user_slug_idx ON pages(user_id, slug)"
        )
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


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def slugify(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_text).strip("-").lower()
    return slug or "page"


def unique_slug(
    conn: sqlite3.Connection,
    base: str,
    *,
    user_id: int,
    ignore_id: int | None = None,
) -> str:
    """Return a slug guaranteed unique, appending -2, -3, ... on collision."""
    candidate = base
    suffix = 1
    while True:
        row = conn.execute(
            "SELECT id FROM pages WHERE slug = ? AND user_id = ?",
            (candidate, user_id),
        ).fetchone()
        if row is None or row["id"] == ignore_id:
            return candidate
        suffix += 1
        candidate = f"{base}-{suffix}"


def count_users() -> int:
    with connect() as conn:
        return conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]


def create_user(email: str, password_hash: str) -> int:
    now = _now()
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO users (email, password_hash, created_at) VALUES (?, ?, ?)",
            (email, password_hash, now),
        )
        return int(cur.lastrowid)


def get_user_by_email(email: str) -> sqlite3.Row | None:
    with connect() as conn:
        return conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()


def get_user_by_id(user_id: int) -> sqlite3.Row | None:
    with connect() as conn:
        return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def claim_unowned_pages(user_id: int) -> int:
    with connect() as conn:
        cur = conn.execute(
            "UPDATE pages SET user_id = ? WHERE user_id IS NULL",
            (user_id,),
        )
        return cur.rowcount


def list_pages(user_id: int) -> list[sqlite3.Row]:
    with connect() as conn:
        return conn.execute(
            "SELECT slug, title, updated_at FROM pages WHERE user_id = ? "
            "ORDER BY updated_at DESC",
            (user_id,),
        ).fetchall()


def get_page(slug: str, user_id: int) -> sqlite3.Row | None:
    with connect() as conn:
        return conn.execute(
            "SELECT * FROM pages WHERE slug = ? AND user_id = ?",
            (slug, user_id),
        ).fetchone()


def latest_page(user_id: int) -> sqlite3.Row | None:
    with connect() as conn:
        return conn.execute(
            "SELECT * FROM pages WHERE user_id = ? ORDER BY updated_at DESC LIMIT 1",
            (user_id,),
        ).fetchone()


def count_pages(user_id: int) -> int:
    with connect() as conn:
        return conn.execute(
            "SELECT COUNT(*) AS n FROM pages WHERE user_id = ?",
            (user_id,),
        ).fetchone()["n"]


def create_page(user_id: int, title: str, content: str) -> str:
    title = title.strip() or "Untitled"
    now = _now()
    with connect() as conn:
        slug = unique_slug(conn, slugify(title), user_id=user_id)
        conn.execute(
            "INSERT INTO pages (user_id, slug, title, content, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, slug, title, content, now, now),
        )
        return slug


def update_page(user_id: int, slug: str, title: str, content: str) -> str | None:
    """Update an existing page; returns the (possibly new) slug, or None if missing."""
    title = title.strip() or "Untitled"
    with connect() as conn:
        row = conn.execute(
            "SELECT id FROM pages WHERE slug = ? AND user_id = ?",
            (slug, user_id),
        ).fetchone()
        if row is None:
            return None
        new_slug = unique_slug(conn, slugify(title), user_id=user_id, ignore_id=row["id"])
        conn.execute(
            "UPDATE pages SET slug = ?, title = ?, content = ?, updated_at = ? WHERE id = ?",
            (new_slug, title, content, _now(), row["id"]),
        )
        return new_slug


def delete_page(user_id: int, slug: str) -> bool:
    with connect() as conn:
        cur = conn.execute(
            "DELETE FROM pages WHERE slug = ? AND user_id = ?",
            (slug, user_id),
        )
        return cur.rowcount > 0


def _fts_query(raw: str) -> str:
    """Turn arbitrary user input into a safe FTS5 prefix query."""
    terms = re.findall(r"[\w]+", raw, flags=re.UNICODE)
    if not terms:
        return ""
    return " ".join(f'"{term}"*' for term in terms)


def search_pages(user_id: int, query: str, limit: int = 20) -> list[sqlite3.Row]:
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
            WHERE pages_fts MATCH ? AND p.user_id = ?
            ORDER BY rank
            LIMIT ?
            """,
            (match, user_id, limit),
        ).fetchall()
