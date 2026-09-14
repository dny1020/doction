"""Tests for the bound on page content.

The limit is not the ReDoS fix — that lives in the wikilink pattern, which is linear now. It
caps what a single request can cost when a parser later turns out to be worse than believed,
which is exactly what happened once.

It is enforced in `db`, not on the Pydantic models, because MCP calls `create_page` and
`update_page` directly and would bypass them. The agent-facing surface is where a huge page is
easiest to produce, so a limit that missed it would miss the likeliest case.
"""

from app import db


def _register(client, email="size@example.com", password="password123"):
    return client.post("/api/auth/register", json={"email": email, "password": password})


def _page_of(size: int) -> str:
    return "a" * size


def test_an_ordinary_page_is_accepted(client):
    """Un límite que rechaza documentos reales es un defecto propio."""
    _register(client)
    # Más largo que cualquier página sembrada (542 B) y que el README de este repo (~18 KB).
    r = client.post("/api/pages", json={"title": "Larga", "content": _page_of(64 * 1024)})
    assert r.status_code == 201, r.text


def test_content_over_the_limit_is_rejected_naming_the_limit(client):
    _register(client, email="over@example.com")
    r = client.post(
        "/api/pages",
        json={"title": "Enorme", "content": _page_of(db.MAX_CONTENT_BYTES + 1)},
    )
    assert r.status_code == 400, r.text
    # El requisito dice que la respuesta nombre el límite, no que falle de forma opaca.
    assert str(db.MAX_CONTENT_BYTES) in r.text.replace(",", "")


def test_updating_a_page_is_bounded_too(client):
    _register(client, email="upd@example.com")
    slug = client.post("/api/pages", json={"title": "P", "content": "corta"}).json()["slug"]

    r = client.put(f"/api/pages/{slug}", json={"content": _page_of(db.MAX_CONTENT_BYTES + 1)})
    assert r.status_code == 400, r.text
    assert str(db.MAX_CONTENT_BYTES) in r.text.replace(",", "")


def test_the_limit_counts_bytes_not_characters(client):
    """Un carácter multibyte ocupa más de un byte; el techo es de memoria, no de tipografía."""
    _register(client, email="utf8@example.com")
    # "ñ" son 2 bytes en UTF-8: esto pasa de MAX aunque tenga la mitad de caracteres.
    content = "ñ" * (db.MAX_CONTENT_BYTES // 2 + 1)
    assert len(content) < db.MAX_CONTENT_BYTES < len(content.encode("utf-8"))

    r = client.post("/api/pages", json={"title": "UTF-8", "content": content})
    assert r.status_code == 400, r.text


def test_the_limit_also_covers_the_agent_surface():
    """MCP llama a db directamente: el guard tiene que estar donde ambos caminos convergen."""
    try:
        db.create_page(1, 1, "T", _page_of(db.MAX_CONTENT_BYTES + 1))
    except ValueError as exc:
        assert str(db.MAX_CONTENT_BYTES) in str(exc).replace(",", "")
    else:
        raise AssertionError("db.create_page aceptó contenido por encima del límite")
