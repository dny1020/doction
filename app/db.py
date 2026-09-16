import json
import logging
import os
import re
import threading
import unicodedata
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import LiteralString
from urllib.parse import urlsplit, urlunsplit

from psycopg import Connection
from psycopg.rows import DictRow, dict_row
from psycopg_pool import ConnectionPool

from app import meta
from app.avatar import normalize_color
from app.models import (
    ApiToken,
    ChunkVector,
    Delivery,
    EmbedTarget,
    ExtractedPage,
    LinkEdge,
    Member,
    Mention,
    NoteRef,
    Page,
    PageMeta,
    PageNode,
    PageRef,
    PendingDelivery,
    RelatedPage,
    SearchHit,
    SnippetPart,
    UploadHit,
    User,
    Webhook,
    Workspace,
)

logger = logging.getLogger(__name__)

DEFAULT_DATABASE_URL = "postgresql://doction:doction@localhost:5432/doction"
DEFAULT_DATA_DIR = "data"
DEFAULT_WORKSPACE_NAME = "Personal"
DEFAULT_WORKSPACE_SLUG = "personal"

_pool: ConnectionPool[Connection[DictRow]] | None = None
_pool_lock = threading.Lock()


def database_url() -> str:
    return os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)


def masked_database_url() -> str:
    """`database_url()` with the credentials stripped, safe to log."""
    parts = urlsplit(database_url())
    if parts.password is None:
        return urlunsplit(parts)
    host = f"{parts.hostname or ''}"
    if parts.port:
        host += f":{parts.port}"
    netloc = f"{parts.username}:***@{host}" if parts.username else f"***@{host}"
    return urlunsplit(parts._replace(netloc=netloc))


def data_dir() -> Path:
    """Where the page git repo and the uploads live; unrelated to the database."""
    d = Path(os.environ.get("DATA_DIR", DEFAULT_DATA_DIR))
    d.mkdir(parents=True, exist_ok=True)
    return d


def _get_pool() -> ConnectionPool[Connection[DictRow]]:
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                _pool = ConnectionPool(
                    database_url(),
                    min_size=1,
                    max_size=10,
                    # `connection_class` repeats the kwargs row_factory, but it is what
                    # types rows as dicts rather than tuples for the checker.
                    connection_class=Connection[DictRow],
                    kwargs={"row_factory": dict_row},
                    open=True,
                    # Check the connection on checkout, so a Postgres restart
                    # reconnects instead of failing until dead connections recycle.
                    check=ConnectionPool[Connection[DictRow]].check_connection,
                )
    return _pool


def connect():
    """A pooled connection: commits on exit, rolls back on exception."""
    return _get_pool().connection()


def reset_pool() -> None:
    """Close the current pool; the next connect() builds a new one. Tests only."""
    global _pool
    with _pool_lock:
        if _pool is not None:
            _pool.close()
            _pool = None


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


# ── Rows to dataclasses ──────────────────────────────────────────────────────
# .get(...) throughout, so a column a query did not select comes back as None.


