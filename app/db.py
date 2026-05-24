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


def init_db() -> None:
    """Create the pages table, the FTS5 index, and sync triggers (idempotent)."""
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS pages (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                slug       TEXT NOT NULL UNIQUE,
                title      TEXT NOT NULL,
                content    TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

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


def unique_slug(conn: sqlite3.Connection, base: str, *, ignore_id: int | None = None) -> str:
    """Return a slug guaranteed unique, appending -2, -3, ... on collision."""
    candidate = base
    suffix = 1
    while True:
        row = conn.execute("SELECT id FROM pages WHERE slug = ?", (candidate,)).fetchone()
        if row is None or row["id"] == ignore_id:
            return candidate
        suffix += 1
        candidate = f"{base}-{suffix}"


def list_pages() -> list[sqlite3.Row]:
    with connect() as conn:
        return conn.execute(
            "SELECT slug, title, updated_at FROM pages ORDER BY updated_at DESC"
        ).fetchall()


def get_page(slug: str) -> sqlite3.Row | None:
    with connect() as conn:
        return conn.execute("SELECT * FROM pages WHERE slug = ?", (slug,)).fetchone()


def latest_page() -> sqlite3.Row | None:
    with connect() as conn:
        return conn.execute("SELECT * FROM pages ORDER BY updated_at DESC LIMIT 1").fetchone()


def count_pages() -> int:
    with connect() as conn:
        return conn.execute("SELECT COUNT(*) AS n FROM pages").fetchone()["n"]


def create_page(title: str, content: str) -> str:
    title = title.strip() or "Untitled"
    now = _now()
    with connect() as conn:
        slug = unique_slug(conn, slugify(title))
        conn.execute(
            "INSERT INTO pages (slug, title, content, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (slug, title, content, now, now),
        )
        return slug


def update_page(slug: str, title: str, content: str) -> str | None:
    """Update an existing page; returns the (possibly new) slug, or None if missing."""
    title = title.strip() or "Untitled"
    with connect() as conn:
        row = conn.execute("SELECT id FROM pages WHERE slug = ?", (slug,)).fetchone()
        if row is None:
            return None
        new_slug = unique_slug(conn, slugify(title), ignore_id=row["id"])
        conn.execute(
            "UPDATE pages SET slug = ?, title = ?, content = ?, updated_at = ? WHERE id = ?",
            (new_slug, title, content, _now(), row["id"]),
        )
        return new_slug


def delete_page(slug: str) -> bool:
    with connect() as conn:
        cur = conn.execute("DELETE FROM pages WHERE slug = ?", (slug,))
        return cur.rowcount > 0


def _fts_query(raw: str) -> str:
    """Turn arbitrary user input into a safe FTS5 prefix query."""
    terms = re.findall(r"[\w]+", raw, flags=re.UNICODE)
    if not terms:
        return ""
    return " ".join(f'"{term}"*' for term in terms)


def search_pages(query: str, limit: int = 20) -> list[sqlite3.Row]:
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
            WHERE pages_fts MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (match, limit),
        ).fetchall()
