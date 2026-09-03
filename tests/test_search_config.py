"""Tests de la configuración de búsqueda `doction` y de su convergencia.

Cubren el defecto que originó el cambio: una consulta en español sin tildes no
encontraba la página acentuada, en los dos caminos de recuperación a la vez.
"""

import psycopg
import pytest

from app import db, meta


def _register(client, email="user@example.com", password="password123"):
    return client.post("/api/auth/register", json={"email": email, "password": password})


def _token(client) -> str:
    _register(client)
    r = client.post("/api/token", json={"email": "user@example.com", "password": "password123"})
    return r.json()["token"]


def _page(client, token: str, title: str, content: str) -> str:
    r = client.post(
        "/api/pages",
        json={"title": title, "content": content},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201, r.text
    return r.json()["slug"]


def _search(client, token: str, query: str) -> list[str]:
    r = client.get(f"/api/search?q={query}", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    return [hit["slug"] for hit in r.json()]


# ── Plegado de acentos ───────────────────────────────────────────────────────


def test_unaccented_query_finds_accented_content(client):
    token = _token(client)
    slug = _page(client, token, "Renovación TLS con Certbot", "Renovar el certificado.")
    _page(client, token, "Otra cosa", "Contenido sin relación.")
    assert _search(client, token, "renovacion")[:1] == [slug]


def test_accented_query_finds_unaccented_content(client):
    token = _token(client)
    slug = _page(client, token, "Contenedor caido o en error", "Diagnostico rapido.")
    _page(client, token, "Otra cosa", "Contenido sin relación.")
    assert _search(client, token, "caído")[:1] == [slug]


def test_english_terms_still_match(client):
    """La clase de control: el vocabulario técnico inglés no se toca."""
    token = _token(client)
    slug = _page(client, token, "Renovación TLS con Certbot", "Usa certbot renew y recarga.")
    _page(client, token, "Almacenamiento", "Montajes y particiones.")
    assert _search(client, token, "certbot")[:1] == [slug]


def test_accent_folding_does_not_merge_unrelated_words(client):
    token = _token(client)
    _page(client, token, "Gestión de Secretos", "Archivos de secretos del host.")
    fstab = _page(client, token, "Errores fstab", "Montajes del SSD y del USB.")
    assert _search(client, token, "fstab") == [fstab]


# ── Convergencia del esquema ─────────────────────────────────────────────────

_LEGACY_PAGES_EXPR = (
    "setweight(to_tsvector('english', coalesce(title, '')), 'A') || "
    "setweight(to_tsvector('english', coalesce(content, '')), 'B')"
)


def _search_vector_expr(conn, table: str) -> str:
    row = conn.execute(
        """
        SELECT pg_get_expr(d.adbin, d.adrelid) AS expr
        FROM pg_attrdef d
        JOIN pg_attribute a ON a.attrelid = d.adrelid AND a.attnum = d.adnum
        WHERE d.adrelid = %s::regclass AND a.attname = 'search_vector'
        """,
        (table,),
    ).fetchone()
    return (row["expr"] if row else "") or ""


def _attnum(conn, table: str) -> int:
    row = conn.execute(
        "SELECT attnum FROM pg_attribute "
        "WHERE attrelid = %s::regclass AND attname = 'search_vector'",
        (table,),
    ).fetchone()
    assert row is not None
    return int(row["attnum"])


def _downgrade_to_legacy(conn) -> None:
    conn.execute("ALTER TABLE pages DROP COLUMN search_vector")
    conn.execute(
        "ALTER TABLE pages ADD COLUMN search_vector tsvector "
        f"GENERATED ALWAYS AS ({_LEGACY_PAGES_EXPR}) STORED"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS pages_search_idx ON pages USING GIN(search_vector)")


def test_populated_legacy_database_converges(client):
    """Una base con el esquema viejo se actualiza al arrancar, sin perder páginas."""
    token = _token(client)
    slug = _page(client, token, "Renovación TLS con Certbot", "Renovar el certificado.")

    with db.connect() as conn:
        _downgrade_to_legacy(conn)
    assert _search(client, token, "renovacion") == []  # el defecto, reproducido

    db.init_db()

    with db.connect() as conn:
        assert "'doction'" in _search_vector_expr(conn, "pages")
    assert _search(client, token, "renovacion")[:1] == [slug]


def test_convergence_is_idempotent(client):
    """El segundo arranque no reconstruye: la columna conserva su attnum."""
    with db.connect() as conn:
        before = _attnum(conn, "pages")
    db.init_db()
    with db.connect() as conn:
        assert _attnum(conn, "pages") == before


def test_convergence_runs_in_both_directions(client, monkeypatch):
    """Volver a una imagen anterior también converge: el mecanismo no tiene sentido único."""
    monkeypatch.setitem(
        db._SEARCH_VECTOR_COLUMNS, "pages", (_LEGACY_PAGES_EXPR, "pages_search_idx")
    )
    monkeypatch.setattr(db, "TS_CONFIG", "english")
    with db.connect() as conn:
        db._converge_search_vectors(conn, force=False)
        assert "'english'" in _search_vector_expr(conn, "pages")


def test_fresh_database_needs_no_rebuild(client):
    with db.connect() as conn:
        assert "'doction'" in _search_vector_expr(conn, "pages")
        before = _attnum(conn, "pages")
        db._converge_search_vectors(conn, force=False)
        assert _attnum(conn, "pages") == before


# ── Degradación sin la extensión ─────────────────────────────────────────────


class _NoExtensionConn:
    """Conexión que rechaza CREATE EXTENSION, como un rol sin permiso para crearla."""

    def __init__(self, conn):
        self._conn = conn

    def execute(self, query, params=None):
        if "CREATE EXTENSION" in str(query):
            raise psycopg.errors.InsufficientPrivilege("permission denied to create extension")
        if params is None:
            return self._conn.execute(query)
        return self._conn.execute(query, params)

    def rollback(self):
        self._conn.rollback()


def test_missing_unaccent_extension_does_not_break_startup(client):
    """Sin permiso para crear la extensión el servidor arranca igual, sin plegado."""
    with db.connect() as conn:
        changed = db._ensure_text_search_config(_NoExtensionConn(conn))
        assert changed is True
        row = conn.execute(
            """
            SELECT string_agg(d.dictname, ', ' ORDER BY m.mapseqno) AS dicts
            FROM pg_ts_config c
            JOIN pg_ts_config_map m ON m.mapcfg = c.oid
            JOIN pg_ts_dict d ON d.oid = m.mapdict
            JOIN ts_token_type(c.cfgparser) t ON t.tokid = m.maptokentype
            WHERE c.cfgname = 'doction' AND t.alias = 'word'
            """
        ).fetchone()
        assert row is not None and row["dicts"] == "english_stem"


@pytest.mark.parametrize("query", ["renovacion", "renovación"])
def test_both_spellings_return_the_same_page(client, query):
    token = _token(client)
    slug = _page(client, token, "Renovación TLS con Certbot", "Renovar el certificado.")
    assert _search(client, token, query)[:1] == [slug]


# ── Seguridad al cambiar de encoder ──────────────────────────────────────────


def test_chunks_from_another_model_are_not_scored(client, monkeypatch):
    """Media reindexación no debe mezclar dos espacios de embeddings en un coseno."""
    monkeypatch.setenv("SEMANTIC_SEARCH", "1")
    monkeypatch.setenv("EMBED_STUB", "1")
    from app import embeddings

    embeddings.reset_embedder()
    token = _token(client)
    slug = _page(client, token, "Certbot", "Renovar el certificado TLS.")
    embeddings.drain_pending()

    current = embeddings.current_model_name()
    assert db.workspace_chunk_vectors(1, current, meta.CHUNKER_ID)

    with db.connect() as conn:
        conn.execute("UPDATE page_chunks SET model = 'otro-modelo'")
    assert db.workspace_chunk_vectors(1, current, meta.CHUNKER_ID) == []
    assert slug  # la página sigue existiendo; solo sus vectores quedan fuera


def test_stale_chunker_pages_are_requeued(client, monkeypatch):
    """Partir la página de otra forma invalida los vectores igual que cambiar de encoder.

    Antes la obsolescencia solo miraba el modelo, así que un cambio de troceador
    dejaba fragmentos viejos sirviéndose para siempre.
    """
    monkeypatch.setenv("SEMANTIC_SEARCH", "1")
    monkeypatch.setenv("EMBED_STUB", "1")
    from app import embeddings

    embeddings.reset_embedder()
    token = _token(client)
    _page(client, token, "Certbot", "Renovar el certificado TLS.")
    embeddings.drain_pending()
    assert db.pages_to_embed(10) == []

    with db.connect() as conn:
        conn.execute("UPDATE page_chunks SET chunker = 'troceador-viejo'")

    model = embeddings.current_model_name()
    assert db.mark_stale_model_dirty(model, meta.CHUNKER_ID) >= 1
    assert db.pages_to_embed(10), "la página debería volver a la cola"
    # Y sus vectores no se puntúan mientras tanto.
    assert db.workspace_chunk_vectors(1, model, meta.CHUNKER_ID) == []


def test_stale_model_pages_are_requeued(client, monkeypatch):
    monkeypatch.setenv("SEMANTIC_SEARCH", "1")
    monkeypatch.setenv("EMBED_STUB", "1")
    from app import embeddings

    embeddings.reset_embedder()
    token = _token(client)
    _page(client, token, "Certbot", "Renovar el certificado TLS.")
    embeddings.drain_pending()
    assert db.pages_to_embed(10) == []

    with db.connect() as conn:
        conn.execute("UPDATE page_chunks SET model = 'modelo-viejo'")

    with db.connect() as conn:
        row = conn.execute("SELECT count(DISTINCT page_id) AS n FROM page_chunks").fetchone()
    assert row is not None and row["n"] >= 1
    embedded = int(row["n"])

    assert db.mark_stale_model_dirty(embeddings.current_model_name(), meta.CHUNKER_ID) == embedded
    assert len(db.pages_to_embed(20)) == embedded
    assert embeddings.drain_pending() == embedded
    assert db.workspace_chunk_vectors(1, embeddings.current_model_name(), meta.CHUNKER_ID)


def test_current_model_name_does_not_load_the_model(monkeypatch):
    """Se consulta también con la semántica apagada: no puede abrir la sesión ONNX."""
    from app import embeddings

    embeddings.reset_embedder()
    monkeypatch.delenv("EMBED_STUB", raising=False)
    monkeypatch.setattr(
        embeddings, "_OnnxEmbedder", _exploding_encoder(embeddings._OnnxEmbedder.name)
    )
    assert embeddings.current_model_name() == "all-MiniLM-L6-v2-int8"


def _exploding_encoder(name: str):
    class Exploding:
        pass

    Exploding.name = name  # type: ignore[attr-defined]
    Exploding.__init__ = lambda self: pytest.fail("no debe construirse el encoder")  # type: ignore[method-assign]
    return Exploding