def _to_user(row: dict) -> User:
    return User(
        id=row["id"],
        email=row["email"],
        password_hash=row["password_hash"],
        created_at=row["created_at"],
        display_name=row.get("display_name"),
        avatar_color=normalize_color(row.get("avatar_color")),
        token_version=row.get("token_version") or 0,
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


# ── Schema ───────────────────────────────────────────────────────────────────
# The final shape, with no migration ladder. `search_vector` is a generated column,
# so Postgres keeps it in sync without triggers.
SCHEMA_STATEMENTS: list[LiteralString] = [
    """
    CREATE TABLE IF NOT EXISTS users (
        id            BIGSERIAL PRIMARY KEY,
        email         TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        created_at    TEXT NOT NULL,
        display_name  TEXT,
        avatar_color  TEXT,
        token_version INTEGER NOT NULL DEFAULT 0
    )
    """,
    # For databases predating token_version.
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS token_version INTEGER NOT NULL DEFAULT 0",
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
            setweight(to_tsvector('doction', coalesce(title, '')), 'A') ||
            setweight(to_tsvector('doction', coalesce(content, '')), 'B')
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
    # dst_slug is kept alongside the resolved page because it is the only
    # representation a broken link has, and a broken link is information.
    (
        "ALTER TABLE page_links ADD COLUMN IF NOT EXISTS dst_page_id BIGINT "
        "REFERENCES pages(id) ON DELETE SET NULL"
    ),
    "CREATE INDEX IF NOT EXISTS page_links_dst_page_idx ON page_links(dst_page_id)",
    # Idempotent backfill: resolve links that already existed.
    """
    UPDATE page_links l SET dst_page_id = p.id
    FROM pages p
    WHERE l.dst_page_id IS NULL
      AND p.workspace_id = l.workspace_id
      AND p.slug = l.dst_slug
      AND p.deleted_at IS NULL
    """,
    # An old slug resolves forever, so renaming never breaks [[wikilinks]] already
    # written in other pages' markdown.
    """
    CREATE TABLE IF NOT EXISTS page_aliases (
        workspace_id BIGINT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
        slug         TEXT   NOT NULL,
        page_id      BIGINT NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
        created_at   TEXT   NOT NULL,
        PRIMARY KEY (workspace_id, slug)
    )
    """,
    "CREATE INDEX IF NOT EXISTS page_aliases_page_idx ON page_aliases(page_id)",
    # Outgoing webhooks. Deliveries queue in a table, not in memory, so a dead
    # receiver or a restart loses no events.
    """
    CREATE TABLE IF NOT EXISTS webhooks (
        id              BIGSERIAL PRIMARY KEY,
        workspace_id    BIGINT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
        url             TEXT   NOT NULL,
        secret          TEXT   NOT NULL,
        events          TEXT   NOT NULL DEFAULT '',
        active          BOOLEAN NOT NULL DEFAULT TRUE,
        created_at      TEXT   NOT NULL,
        last_status     TEXT,
        last_attempt_at TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS webhooks_ws_idx ON webhooks(workspace_id)",
    """
    CREATE TABLE IF NOT EXISTS webhook_deliveries (
        id              BIGSERIAL PRIMARY KEY,
        webhook_id      BIGINT NOT NULL REFERENCES webhooks(id) ON DELETE CASCADE,
        event           TEXT   NOT NULL,
        payload_json    TEXT   NOT NULL,
        attempts        INTEGER NOT NULL DEFAULT 0,
        next_attempt_at TEXT   NOT NULL,
        delivered_at    TEXT,
        last_error      TEXT
    )
    """,
    # The worker looks for pending rows by (delivered_at IS NULL, next_attempt_at).
    (
        "CREATE INDEX IF NOT EXISTS webhook_deliveries_due_idx "
        "ON webhook_deliveries(next_attempt_at) WHERE delivered_at IS NULL"
    ),
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
    # ADD COLUMN IF NOT EXISTS because page_chunks already exists on any live
    # deployment, and the CREATE above will not touch a table that is already there.
    "ALTER TABLE page_chunks ADD COLUMN IF NOT EXISTS path TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE page_chunks ADD COLUMN IF NOT EXISTS chunker TEXT NOT NULL DEFAULT ''",
    "CREATE INDEX IF NOT EXISTS page_chunks_ws_idx ON page_chunks(workspace_id)",
    "CREATE INDEX IF NOT EXISTS page_chunks_page_idx ON page_chunks(page_id)",
    """
    CREATE TABLE IF NOT EXISTS upload_texts (
        name          TEXT NOT NULL,
        workspace_id  BIGINT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
        user_id       BIGINT REFERENCES users(id) ON DELETE SET NULL,
        text          TEXT NOT NULL,
        created_at    TEXT NOT NULL,
        search_vector tsvector GENERATED ALWAYS AS (
            to_tsvector('doction', coalesce(text, ''))
        ) STORED,
        PRIMARY KEY (name, workspace_id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS upload_texts_search_idx ON upload_texts USING GIN(search_vector)",
]


def _unique_workspace_slug(
    conn,
    base: str,
    *,
    ignore_id: int | None = None,
) -> str:
    """Globally unique slug: it is also the directory name in the git repo."""
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
    missing = conn.execute("""
        SELECT u.id
        FROM users u
        LEFT JOIN workspaces w ON w.user_id = u.id
        GROUP BY u.id
        HAVING COUNT(w.id) = 0
        """).fetchall()
    for row in missing:
        user_id = int(row["id"])
        slug = _unique_workspace_slug(conn, DEFAULT_WORKSPACE_SLUG)
        conn.execute(
            "INSERT INTO workspaces (user_id, slug, name, created_at) VALUES (%s, %s, %s, %s)",
            (user_id, slug, DEFAULT_WORKSPACE_NAME, _now()),
        )


def _ensure_member_owners(conn) -> None:
    """Idempotent backfill: each workspace's creator becomes its 'owner' member."""
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
    """Rebuild a page's frontmatter, tags and links. Idempotent per page_id."""
    fm, _ = meta.parse_frontmatter(content)
    conn.execute("DELETE FROM page_meta WHERE page_id = %s", (page_id,))
    conn.execute(
        "INSERT INTO page_meta (page_id, type, frontmatter_json) VALUES (%s, %s, %s)",
        (page_id, meta.page_type(content), json.dumps(fm, ensure_ascii=False)),
    )

    conn.execute("DELETE FROM page_tags WHERE page_id = %s", (page_id,))
    tags = [(page_id, tag) for tag in meta.extract_tags(content)]
    if tags:
        conn.cursor().executemany("INSERT INTO page_tags (page_id, tag) VALUES (%s, %s)", tags)

    conn.execute("DELETE FROM page_links WHERE src_page_id = %s", (page_id,))
    seen: set[str] = set()
    edges: list[tuple[int, str, int, int, str, int, str]] = []
    for target in meta.extract_links(content):
        dst = slugify(target)
        if dst not in seen:
            seen.add(dst)
            # The values repeat because the subquery looks for the target among
            # pages first and then among the aliases.
            edges.append((page_id, dst, workspace_id, workspace_id, dst, workspace_id, dst))
    if edges:
        # NULL when the target does not exist yet; create_page fills it in later.
        conn.cursor().executemany(
            """
            INSERT INTO page_links (src_page_id, dst_slug, workspace_id, dst_page_id)
            VALUES (
                %s, %s, %s,
                (SELECT id FROM pages
                 WHERE workspace_id = %s AND slug = %s AND deleted_at IS NULL
                 UNION ALL
                 SELECT page_id FROM page_aliases
                 WHERE workspace_id = %s AND slug = %s
                 LIMIT 1)
            )
            """,
            edges,
        )

    # Content changed: mark for re-embedding by the async worker.
    conn.execute("UPDATE pages SET embed_dirty = 1 WHERE id = %s", (page_id,))


# Our own search configuration: fold accents before stemming. A bare `unaccent()` is
# STABLE, not IMMUTABLE, so Postgres rejects it in a generated column; chained inside a
# named configuration it is fine, because to_tsvector(regconfig, text) is IMMUTABLE.
# The stemmer is English by measurement: `spanish_stem` scores 0.00 MRR on English
# queries. See evals/results/2026-08-24-minilm-en.json.
TS_CONFIG = "doction"
_TS_STEMMER = "english_stem"
_TS_WORD_TOKENS = "asciiword, asciihword, hword_asciipart, word, hword, hword_part"


def _ensure_text_search_config(conn) -> bool:
    """Create or update the `doction` configuration; True when its mapping changed.

    Without the `unaccent` extension the configuration falls back to the stemmer alone:
    search loses accent folding but the server still boots.
    """
    unaccent = True
    try:
        conn.execute("CREATE EXTENSION IF NOT EXISTS unaccent")
    except Exception:
        conn.rollback()
        unaccent = False
        logger.warning(
            "could not create the unaccent extension; %s has no accent folding "
            "(unaccented queries against accented pages will miss)",
            TS_CONFIG,
        )

    dictionaries = f"unaccent, {_TS_STEMMER}" if unaccent else _TS_STEMMER
    existing = conn.execute(
        """
        SELECT string_agg(d.dictname, ', ' ORDER BY m.mapseqno) AS dicts
        FROM pg_ts_config c
        JOIN pg_ts_config_map m ON m.mapcfg = c.oid
        JOIN pg_ts_dict d ON d.oid = m.mapdict
        JOIN ts_token_type(c.cfgparser) t ON t.tokid = m.maptokentype
        WHERE c.cfgname = %s AND t.alias = 'word'
        """,
        (TS_CONFIG,),
    ).fetchone()

    if existing is not None and existing["dicts"] == dictionaries:
        return False

    if existing is None or existing["dicts"] is None:
        conn.execute(f"CREATE TEXT SEARCH CONFIGURATION {TS_CONFIG} ( COPY = english )")
    conn.execute(
        f"ALTER TEXT SEARCH CONFIGURATION {TS_CONFIG} "
        f"ALTER MAPPING FOR {_TS_WORD_TOKENS} WITH {dictionaries}"
    )
    logger.info("search configuration %s -> %s", TS_CONFIG, dictionaries)
    return True


# Postgres computes generated columns on write, so neither a new definition nor a
# changed configuration mapping reaches an existing database on its own. Rather than a
# migration ladder, this compares the stored state against what the code declares and
# converges — which also makes rolling back to an older image work.
_SEARCH_VECTOR_COLUMNS = {
    "pages": (
        "setweight(to_tsvector('doction', coalesce(title, '')), 'A') || "
        "setweight(to_tsvector('doction', coalesce(content, '')), 'B')",
        "pages_search_idx",
    ),
    "upload_texts": (
        "to_tsvector('doction', coalesce(text, ''))",
        "upload_texts_search_idx",
    ),
}


def _converge_search_vectors(conn, *, force: bool) -> None:
    """Rebuild any `search_vector` column not built on the current configuration."""
    for table, (expression, index) in _SEARCH_VECTOR_COLUMNS.items():
        row = conn.execute(
            """
            SELECT pg_get_expr(d.adbin, d.adrelid) AS expr
            FROM pg_attrdef d
            JOIN pg_attribute a ON a.attrelid = d.adrelid AND a.attnum = d.adnum
            WHERE d.adrelid = %s::regclass AND a.attname = 'search_vector'
            """,
            (table,),
        ).fetchone()
        current = (row["expr"] if row else None) or ""
        if not force and f"'{TS_CONFIG}'" in current:
            continue
        # DROP COLUMN takes the GIN index with it, so it is recreated below.
        conn.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS search_vector")
        conn.execute(
            f"ALTER TABLE {table} ADD COLUMN search_vector tsvector "
            f"GENERATED ALWAYS AS ({expression}) STORED"
        )
        conn.execute(f"CREATE INDEX IF NOT EXISTS {index} ON {table} USING GIN(search_vector)")
        logger.info("rebuilt %s.search_vector on %s", table, TS_CONFIG)


def init_db() -> None:
    """Create the schema (idempotent) and run the defensive backfills."""
    with connect() as conn:
        mapping_changed = _ensure_text_search_config(conn)
        for stmt in SCHEMA_STATEMENTS:
            conn.execute(stmt)
        _converge_search_vectors(conn, force=mapping_changed)
        _ensure_default_workspaces(conn)
        _ensure_member_owners(conn)


# A ceiling on what one request can cost when a parser turns out worse than believed,
# not the ReDoS fix (that is the linear pattern in meta.py). It lives here and not in
# the Pydantic models because MCP calls create_page/update_page directly, and the agent
# surface is where an enormous page is easiest to generate.
MAX_CONTENT_BYTES = 1024 * 1024


def _check_content_size(content: str) -> None:
    size = len(content.encode("utf-8"))
    if size > MAX_CONTENT_BYTES:
        raise ValueError(
            f"page content is {size:,} bytes, over the {MAX_CONTENT_BYTES:,}-byte limit"
        )


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
    """Unique slug within the workspace; collisions get -2, -3, ..."""
    candidate = base
    suffix = 1
    while True:
        # An alias holds a name as firmly as a live page does; otherwise a rename
        # could steal the slug from an old link that still resolves.
        row = conn.execute(
            """
            SELECT id FROM pages WHERE slug = %s AND workspace_id = %s
            UNION ALL
            SELECT page_id AS id FROM page_aliases WHERE slug = %s AND workspace_id = %s
            """,
            (candidate, workspace_id, candidate, workspace_id),
        ).fetchone()
        if row is None or row["id"] == ignore_id:
            return candidate
        suffix += 1
        candidate = f"{base}-{suffix}"


def create_user(email: str, password_hash: str) -> int:
    with connect() as conn:
        row = conn.execute(
            "INSERT INTO users (email, password_hash, created_at) VALUES (%s, %s, %s) RETURNING id",
            (email, password_hash, _now()),
        ).fetchone()
        assert row is not None
        return int(row["id"])


def has_users() -> bool:
    """Whether any user exists yet, for the first-run flow."""
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


def update_user_password(user_id: int, password_hash: str) -> int:
    """Change the password and bump token_version, invalidating every JWT issued before.

    Returns the new version, so the current session can be reissued.
    """
    with connect() as conn:
        row = conn.execute(
            "UPDATE users SET password_hash = %s, token_version = token_version + 1 "
            "WHERE id = %s RETURNING token_version",
            (password_hash, user_id),
        ).fetchone()
        return int(row["token_version"]) if row else 0


def list_workspaces(user_id: int) -> list[Workspace]:
    """Workspaces the user is a member of, own and shared, each with their role."""
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
    """Resolve a workspace by slug, only if the user is a member."""
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
        assert row is not None
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
    """Delete the workspace and its pages; refuses to delete the last one."""
    with connect() as conn:
        total = conn.execute(
            "SELECT COUNT(*) AS n FROM workspaces WHERE user_id = %s", (user_id,)
        ).fetchone()
        assert total is not None
        if total["n"] <= 1:
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
    """The user's role in the workspace ('owner' | 'member'), or None if not a member."""
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
            assert row is not None
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


def list_pages_tree(workspace_id: int) -> list[PageNode]:
    """Flat DFS list carrying `depth`, for rendering the sidebar tree."""
    with connect() as conn:
        rows = conn.execute(
            # Unfiled notes (type: memo, no parent) live in the paginated feed, not
            # here: this query does not paginate and the sidebar draws all of it.
            # Moving one under a parent is what files it into the tree.
            "SELECT p.id, p.slug, p.title, p.parent_id FROM pages p "
            "LEFT JOIN page_meta m ON m.page_id = p.id "
            "WHERE p.workspace_id = %s AND p.deleted_at IS NULL "
            "AND (m.type IS NULL OR m.type <> 'memo' OR p.parent_id IS NOT NULL) "
            "ORDER BY p.created_at, p.id",
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


def get_page(slug: str, workspace_id: int) -> Page | None:
    # Membership was checked when the workspace was resolved; workspace_id is enough.
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
        if row is None:
            # A rename leaves an alias so [[wikilinks]] already written keep resolving.
            alias = conn.execute(
                "SELECT page_id FROM page_aliases WHERE slug = %s AND workspace_id = %s",
                (slug, workspace_id),
            ).fetchone()
            if alias is not None:
                row = conn.execute(
                    """
                    SELECT p.*, parent.slug AS parent_slug, parent.title AS parent_title,
                           editor.email AS updated_by_email,
                           editor.display_name AS updated_by_name
                    FROM pages p
                    LEFT JOIN pages parent ON parent.id = p.parent_id
                    LEFT JOIN users editor ON editor.id = p.updated_by
                    WHERE p.id = %s AND p.deleted_at IS NULL
                    """,
                    (alias["page_id"],),
                ).fetchone()
        return _to_page(row) if row else None


def get_ancestors(page_id: int, workspace_id: int) -> list[PageRef]:
    """The ancestor chain from the root down to the direct parent, page excluded."""
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
    _check_content_size(content)
    title = title.strip() or meta.derive_title(content)
    # With no requested slug and no title, the slug comes from a timestamp: derived
    # from the title, a hundred untitled notes would be untitled-2 ... -101.
    if requested_slug:
        base_slug = slugify(requested_slug.strip())
    elif title == meta.UNTITLED:
        base_slug = f"nota-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}"
    else:
        base_slug = slugify(title)
    now = _now()

    with connect() as conn:
        parent_id = _resolve_parent_id(
            conn,
            parent_slug,
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
        assert row is not None
        page_id = int(row["id"])
        _index_page_meta(conn, page_id, workspace_id, content)
        # Forward references: links written before their target existed would stay
        # broken forever otherwise.
        conn.execute(
            """
            UPDATE page_links SET dst_page_id = %s
            WHERE dst_page_id IS NULL AND workspace_id = %s AND dst_slug = %s
            """,
            (page_id, workspace_id, slug),
        )
        emit_event(conn, workspace_id, "page.created", {"page": {"slug": slug, "title": title}})
        return slug


def update_page(user_id: int, workspace_id: int, slug: str, title: str, content: str) -> str | None:
    """Update a page, keeping its slug stable; returns the slug, or None if missing."""
    _check_content_size(content)
    title = title.strip() or meta.derive_title(content)
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
        emit_event(conn, workspace_id, "page.updated", {"page": {"slug": slug, "title": title}})
        return slug


def upsert_page_section(
    user_id: int,
    workspace_id: int,
    slug: str,
    heading: str,
    body: str,
    *,
    level: int = 2,
    parent: str | None = None,
) -> str | None:
    """Write a single section of a page. Returns the slug, or None if it does not exist.

    Goes through `update_page` rather than its own UPDATE, so the version lands in git
    history, the page is re-queued for indexing and the webhook event fires like any
    other write. Reading and writing inside one call also means two agents editing
    different sections do not overwrite each other. `AmbiguousSection` propagates.
    """
    page = get_page(slug, workspace_id)
    if page is None:
        return None
    content = meta.upsert_section(page.content, heading, body, level=level, parent=parent)
    if content == page.content:
        return slug
    return update_page(user_id, workspace_id, slug, page.title, content)


# ── Outgoing webhooks ────────────────────────────────────────────────────────
# emit_event() runs inside the transaction that made the write, so the event queues in
# the same commit as the change. Delivery is the worker's job; no HTTP happens here.

MAX_DELIVERY_ATTEMPTS = 6


def emit_event(conn, workspace_id: int, event: str, payload: dict) -> None:
    """Queue `event` for the workspace's active webhooks that listen for it."""
    rows = conn.execute(
        "SELECT id, events FROM webhooks WHERE workspace_id = %s AND active",
        (workspace_id,),
    ).fetchall()
    if not rows:
        return
    body = json.dumps({**payload, "event": event, "at": _now()}, ensure_ascii=False)
    now = _now()
    encolar = [
        (r["id"], event, body, now)
        for r in rows
        # Empty events means all; otherwise a comma-separated list.
        if not r["events"] or event in {e.strip() for e in r["events"].split(",")}
    ]
    if encolar:
        conn.cursor().executemany(
            "INSERT INTO webhook_deliveries (webhook_id, event, payload_json, next_attempt_at) "
            "VALUES (%s, %s, %s, %s)",
            encolar,
        )


def list_webhooks(workspace_id: int) -> list[Webhook]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, workspace_id, url, events, active, created_at, last_status, "
            "last_attempt_at FROM webhooks WHERE workspace_id = %s ORDER BY id",
            (workspace_id,),
        ).fetchall()
        return [
            Webhook(
                id=r["id"],
                workspace_id=r["workspace_id"],
                url=r["url"],
                events=r["events"],
                active=r["active"],
                created_at=r["created_at"],
                last_status=r["last_status"],
                last_attempt_at=r["last_attempt_at"],
            )
            for r in rows
        ]


def create_webhook(workspace_id: int, url: str, secret: str, events: str = "") -> int:
    with connect() as conn:
        row = conn.execute(
            "INSERT INTO webhooks (workspace_id, url, secret, events, created_at) "
            "VALUES (%s, %s, %s, %s, %s) RETURNING id",
            (workspace_id, url, secret, events, _now()),
        ).fetchone()
        assert row is not None
        return int(row["id"])


def delete_webhook(workspace_id: int, webhook_id: int) -> bool:
    with connect() as conn:
        cur = conn.execute(
            "DELETE FROM webhooks WHERE id = %s AND workspace_id = %s",
            (webhook_id, workspace_id),
        )
        return cur.rowcount > 0


def due_deliveries(limit: int = 10) -> list[PendingDelivery]:
    """Pending deliveries whose retry time has come."""
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT d.id, d.webhook_id, w.url, w.secret, d.event, d.payload_json, d.attempts
            FROM webhook_deliveries d
            JOIN webhooks w ON w.id = d.webhook_id
            WHERE d.delivered_at IS NULL AND d.next_attempt_at <= %s AND w.active
            ORDER BY d.id
            LIMIT %s
            """,
            (_now(), limit),
        ).fetchall()
        return [
            PendingDelivery(
                id=r["id"],
                webhook_id=r["webhook_id"],
                url=r["url"],
                secret=r["secret"],
                event=r["event"],
                payload_json=r["payload_json"],
                attempts=r["attempts"],
            )
            for r in rows
        ]


def _delivery_status(delivered_at: str | None, last_error: str | None) -> str:
    """`delivered_at` means "no longer retried", not "succeeded".

    The worker also sets it when retries run out, leaving `last_error` behind, so both
    columns have to be read together.
    """
    if delivered_at is None:
        return "pending"
    return "failed" if last_error else "delivered"


def list_deliveries(webhook_id: int, limit: int = 20) -> list[Delivery]:
    """A webhook's recent deliveries, newest first.

    No `payload_json`: the event body carries page content and this is an operational
    view of what went out and what did not.
    """
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, webhook_id, event, attempts, last_error, next_attempt_at, delivered_at "
            "FROM webhook_deliveries WHERE webhook_id = %s ORDER BY id DESC LIMIT %s",
            (webhook_id, limit),
        ).fetchall()
        return [
            Delivery(
                id=r["id"],
                webhook_id=r["webhook_id"],
                event=r["event"],
                status=_delivery_status(r["delivered_at"], r["last_error"]),
                attempts=r["attempts"],
                last_error=r["last_error"],
                next_attempt_at=r["next_attempt_at"],
                delivered_at=r["delivered_at"],
            )
            for r in rows
        ]


def delivery_counts(workspace_id: int) -> dict[int, dict[str, int]]:
    """Pending and failed counts per webhook, aggregated in one query rather than N+1."""
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT d.webhook_id,
                   COUNT(*) FILTER (WHERE d.delivered_at IS NULL) AS pending,
                   COUNT(*) FILTER (
                       WHERE d.delivered_at IS NOT NULL AND d.last_error IS NOT NULL
                   ) AS failed
            FROM webhook_deliveries d
            JOIN webhooks w ON w.id = d.webhook_id
            WHERE w.workspace_id = %s
            GROUP BY d.webhook_id
            """,
            (workspace_id,),
        ).fetchall()
        return {r["webhook_id"]: {"pending": r["pending"], "failed": r["failed"]} for r in rows}


def mark_delivered(delivery_id: int, webhook_id: int, status: str) -> None:
    now = _now()
    with connect() as conn:
        conn.execute(
            "UPDATE webhook_deliveries SET delivered_at = %s, attempts = attempts + 1, "
            "last_error = NULL WHERE id = %s",
            (now, delivery_id),
        )
        conn.execute(
            "UPDATE webhooks SET last_status = %s, last_attempt_at = %s WHERE id = %s",
            (status, now, webhook_id),
        )


def mark_failed(delivery_id: int, webhook_id: int, error: str, attempts: int) -> None:
    """Reschedule with exponential backoff; marks the delivery once retries run out."""
    now = datetime.now(UTC)
    # 1min, 2, 4, 8, 16...
    wait = timedelta(minutes=2 ** min(attempts, 5))
    next_attempt = (now + wait).isoformat(timespec="seconds")
    exhausted = attempts + 1 >= MAX_DELIVERY_ATTEMPTS
    with connect() as conn:
        conn.execute(
            "UPDATE webhook_deliveries SET attempts = attempts + 1, last_error = %s, "
            "next_attempt_at = %s, delivered_at = %s WHERE id = %s",
            (
                error[:500],
                next_attempt,
                now.isoformat(timespec="seconds") if exhausted else None,
                delivery_id,
            ),
        )
        conn.execute(
            "UPDATE webhooks SET last_status = %s, last_attempt_at = %s WHERE id = %s",
            (error[:200], now.isoformat(timespec="seconds"), webhook_id),
        )


def move_page(workspace_id: int, slug: str, parent_slug: str | None) -> str | None:
    """Reparent a page; returns its slug, or None if it does not exist.

    The git repo is flat (`{workspace}/{slug}.md`), so a move touches no file.
    Raises ValueError when the target is missing or the move would create a cycle.
    """
    with connect() as conn:
        row = conn.execute(
            "SELECT id FROM pages WHERE slug = %s AND workspace_id = %s AND deleted_at IS NULL",
            (slug, workspace_id),
        ).fetchone()
        if row is None:
            return None
        page_id = int(row["id"])

        parent_id: int | None = None
        if parent_slug:
            parent = conn.execute(
                "SELECT id FROM pages WHERE slug = %s AND workspace_id = %s AND deleted_at IS NULL",
                (parent_slug, workspace_id),
            ).fetchone()
            if parent is None:
                raise ValueError(f"parent not found: {parent_slug}")
            parent_id = int(parent["id"])

        # pages.parent_id has no constraint against cycles and list_pages_tree's DFS
        # would hang, so the ancestors are checked first.
        ancestor = parent_id
        seen: set[int] = set()
        while ancestor is not None and ancestor not in seen:
            if ancestor == page_id:
                raise ValueError("a page cannot become its own descendant")
            seen.add(ancestor)
            up = conn.execute("SELECT parent_id FROM pages WHERE id = %s", (ancestor,)).fetchone()
            ancestor = up["parent_id"] if up else None

        conn.execute(
            "UPDATE pages SET parent_id = %s, updated_at = %s WHERE id = %s",
            (parent_id, _now(), page_id),
        )
        emit_event(
            conn,
            workspace_id,
            "page.moved",
            {"page": {"slug": slug}, "parent_slug": parent_slug},
        )
        return slug


def rename_page(workspace_id: int, slug: str, new_slug: str) -> str | None:
    """Change the slug, leaving an alias behind; returns the new one, or None.

    The linking pages' markdown is not rewritten — that would produce git commits on
    pages the user never edited. The alias keeps existing [[wikilinks]] alive.
    """
    base = slugify(new_slug)
    if not base:
        raise ValueError("empty slug")
    with connect() as conn:
        row = conn.execute(
            "SELECT id, slug FROM pages "
            "WHERE slug = %s AND workspace_id = %s AND deleted_at IS NULL",
            (slug, workspace_id),
        ).fetchone()
        if row is None:
            return None
        page_id = int(row["id"])
        previous = str(row["slug"])
        if base == previous:
            return previous

        final = unique_slug(conn, base, workspace_id=workspace_id, ignore_id=page_id)
        now = _now()
        conn.execute(
            "UPDATE pages SET slug = %s, updated_at = %s WHERE id = %s", (final, now, page_id)
        )
        conn.execute(
            "INSERT INTO page_aliases (workspace_id, slug, page_id, created_at) "
            "VALUES (%s, %s, %s, %s) ON CONFLICT (workspace_id, slug) DO NOTHING",
            (workspace_id, previous, page_id, now),
        )
        # dst_page_id is the truth and does not change; dst_slug is a display cache.
        conn.execute("UPDATE page_links SET dst_slug = %s WHERE dst_page_id = %s", (final, page_id))
        emit_event(
            conn,
            workspace_id,
            "page.renamed",
            {"page": {"slug": final}, "previous_slug": previous},
        )
        return final


def list_children(workspace_id: int, slug: str) -> list[PageRef] | None:
    """A page's direct children, or None if the page does not exist."""
    with connect() as conn:
        row = conn.execute(
            "SELECT id FROM pages WHERE slug = %s AND workspace_id = %s AND deleted_at IS NULL",
            (slug, workspace_id),
        ).fetchone()
        if row is None:
            return None
        rows = conn.execute(
            "SELECT slug, title FROM pages "
            "WHERE parent_id = %s AND deleted_at IS NULL ORDER BY title",
            (row["id"],),
        ).fetchall()
        return [PageRef(slug=r["slug"], title=r["title"]) for r in rows]


def list_notes(workspace_id: int, *, limit: int = 50, before: str | None = None) -> list[NoteRef]:
    """Cursor-paginated feed of unfiled notes.

    The inbox is `type: memo` *and* parentless, so moving a note under any page files it
    into the tree. Separate from list_pages_tree, which paginates nothing.
    """
    limit = max(1, min(limit, 200))
    sql = """
        SELECT p.slug, p.title, p.created_at, p.content
        FROM pages p
        JOIN page_meta m ON m.page_id = p.id
        WHERE p.workspace_id = %s AND p.deleted_at IS NULL
          AND m.type = 'memo' AND p.parent_id IS NULL
    """
    params: list[object] = [workspace_id]
    if before:
        sql += " AND p.created_at < %s"
        params.append(before)
    sql += " ORDER BY p.created_at DESC LIMIT %s"
    params.append(limit)
    with connect() as conn:
        rows = conn.execute(sql, params).fetchall()  # type: ignore[arg-type]
        return [
            NoteRef(
                slug=r["slug"],
                title=r["title"],
                created_at=r["created_at"],
                # Trimmed after the frontmatter is stripped: cut in SQL, the excerpt
                # showed `--- type: memo ---` as if it were the note.
                excerpt=meta.parse_frontmatter(r["content"] or "")[1].strip()[:200],
            )
            for r in rows
        ]


def delete_page(workspace_id: int, slug: str) -> bool:
    """Soft delete: move the page to the trash, recoverably.

    Neither the git file nor the derived data is removed; the page just stops appearing
    in listings, search and links.
    """
    with connect() as conn:
        cur = conn.execute(
            "UPDATE pages SET deleted_at = %s WHERE slug = %s AND workspace_id = %s "
            "AND deleted_at IS NULL",
            (_now(), slug, workspace_id),
        )
        if cur.rowcount > 0:
            emit_event(conn, workspace_id, "page.deleted", {"page": {"slug": slug}})
        return cur.rowcount > 0


def list_deleted_pages(workspace_id: int) -> list[Page]:
    """Pages in the workspace trash, most recent first."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT slug, title, deleted_at FROM pages "
            "WHERE workspace_id = %s AND deleted_at IS NOT NULL "
            "ORDER BY deleted_at DESC",
            (workspace_id,),
        ).fetchall()
        return [_to_page(row) for row in rows]


def restore_page(workspace_id: int, slug: str) -> bool:
    """Take a page back out of the trash."""
    with connect() as conn:
        cur = conn.execute(
            "UPDATE pages SET deleted_at = NULL WHERE slug = %s AND workspace_id = %s "
            "AND deleted_at IS NOT NULL",
            (slug, workspace_id),
        )
        return cur.rowcount > 0


def purge_page(workspace_id: int, slug: str) -> bool:
    """Permanently delete a page already in the trash; CASCADE clears its derived rows."""
    with connect() as conn:
        cur = conn.execute(
            "DELETE FROM pages WHERE slug = %s AND workspace_id = %s AND deleted_at IS NOT NULL",
            (slug, workspace_id),
        )
        return cur.rowcount > 0


def pages_for_export(workspace_id: int) -> list[Page]:
    """Live pages of a workspace, for the markdown export."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT slug, title, content FROM pages "
            "WHERE workspace_id = %s AND deleted_at IS NULL ORDER BY slug",
            (workspace_id,),
        ).fetchall()
        return [_to_page(row) for row in rows]


def list_child_pages(workspace_id: int, parent_id: int) -> list[Page]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT slug, title, updated_at FROM pages "
            "WHERE workspace_id = %s AND parent_id = %s AND deleted_at IS NULL "
            "ORDER BY updated_at DESC",
            (workspace_id, parent_id),
        ).fetchall()
        return [_to_page(row) for row in rows]


def _fts_query(raw: str) -> str:
    """Turn user input into a safe prefix tsquery.

    The terms are already filtered to \\w+, so `term:*` is always valid tsquery syntax
    and there is nothing to inject.
    """
    terms = re.findall(r"[\w]+", raw, flags=re.UNICODE)
    if not terms:
        return ""
    return " & ".join(f"{term}:*" for term in terms)


# ts_headline marks matches with these control characters rather than <mark>, so the
# snippet leaves here as text and the highlighting as positions: page content cannot
# re-enter the DOM as HTML. Control characters because `translate()` strips them from
# the input first, so a marked span can only have come from the highlighter.
_MARK_OPEN = "\x01"
_MARK_CLOSE = "\x02"
_HEADLINE_OPTS = (
    f"StartSel={_MARK_OPEN}, StopSel={_MARK_CLOSE}, MaxWords=12, MinWords=1, MaxFragments=1"
)


def _split_snippet(marked: str) -> tuple[str, list[SnippetPart]]:
    """Split a ts_headline snippet into (plain text, spans)."""
    parts: list[SnippetPart] = []
    rest = marked or ""
    while rest:
        before, opened, rest = rest.partition(_MARK_OPEN)
        if before:
            parts.append(SnippetPart(text=before, match=False))
        if not opened:
            break
        hit, _, rest = rest.partition(_MARK_CLOSE)
        if hit:
            parts.append(SnippetPart(text=hit, match=True))
    return "".join(part.text for part in parts), parts


def search_pages(
    workspace_id: int,
    query: str,
    limit: int = 20,
    tags: list[str] | None = None,
) -> list[SearchHit]:
    """Lexical workspace search, optionally narrowed by tags.

    The filter is inside the query, not applied to its result: filtering after the LIMIT
    would return fewer pages than exist.
    """
    match = _fts_query(query)
    if not match:
        return []
    # LiteralString fragments keep the f-string below a LiteralString too, so the
    # checker proves no user input reaches the SQL; its values travel through %s.
    tag_join: LiteralString = ""
    tag_params: list = []
    if tags:
        tag_join = (
            " AND EXISTS (SELECT 1 FROM page_tags t WHERE t.page_id = p.id AND t.tag = ANY(%s))"
        )
        tag_params = [[t.strip().lstrip("#").lower() for t in tags if t.strip()]]
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT p.slug, p.title,
                   ts_headline(
                       'doction',
                       translate(
                           p.title || ' ' ||
                           -- Frontmatter is stripped from what is shown, not from
                           -- what is indexed: a snippet opening with
                           -- `--- type: memo ---` is metadata, not the note.
                           regexp_replace(p.content, '^---\n.*?\n---\n', ''),
                           %s, ''
                       ),
                       to_tsquery('doction', %s), %s
                   ) AS snippet
            FROM pages p
            WHERE p.search_vector @@ to_tsquery('doction', %s) AND p.workspace_id = %s
              AND p.deleted_at IS NULL{tag_join}
            ORDER BY ts_rank(p.search_vector, to_tsquery('doction', %s)) DESC
            LIMIT %s
            """,
            (
                _MARK_OPEN + _MARK_CLOSE,
                match,
                _HEADLINE_OPTS,
                match,
                workspace_id,
                *tag_params,
                match,
                limit,
            ),
        ).fetchall()
        hits = []
        for row in rows:
            text, parts = _split_snippet(row["snippet"])
            hits.append(SearchHit(slug=row["slug"], title=row["title"], snippet=text, parts=parts))
        return hits


def slugs_with_tags(workspace_id: int, tags: list[str]) -> set[str]:
    """Workspace slugs carrying any of the given tags.

    The vector list is filtered in memory and needs this allowed set; the lexical one
    filters in its own SQL.
    """
    wanted = [t.strip().lstrip("#").lower() for t in tags if t.strip()]
    if not wanted:
        return set()
    with connect() as conn:
        rows = conn.execute(
            "SELECT DISTINCT p.slug FROM pages p "
            "JOIN page_tags t ON t.page_id = p.id "
            "WHERE p.workspace_id = %s AND p.deleted_at IS NULL AND t.tag = ANY(%s)",
            (workspace_id, wanted),
        ).fetchall()
        return {r["slug"] for r in rows}


def _page_tags(conn, page_id: int) -> list[str]:
    rows = conn.execute(
        "SELECT tag FROM page_tags WHERE page_id = %s ORDER BY id", (page_id,)
    ).fetchall()
    return [r["tag"] for r in rows]


def get_page_meta(workspace_id: int, slug: str) -> PageMeta | None:
    """A page's frontmatter and tags, or None if it does not exist."""
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
    workspace_id: int,
    *,
    page_type: str | None = None,
    tag: str | None = None,
    limit: int = 200,
) -> list[ExtractedPage]:
    """Filter pages by frontmatter `type` and/or `tag`: structure without an LLM."""
    # LiteralString fragments keep the f-string below a LiteralString too, so the
    # checker proves no user input reaches the SQL; its values travel through %s.
    joins: LiteralString = ""
    params: list = []
    if tag:
        joins = "JOIN page_tags t ON t.page_id = p.id AND t.tag = %s"
        params.append(meta.normalize_tag(tag))
    where: list[LiteralString] = ["p.workspace_id = %s", "p.deleted_at IS NULL"]
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


