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


def _get_pool() -> ConnectionPool[Connection[DictRow]]:
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                _pool = ConnectionPool(
                    database_url(),
                    min_size=1,
                    max_size=10,
                    # `connection_class` duplica el row_factory de kwargs, pero es lo
                    # que hace que las filas se tipen como dict y no como tupla: sin
                    # él, cada row["campo"] de este módulo es un error de tipos.
                    connection_class=Connection[DictRow],
                    kwargs={"row_factory": dict_row},
                    open=True,
                    # Valida la conexión al sacarla del pool: si Postgres se
                    # reinició (reboot de la Pi), se reconecta solo en vez de
                    # fallar hasta que las conexiones muertas se reciclen.
                    check=ConnectionPool[Connection[DictRow]].check_connection,
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


# ── Esquema ───────────────────────────────────────────────────────────────────
# Esquema final directo (sin el historial de migraciones de la era SQLite: no hay
# datos legacy que reconciliar porque una base Postgres nueva nace ya con esta forma
# — ver scripts/migrate_sqlite_to_postgres.py para la migración única de datos
# existentes). `search_vector` es una columna generada: Postgres la mantiene
# sincronizada solo, sin triggers (a diferencia de los 3 triggers que requería FTS5).
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
    # Bases anteriores a token_version (idempotente).
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
    # El destino real de un wikilink es la página; dst_slug se conserva porque es
    # la única representación que tiene un enlace roto, y los enlaces rotos son
    # información (los reporta graph.link_insights).
    "ALTER TABLE page_links ADD COLUMN IF NOT EXISTS dst_page_id BIGINT "
    "REFERENCES pages(id) ON DELETE SET NULL",
    "CREATE INDEX IF NOT EXISTS page_links_dst_page_idx ON page_links(dst_page_id)",
    # Backfill idempotente: resuelve los enlaces que ya existían.
    """
    UPDATE page_links l SET dst_page_id = p.id
    FROM pages p
    WHERE l.dst_page_id IS NULL
      AND p.workspace_id = l.workspace_id
      AND p.slug = l.dst_slug
      AND p.deleted_at IS NULL
    """,
    # Un slug anterior sigue resolviendo para siempre: renombrar no rompe los
    # [[wikilinks]] escritos en el markdown de otras páginas, y evita tener que
    # reescribir contenido que el usuario no editó.
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
    # Webhooks de salida. La entrega va en cola en tabla, no en memoria: si el
    # receptor está caído o doction reinicia, los eventos no se pierden.
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
    # El worker busca pendientes por (delivered_at IS NULL, next_attempt_at).
    "CREATE INDEX IF NOT EXISTS webhook_deliveries_due_idx "
    "ON webhook_deliveries(next_attempt_at) WHERE delivered_at IS NULL",
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
    # `path` es la cadena de encabezados dentro del documento; `chunker` identifica
    # el algoritmo que produjo el fragmento. Van con ADD COLUMN IF NOT EXISTS porque
    # page_chunks ya existe en cualquier despliegue vivo, y el CREATE de arriba no
    # toca una tabla creada.
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
        conn.cursor().executemany("INSERT INTO page_tags (page_id, tag) VALUES (%s, %s)", tags)

    conn.execute("DELETE FROM page_links WHERE src_page_id = %s", (page_id,))
    seen: set[str] = set()
    edges: list[tuple[int, str, int, int, str, int, str]] = []
    for target in meta.extract_links(content):
        dst = slugify(target)
        if dst not in seen:
            seen.add(dst)
            # Los valores se repiten porque la subconsulta busca el destino
            # primero entre las páginas y luego entre los alias.
            edges.append((page_id, dst, workspace_id, workspace_id, dst, workspace_id, dst))
    if edges:
        # dst_page_id se resuelve aquí; queda NULL si el destino aún no existe,
        # y create_page lo rellena cuando esa página se crea.
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

    # El contenido cambió: marcar para reembedding (lo procesa el worker async).
    conn.execute("UPDATE pages SET embed_dirty = 1 WHERE id = %s", (page_id,))


# Configuración de búsqueda propia: pliega acentos antes de aplicar el stemmer.
# `unaccent()` suelto no vale en una columna generada —es STABLE, no IMMUTABLE, y
# Postgres la rechaza—; encadenado dentro de una configuración sí, porque
# to_tsvector(regconfig, text) sí es IMMUTABLE.
#
# El stemmer es el inglés, medido: con `spanish_stem` las consultas en inglés
# contra páginas en español caen a 0.00 de MRR (evals/results/2026-08-24-minilm-en.json).
# El acento es el problema real; el stemmer inglés no lo era.
TS_CONFIG = "doction"
_TS_STEMMER = "english_stem"
_TS_WORD_TOKENS = "asciiword, asciihword, hword_asciipart, word, hword, hword_part"


def _ensure_text_search_config(conn) -> bool:
    """Crea/actualiza la configuración `doction`. True si su mapeo cambió.

    Sin la extensión `unaccent` (rol sin permiso para crearla) la configuración se
    queda en el stemmer solo: la búsqueda pierde el plegado de acentos pero el
    servidor arranca igual.
    """
    unaccent = True
    try:
        conn.execute("CREATE EXTENSION IF NOT EXISTS unaccent")
    except Exception:
        conn.rollback()
        unaccent = False
        logger.warning(
            "no se pudo crear la extensión unaccent; %s se queda sin plegado de "
            "acentos (las consultas en español sin tildes fallarán)",
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
    logger.info("configuración de búsqueda %s → %s", TS_CONFIG, dictionaries)
    return True


# Las columnas generadas no se recalculan solas cuando cambia su definición ni
# cuando cambia el mapeo de la configuración: Postgres las calcula al escribir.
# `init_db` es CREATE TABLE IF NOT EXISTS a propósito (sin escalera de
# migraciones), así que una base ya existente nunca vería el cambio. Esto no
# añade una escalera: comprueba el estado real contra el que declara el código y
# converge. Al ser convergente, volver a una imagen anterior también funciona.
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
    """Reconstruye las columnas `search_vector` que no estén en la configuración."""
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
        # DROP COLUMN se lleva por delante el índice GIN, así que se recrea.
        conn.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS search_vector")
        conn.execute(
            f"ALTER TABLE {table} ADD COLUMN search_vector tsvector "
            f"GENERATED ALWAYS AS ({expression}) STORED"
        )
        conn.execute(f"CREATE INDEX IF NOT EXISTS {index} ON {table} USING GIN(search_vector)")
        logger.info("search_vector de %s reconstruido sobre %s", table, TS_CONFIG)


def init_db() -> None:
    """Crea el esquema (idempotente) y corre los backfills defensivos."""
    with connect() as conn:
        mapping_changed = _ensure_text_search_config(conn)
        for stmt in SCHEMA_STATEMENTS:
            conn.execute(stmt)
        _converge_search_vectors(conn, force=mapping_changed)
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
        # Un alias ocupa el nombre igual que una página viva: si no, renombrar
        # podría robarle el slug a un enlace antiguo que aún resuelve.
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


def update_user_password(user_id: int, password_hash: str) -> int:
    """Cambia la contraseña y sube token_version → invalida todas las sesiones JWT
    emitidas antes del cambio. Devuelve la nueva versión (para reemitir la sesión actual)."""
    with connect() as conn:
        row = conn.execute(
            "UPDATE users SET password_hash = %s, token_version = token_version + 1 "
            "WHERE id = %s RETURNING token_version",
            (password_hash, user_id),
        ).fetchone()
        return int(row["token_version"]) if row else 0


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
    """Borra el workspace y sus páginas. No borra el último que quede."""
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
    """Lista plana en orden DFS con campo depth para renderizar el árbol en la sidebar."""
    with connect() as conn:
        rows = conn.execute(
            # Las capturas SIN ARCHIVAR (type: memo, sin padre) viven en el feed
            # paginado, no en el árbol: esta consulta no pagina y la sidebar las
            # pinta todas. En cuanto una se mueve bajo un padre deja de ser
            # bandeja y pasa a ser una página más del árbol; el triaje es
            # move_page y no reescribe el frontmatter de nadie.
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
        if row is None:
            # Slug anterior: un renombrado deja alias para que los [[wikilinks]]
            # ya escritos sigan resolviendo sin tocar el markdown de nadie.
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
    title = title.strip() or meta.derive_title(content)
    # Sin requested_slug ni título propio, el slug sale de una marca temporal: si
    # se derivara del título, cien capturas sin título darían untitled-2 … -101.
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
        # Referencias hacia adelante: enlaces escritos antes de que existiera el
        # destino. Sin esto quedarían rotos para siempre aunque el destino llegue.
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
    """Actualiza una página manteniendo el slug estable; devuelve slug o None si no existe."""
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
    """Escribe una sola sección de una página. Devuelve el slug, o None si no existe.

    Pasa por `update_page`, no por un UPDATE propio: así la versión queda en el
    historial de git, la página se re-encola para indexar y el evento sale por los
    webhooks exactamente igual que en cualquier otra escritura. Una escritura que se
    saltara ese camino sería una página que cambia sin que nadie se entere.

    Lee y escribe dentro de la misma llamada, de modo que dos agentes tocando
    secciones distintas de una página no se pisan: cada uno reescribe solo su bloque
    sobre el contenido más reciente, en vez de mandar el cuerpo entero que leyó hace
    un minuto.

    `AmbiguousSection` sube tal cual: elegir por el llamante cuál de dos encabezados
    idénticos quería es peor que decirle que desambigüe.
    """
    page = get_page(slug, workspace_id)
    if page is None:
        return None
    content = meta.upsert_section(page.content, heading, body, level=level, parent=parent)
    if content == page.content:
        return slug
    return update_page(user_id, workspace_id, slug, page.title, content)


# ── Webhooks de salida ───────────────────────────────────────────────────────
# emit_event() se llama DENTRO de la transacción que ya hizo la escritura, así el
# evento se encola en el mismo commit que el cambio: no hay ventana en la que la
# página exista y su aviso se haya perdido. La entrega la hace el worker aparte;
# aquí no se abre ni una conexión HTTP.

MAX_DELIVERY_ATTEMPTS = 6


def emit_event(conn, workspace_id: int, event: str, payload: dict) -> None:
    """Encola `event` para los webhooks activos del workspace que lo escuchen."""
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
        # events vacío = todos; si no, lista separada por comas.
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
    """Entregas pendientes cuyo momento de reintento ya pasó."""
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
    """`delivered_at` marca "ya no se reintenta", no "salió bien".

    El worker lo pone también al agotar los reintentos, y ahí deja `last_error`.
    Sin mirar las dos columnas, una entrega abandonada se leería como entregada.
    """
    if delivered_at is None:
        return "pending"
    return "failed" if last_error else "delivered"


def list_deliveries(webhook_id: int, limit: int = 20) -> list[Delivery]:
    """Las entregas recientes de un webhook, la más nueva primero.

    No devuelve `payload_json`: el cuerpo del evento lleva el contenido de la
    página, y esto es una vista de operación — qué salió y qué no.
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
    """Pendientes y fallidas por webhook del workspace, para marcar la lista.

    Una sola consulta agregada y no una por webhook: la lista de ajustes los pinta
    todos, y N+1 consultas para pintar dos números no se sostienen.
    """
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
    """Reprograma con backoff exponencial; al agotar intentos la deja marcada."""
    now = datetime.now(UTC)
    # 1min, 2, 4, 8, 16… La entrega deja de reintentarse al llegar al máximo.
    espera = timedelta(minutes=2 ** min(attempts, 5))
    siguiente = (now + espera).isoformat(timespec="seconds")
    agotada = attempts + 1 >= MAX_DELIVERY_ATTEMPTS
    with connect() as conn:
        conn.execute(
            "UPDATE webhook_deliveries SET attempts = attempts + 1, last_error = %s, "
            "next_attempt_at = %s, delivered_at = %s WHERE id = %s",
            (
                error[:500],
                siguiente,
                now.isoformat(timespec="seconds") if agotada else None,
                delivery_id,
            ),
        )
        conn.execute(
            "UPDATE webhooks SET last_status = %s, last_attempt_at = %s WHERE id = %s",
            (error[:200], now.isoformat(timespec="seconds"), webhook_id),
        )


def move_page(workspace_id: int, slug: str, parent_slug: str | None) -> str | None:
    """Reparenta una página; devuelve su slug o None si no existe.

    Es la operación más barata del modelo: el repo git es plano
    (`{workspace}/{slug}.md`), así que mover no toca ningún fichero.

    Lanza ValueError si el destino no existe o crearía un ciclo.
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

        # pages.parent_id no tiene restricción contra bucles y el DFS de
        # list_pages_tree se colgaría, así que hay que mirar los ancestros antes.
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
    """Cambia el slug dejando alias del anterior; devuelve el nuevo o None.

    No reescribe el markdown de las páginas que enlazan: hacerlo produciría
    commits de git en páginas que el usuario no editó. El alias mantiene vivos
    los [[wikilinks]] ya escritos.
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
        # dst_page_id es la verdad y no cambia; dst_slug es caché para mostrar.
        conn.execute("UPDATE page_links SET dst_slug = %s WHERE dst_page_id = %s", (final, page_id))
        emit_event(
            conn,
            workspace_id,
            "page.renamed",
            {"page": {"slug": final}, "previous_slug": previous},
        )
        return final


def list_children(workspace_id: int, slug: str) -> list[PageRef] | None:
    """Hijos directos de una página. None si la página no existe."""
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
    """Feed cronológico de capturas sin archivar, paginado por cursor.

    Existe porque list_pages_tree devuelve TODAS las páginas sin paginar: unos
    miles de notas harían inusable la barra lateral.

    La bandeja es `type: memo` Y sin padre: mover una nota bajo cualquier página
    la saca de aquí y la mete en el árbol, que es en lo que consiste el triaje.
    """
    limit = max(1, min(limit, 200))
    sql = """
        SELECT p.slug, p.title, p.created_at, LEFT(p.content, 200) AS excerpt
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
                excerpt=r["excerpt"],
            )
            for r in rows
        ]


def delete_page(workspace_id: int, slug: str) -> bool:
    """Soft-delete: mueve la página a la papelera (deleted_at = now). Recuperable.

    No se borra el archivo del repo git ni los datos derivados: solo se marca para que
    deje de aparecer en listados, búsqueda y enlaces. El contenido sigue en la fila."""
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
    """Páginas en la papelera del workspace, más recientes primero."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT slug, title, deleted_at FROM pages "
            "WHERE workspace_id = %s AND deleted_at IS NOT NULL "
            "ORDER BY deleted_at DESC",
            (workspace_id,),
        ).fetchall()
        return [_to_page(row) for row in rows]


def restore_page(workspace_id: int, slug: str) -> bool:
    """Saca una página de la papelera (deleted_at = NULL)."""
    with connect() as conn:
        cur = conn.execute(
            "UPDATE pages SET deleted_at = NULL WHERE slug = %s AND workspace_id = %s "
            "AND deleted_at IS NOT NULL",
            (slug, workspace_id),
        )
        return cur.rowcount > 0


def purge_page(workspace_id: int, slug: str) -> bool:
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
    """Convierte input de usuario en un tsquery de prefijos seguro (equivalente al MATCH
    de prefijos de FTS5). Los términos ya vienen filtrados a \\w+, así que `term:*` es
    siempre sintaxis válida de tsquery — no hay riesgo de inyección."""
    terms = re.findall(r"[\w]+", raw, flags=re.UNICODE)
    if not terms:
        return ""
    return " & ".join(f"{term}:*" for term in terms)


# ts_headline marca las coincidencias con estos dos caracteres de control, no con
# <mark>: el fragmento sale de aquí como texto y el resaltado como posiciones, así
# que el contenido de la página no puede volver a entrar en el DOM como HTML. Son
# de control porque `translate()` los borra del texto de entrada antes de resaltar
# (ver _HEADLINE_OPTS): un tramo marcado solo puede venir del resaltador.
_MARK_OPEN = "\x01"
_MARK_CLOSE = "\x02"
_HEADLINE_OPTS = (
    f"StartSel={_MARK_OPEN}, StopSel={_MARK_CLOSE}, MaxWords=12, MinWords=1, MaxFragments=1"
)


def _split_snippet(marked: str) -> tuple[str, list[SnippetPart]]:
    """Parte un fragmento de ts_headline en (texto plano, tramos)."""
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
    """Búsqueda léxica del workspace, opcionalmente acotada por etiquetas.

    El filtro va dentro de la consulta y no sobre el resultado: filtrar después del
    LIMIT devolvería menos páginas de las que hay, y una que hoy queda por debajo del
    corte tiene que poder salir cuando el filtro quita a las de encima.
    """
    match = _fts_query(query)
    if not match:
        return []
    # Fragmentos LiteralString por el mismo motivo que en extract_pages: así el
    # f-string sigue siéndolo y el checker prueba que no entra nada del usuario en el
    # SQL — sus valores viajan por %s.
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
                       'doction', translate(p.title || ' ' || p.content, %s, ''),
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
    """Slugs del workspace que llevan alguna de las etiquetas dadas.

    La lista vectorial se filtra en memoria (ya trae el workspace entero), así que
    necesita el conjunto permitido; la léxica lo filtra en su propio SQL.
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
    workspace_id: int,
    *,
    page_type: str | None = None,
    tag: str | None = None,
    limit: int = 200,
) -> list[ExtractedPage]:
    """Filtra páginas por `type` y/o `tag` del frontmatter; estructura sin LLM."""
    # Los fragmentos van tipados como LiteralString a propósito: así el f-string de
    # abajo sigue siéndolo y el checker prueba que no hay nada del usuario en el SQL
    # (sus valores viajan por %s).
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
    """Páginas que enlazan a `slug` vía wikilink [[slug]]."""
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


