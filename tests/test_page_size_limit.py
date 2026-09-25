"""Tests for the bound on page content.

Not the ReDoS fix — that is the linear wikilink pattern. This caps what one request can cost
when a parser turns out worse than believed. Enforced in `db` rather than on the Pydantic
models, because MCP calls `create_page` and `update_page` directly and would bypass them.
"""

from app import db


def _register(client, email="size@example.com", password="password123"):
    return client.post("/api/auth/register", json={"email": email, "password": password})


def _page_of(size: int) -> str:
    return "a" * size


def test_an_ordinary_page_is_accepted(client):
    """A limit that rejects real documents is a defect of its own."""
    _register(client)
    # Longer than any seeded page and than this repo's README (~18 KB).
    r = client.post("/api/pages", json={"title": "Larga", "content": _page_of(64 * 1024)})
    assert r.status_code == 201, r.text


def test_content_over_the_limit_is_rejected_naming_the_limit(client):
    _register(client, email="over@example.com")
    r = client.post(
        "/api/pages",
        json={"title": "Enorme", "content": _page_of(db.MAX_CONTENT_BYTES + 1)},
    )
    assert r.status_code == 400, r.text
    # The requirement is that the response names the limit, not that it fails opaquely.
    assert str(db.MAX_CONTENT_BYTES) in r.text.replace(",", "")


def test_updating_a_page_is_bounded_too(client):
    _register(client, email="upd@example.com")
    slug = client.post("/api/pages", json={"title": "P", "content": "corta"}).json()["slug"]

    r = client.put(f"/api/pages/{slug}", json={"content": _page_of(db.MAX_CONTENT_BYTES + 1)})
    assert r.status_code == 400, r.text
    assert str(db.MAX_CONTENT_BYTES) in r.text.replace(",", "")


def test_the_limit_counts_bytes_not_characters(client):
    """The ceiling is memory, not typography: a multibyte character costs more than one byte."""
    _register(client, email="utf8@example.com")
    # "ñ" is 2 bytes in UTF-8, so this exceeds MAX with half as many characters.
    content = "ñ" * (db.MAX_CONTENT_BYTES // 2 + 1)
    assert len(content) < db.MAX_CONTENT_BYTES < len(content.encode("utf-8"))

    r = client.post("/api/pages", json={"title": "UTF-8", "content": content})
    assert r.status_code == 400, r.text


def test_the_limit_also_covers_the_agent_surface():
    """MCP calls db directly: the guard must sit where both paths meet."""
    try:
        db.create_page(1, 1, "T", _page_of(db.MAX_CONTENT_BYTES + 1))
    except ValueError as exc:
        assert str(db.MAX_CONTENT_BYTES) in str(exc).replace(",", "")
    else:
        raise AssertionError("db.create_page aceptó contenido por encima del límite")