def backlinks(workspace_id: int, slug: str) -> list[PageRef]:
    """Pages linking to `slug` through a [[slug]] wikilink."""
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT p.slug, p.title
            FROM page_links l
            JOIN pages p ON p.id = l.src_page_id
            LEFT JOIN pages dst ON dst.id = l.dst_page_id
            WHERE l.workspace_id = %s AND p.deleted_at IS NULL
              AND (dst.slug = %s OR (l.dst_page_id IS NULL AND l.dst_slug = %s))
            ORDER BY p.title
            """,
            (workspace_id, slug, slug),
        ).fetchall()
        return [PageRef(slug=r["slug"], title=r["title"]) for r in rows]


def mentions(workspace_id: int, slug: str) -> list[Mention]:
    """`backlinks` plus the sentence each link is written in.

    Cut in Python rather than SQL because the cut follows wikilink syntax, not text.
    """
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT p.slug, p.title, p.content
            FROM page_links l
            JOIN pages p ON p.id = l.src_page_id
            LEFT JOIN pages dst ON dst.id = l.dst_page_id
            WHERE l.workspace_id = %s AND p.deleted_at IS NULL
              AND (dst.slug = %s OR (l.dst_page_id IS NULL AND l.dst_slug = %s))
            ORDER BY p.title
            """,
            (workspace_id, slug, slug),
        ).fetchall()

    out: list[Mention] = []
    for row in rows:
        # The link may be written against the current slug or one a rename left behind;
        # when neither matches, the mention is still true and only the sentence is lost.
        found = meta.mention_context(row["content"] or "", slug)
        context: list[SnippetPart] = []
        if found:
            before, label, after = found
            if before:
                context.append(SnippetPart(text=before, match=False))
            context.append(SnippetPart(text=label, match=True))
            if after:
                context.append(SnippetPart(text=after, match=False))
        out.append(Mention(slug=row["slug"], title=row["title"], context=context))
    return out