def related_pages(workspace_id: int, slug: str, limit: int = 10) -> list[RelatedPage] | None:
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


def workspace_pages(workspace_id: int) -> list[Page]:
    """Páginas vivas (id, slug, title, content) para las funciones ML locales
    (TF-IDF, sugerencias, insights). El acceso ya lo garantizó la membresía al
    resolver el workspace."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, slug, title, content FROM pages "
            "WHERE workspace_id = %s AND deleted_at IS NULL ORDER BY id",
            (workspace_id,),
        ).fetchall()
        return [_to_page(row) for row in rows]


def page_outgoing_links(page_id: int) -> list[str]:
    """Slugs destino de los wikilinks salientes de una página."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT dst_slug FROM page_links WHERE src_page_id = %s", (page_id,)
        ).fetchall()
        return [r["dst_slug"] for r in rows]


def workspace_links(workspace_id: int) -> list[LinkEdge]:
    """Todas las aristas de wikilinks del workspace (origen vivo; el destino puede
    no existir — enlace roto, lo resuelve app.graph)."""
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
    """Vocabulario de tags vivos del workspace (para alinear sugerencias TF-IDF)."""
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
    """Páginas marcadas como sucias (embed_dirty=1) pendientes de embedding."""
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
    """(páginas vivas, páginas con chunks del pipeline actual) del workspace.

    Cuenta, no trae contenido: `pages_to_embed` devuelve el markdown entero y sirve
    para alimentar al worker, no para informar de cuánto queda por indexar.
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
    """Reemplaza los chunks/vectores de una página y limpia embed_dirty (atómico).

    Cada fragmento entra como `(ord, texto, ruta, vector)`.
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
    """Re-encola las páginas cuyos chunks no vienen del pipeline actual.

    Dos vectores solo son comparables si los produjo el mismo encoder *y* el mismo
    troceador: partir una página de otra forma cambia lo que se embebe tanto como
    cambiar el modelo. Antes esto solo miraba el encoder, así que un cambio de
    troceador dejaba fragmentos viejos sirviéndose para siempre.
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
    """Desmarca una página que no se pudo indexar, para que no bloquee la cola del
    worker. La página vuelve a marcarse sucia en su próxima edición."""
    with connect() as conn:
        conn.execute("UPDATE pages SET embed_dirty = 0 WHERE id = %s", (page_id,))


def workspace_chunk_vectors(workspace_id: int, model: str, chunker: str) -> list[ChunkVector]:
    """Chunks + vectores de un workspace para la búsqueda semántica (KNN en memoria).

    Filtra por `model` y por `chunker`: durante un reindexado conviven vectores de
    dos pipelines distintos, y su coseno no significa nada.
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
    """Guarda/actualiza el texto OCR de un upload. La clave es (name, workspace_id):
    el nombre viene del hash del archivo, así que la misma imagen puede vivir en
    varios workspaces sin que uno vea el texto del otro."""
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
    """Búsqueda FTS sobre el texto OCR de los uploads del workspace."""
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
    """Devuelve el user_id propietario y actualiza last_used_at; None si no existe.

    last_used_at se escribe como mucho una vez por hora: en la UI se muestra solo
    el día, y un agente MCP encadenando llamadas escribía en cada request.
    """
    with connect() as conn:
        row = conn.execute(
            "SELECT id, user_id, last_used_at FROM api_tokens WHERE token_hash = %s",
            (token_hash,),
        ).fetchone()
        if row is None:
            return None
        # Timestamps ISO-8601 UTC con formato fijo: comparar como texto es correcto.
        hour_ago = (datetime.now(UTC) - timedelta(hours=1)).isoformat(timespec="seconds")
        if row["last_used_at"] is None or row["last_used_at"] < hour_ago:
            conn.execute(
                "UPDATE api_tokens SET last_used_at = %s WHERE id = %s",
                (_now(), row["id"]),
            )
        return int(row["user_id"])