def related_pages(workspace_id: int, slug: str, limit: int = 10) -> list[RelatedPage] | None:
    """Neighbours by shared-tag count, descending, or None if the page does not exist."""
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


def workspace_pages(workspace_id: int) -> list[Page]:
    """Live pages for the local ML functions (TF-IDF, suggestions, insights)."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, slug, title, content FROM pages "
            "WHERE workspace_id = %s AND deleted_at IS NULL ORDER BY id",
            (workspace_id,),
        ).fetchall()
        return [_to_page(row) for row in rows]


def page_outgoing_links(page_id: int) -> list[str]:
    """Target slugs of a page's outgoing wikilinks."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT dst_slug FROM page_links WHERE src_page_id = %s", (page_id,)
        ).fetchall()
        return [r["dst_slug"] for r in rows]


def workspace_links(workspace_id: int) -> list[LinkEdge]:
    """Every wikilink edge in the workspace; the source is live, the target may not exist."""
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT l.src_page_id, l.dst_slug
            FROM page_links l
            JOIN pages p ON p.id = l.src_page_id
            WHERE l.workspace_id = %s AND p.deleted_at IS NULL
            """,
            (workspace_id,),
        ).fetchall()
        return [LinkEdge(src_page_id=r["src_page_id"], dst_slug=r["dst_slug"]) for r in rows]


def workspace_tags(workspace_id: int) -> list[str]:
    """The workspace's live tag vocabulary, for aligning TF-IDF suggestions."""
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT t.tag
            FROM page_tags t
            JOIN pages p ON p.id = t.page_id
            WHERE p.workspace_id = %s AND p.deleted_at IS NULL
            """,
            (workspace_id,),
        ).fetchall()
        return [r["tag"] for r in rows]


def pages_to_embed(limit: int = 10) -> list[EmbedTarget]:
    """Pages marked embed_dirty and waiting to be embedded."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, workspace_id, title, content FROM pages "
            "WHERE embed_dirty = 1 AND workspace_id IS NOT NULL AND deleted_at IS NULL "
            "ORDER BY id LIMIT %s",
            (limit,),
        ).fetchall()
        return [
            EmbedTarget(
                id=r["id"],
                workspace_id=r["workspace_id"],
                title=r["title"] or "",
                content=r["content"],
            )
            for r in rows
        ]


def index_counts(workspace_id: int, model: str, chunker: str) -> tuple[int, int]:
    """(live pages, pages chunked by the current pipeline).

    Counts rather than content: `pages_to_embed` returns whole markdown to feed the
    worker, not to report how much is left.
    """
    with connect() as conn:
        row = conn.execute(
            """
            SELECT
                count(*) AS total,
                count(*) FILTER (
                    WHERE EXISTS (
                        SELECT 1 FROM page_chunks c
                        WHERE c.page_id = p.id AND c.model = %s AND c.chunker = %s
                    )
                ) AS indexed
            FROM pages p
            WHERE p.workspace_id = %s AND p.deleted_at IS NULL
            """,
            (model, chunker, workspace_id),
        ).fetchone()
        assert row is not None
        return int(row["total"]), int(row["indexed"])


def store_page_chunks(
    page_id: int,
    workspace_id: int,
    chunks: list[tuple[int, str, str, bytes]],
    model: str,
    chunker: str,
) -> None:
    """Atomically replace a page's chunks and vectors, clearing embed_dirty.

    Each chunk arrives as `(ord, text, path, vector)`.
    """
    now = _now()
    with connect() as conn:
        conn.execute("DELETE FROM page_chunks WHERE page_id = %s", (page_id,))
        if chunks:
            conn.cursor().executemany(
                "INSERT INTO page_chunks "
                "(page_id, workspace_id, ord, text, path, vector, model, chunker, created_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                [
                    (page_id, workspace_id, ord_, text, path, vec, model, chunker, now)
                    for ord_, text, path, vec in chunks
                ],
            )
        conn.execute("UPDATE pages SET embed_dirty = 0 WHERE id = %s", (page_id,))


def mark_stale_model_dirty(model: str, chunker: str) -> int:
    """Re-queue pages whose chunks did not come from the current pipeline.

    Two vectors are comparable only if the same encoder *and* the same chunker produced
    them: splitting a page differently changes what is embedded as much as the model does.
    """
    with connect() as conn:
        row = conn.execute(
            """
            WITH stale AS (
                SELECT DISTINCT page_id FROM page_chunks
                WHERE model <> %s OR chunker <> %s
            )
            UPDATE pages SET embed_dirty = 1
            WHERE id IN (SELECT page_id FROM stale)
            RETURNING id
            """,
            (model, chunker),
        ).fetchall()
        return len(row)


def clear_embed_dirty(page_id: int) -> None:
    """Unmark a page that failed to index so it cannot block the queue; editing re-dirties it."""
    with connect() as conn:
        conn.execute("UPDATE pages SET embed_dirty = 0 WHERE id = %s", (page_id,))


def workspace_chunk_vectors(workspace_id: int, model: str, chunker: str) -> list[ChunkVector]:
    """A workspace's chunks and vectors, for the in-memory KNN.

    Filtered by `model` and `chunker`: during a reindex two pipelines' vectors coexist,
    and their cosine means nothing.
    """
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT c.page_id, c.ord, c.text, c.path, c.vector, p.slug, p.title,
                   m.type AS page_type,
                   COALESCE(
                       (SELECT array_agg(t.tag ORDER BY t.id) FROM page_tags t
                        WHERE t.page_id = p.id),
                       ARRAY[]::text[]
                   ) AS tags
            FROM page_chunks c
            JOIN pages p ON p.id = c.page_id
            LEFT JOIN page_meta m ON m.page_id = p.id
            WHERE c.workspace_id = %s AND c.model = %s AND c.chunker = %s
              AND p.deleted_at IS NULL
            """,
            (workspace_id, model, chunker),
        ).fetchall()
        return [
            ChunkVector(
                page_id=r["page_id"],
                ord=r["ord"],
                text=r["text"],
                path=r["path"],
                vector=bytes(r["vector"]),
                page_type=r["page_type"],
                tags=list(r["tags"] or []),
                slug=r["slug"],
                title=r["title"],
            )
            for r in rows
        ]


def store_upload_text(name: str, user_id: int, workspace_id: int, text: str) -> None:
    """Store an upload's OCR text, keyed by (name, workspace_id).

    The name is the file's hash, so the same image can live in several workspaces
    without one seeing the other's text.
    """
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO upload_texts (name, workspace_id, user_id, text, created_at)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (name, workspace_id)
            DO UPDATE SET text = EXCLUDED.text, user_id = EXCLUDED.user_id
            """,
            (name, workspace_id, user_id, text, _now()),
        )


def search_uploads(workspace_id: int, query: str, limit: int = 5) -> list[UploadHit]:
    """Full-text search over the OCR text of the workspace's uploads."""
    match = _fts_query(query)
    if not match:
        return []
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT name,
                   ts_headline(
                       'doction', translate(text, %s, ''),
                       to_tsquery('doction', %s), %s
                   ) AS snippet
            FROM upload_texts
            WHERE search_vector @@ to_tsquery('doction', %s) AND workspace_id = %s
            ORDER BY ts_rank(search_vector, to_tsquery('doction', %s)) DESC
            LIMIT %s
            """,
            (
                _MARK_OPEN + _MARK_CLOSE,
                match,
                _HEADLINE_OPTS,
                match,
                workspace_id,
                match,
                limit,
            ),
        ).fetchall()
        hits = []
        for r in rows:
            text, parts = _split_snippet(r["snippet"])
            hits.append(UploadHit(name=r["name"], snippet=text, parts=parts))
        return hits


def get_workspace_by_id(workspace_id: int) -> Workspace | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT id, slug, name FROM workspaces WHERE id = %s",
            (workspace_id,),
        ).fetchone()
        return _to_workspace(row) if row else None


def set_page_git_commit(workspace_id: int, slug: str, sha: str) -> None:
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
        assert row is not None
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
    """Return the owning user_id and touch last_used_at; None if the token is unknown.

    last_used_at is written at most hourly: the UI shows only the day, and an agent
    chaining MCP calls would otherwise write on every request.
    """
    with connect() as conn:
        row = conn.execute(
            "SELECT id, user_id, last_used_at FROM api_tokens WHERE token_hash = %s",
            (token_hash,),
        ).fetchone()
        if row is None:
            return None
        # Fixed-format ISO-8601 UTC, so comparing as text is correct.
        hour_ago = (datetime.now(UTC) - timedelta(hours=1)).isoformat(timespec="seconds")
        if row["last_used_at"] is None or row["last_used_at"] < hour_ago:
            conn.execute(
                "UPDATE api_tokens SET last_used_at = %s WHERE id = %s",
                (_now(), row["id"]),
            )
        return int(row["user_id"])
