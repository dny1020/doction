"""Holds the user documentation to what the code actually does.

Every assertion mirrors a claim in `docs/search.md` or `docs/tags-and-metadata.md`, including
the surprising ones — a query has no syntax, the metadata block is not YAML. When one fails,
the change that broke it made the documentation untrue, and the message says which page to fix.

These read only the code, so they run in the stripped Docker `test` stage like any other test.
"""

from app import meta

SEARCH_DOC = "docs/search.md"
TAGS_DOC = "docs/tags-and-metadata.md"


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
    r = client.get("/api/search", params={"q": query}, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    return [hit["slug"] for hit in r.json()]


def _two_pages(client, token: str) -> tuple[str, str]:
    kamailio = _page(client, token, "Kamailio dispatcher", "Kamailio balances calls.")
    asterisk = _page(client, token, "Asterisk queues", "Asterisk holds waiting callers.")
    return kamailio, asterisk


# ── There is no query syntax (docs/search.md) ────────────────────────────────


def test_or_is_not_a_disjunction(client):
    """`OR` is dropped as a stopword and the terms are both required."""
    token = _token(client)
    kamailio, asterisk = _two_pages(client, token)
    assert _search(client, token, "kamailio") == [kamailio]
    assert _search(client, token, "asterisk") == [asterisk]
    assert _search(client, token, "kamailio OR asterisk") == [], (
        f"OR now behaves like a disjunction; {SEARCH_DOC} says it returns nothing"
    )


def test_a_leading_minus_requires_instead_of_excluding(client):
    """The `-` is discarded, so the term a user tried to exclude becomes required."""
    token = _token(client)
    kamailio, _ = _two_pages(client, token)
    assert _search(client, token, "kamailio") == [kamailio]
    assert _search(client, token, "-asterisk kamailio") == [], (
        f"negation now does something; {SEARCH_DOC} says the term becomes required"
    )


def test_a_stopword_only_query_returns_nothing(client):
    token = _token(client)
    _two_pages(client, token)
    assert _search(client, token, "the") == [], (
        f"a stopword-only query now matches; {SEARCH_DOC} says it compiles to an empty query"
    )


def test_terms_are_prefix_matches(client):
    token = _token(client)
    kamailio, _ = _two_pages(client, token)
    assert _search(client, token, "kam") == [kamailio], (
        f"terms are no longer prefix matches; {SEARCH_DOC} says every term is one"
    )


def test_quotes_do_not_make_a_phrase(client):
    """A quoted query matches a page holding the words apart and in the other order."""
    token = _token(client)
    _two_pages(client, token)
    reversed_order = _page(
        client, token, "Reverse order", "queues come first and asterisk comes later."
    )
    hits = _search(client, token, '"asterisk queues"')
    assert reversed_order in hits, (
        f"quoting now constrains order or adjacency; {SEARCH_DOC} says there is no phrase search"
    )


def test_field_syntax_is_not_a_filter(client):
    """`tag:voip` is two ordinary terms, one of them the literal word "tag"."""
    token = _token(client)
    _two_pages(client, token)
    assert _search(client, token, "tag:voip") == [], (
        f"a field filter now exists; {SEARCH_DOC} says `tag:` is not one"
    )


def test_accents_fold_in_both_directions(client):
    token = _token(client)
    slug = _page(client, token, "Renovacion demo", "La Renovación del certificado.")
    assert _search(client, token, "renovacion") == [slug]
    assert _search(client, token, "renovación") == [slug], (
        f"accent folding stopped working; {SEARCH_DOC} documents it in both directions"
    )


# ── The metadata block is not YAML (docs/tags-and-metadata.md) ───────────────

BLOCK_LIST = "---\ntags:\n  - kamailio\n  - sip\n---\n\nbody\n"
INLINE_LIST = "---\ntags: [kamailio, sip]\n---\n\nbody\n"


def test_a_block_list_of_tags_is_silently_ignored():
    assert meta.extract_tags(BLOCK_LIST) == [], (
        f"a block list now yields tags; {TAGS_DOC} says it is silently ignored"
    )


def test_an_inline_list_of_tags_takes_effect():
    assert meta.extract_tags(INLINE_LIST) == ["kamailio", "sip"], (
        f"the inline list stopped working; it is the spelling {TAGS_DOC} tells people to use"
    )


def test_the_unparsed_block_stays_in_the_body():
    """Lines the parser did not understand are left where they are, and stay searchable."""
    parsed, body = meta.parse_frontmatter(BLOCK_LIST)
    assert parsed.get("tags") == ""
    assert "- kamailio" not in body, (
        "the block's own lines are consumed as frontmatter, not left in the body"
    )


def test_a_tag_must_start_with_a_letter():
    assert meta.extract_tags("released in #2026") == [], (
        f"a tag may now start with a digit; {TAGS_DOC} says it must start with a letter"
    )


def test_tags_are_lowercased():
    assert meta.extract_tags("about #Kamailio") == ["kamailio"], (
        f"tags are no longer lowercased; {TAGS_DOC} says they are"
    )


def test_hyphens_are_part_of_a_tag():
    assert meta.extract_tags("about #sip-trunk") == ["sip-trunk"], (
        f"hyphens left tag syntax; {TAGS_DOC} documents #sip-trunk as one tag"
    )


def test_code_is_not_scanned_for_tags():
    inline = meta.extract_tags("a comment `#incode` here")
    fenced = meta.extract_tags("```\n#infence\n```\n")
    assert inline == [] and fenced == [], (
        f"code is now scanned for tags; {TAGS_DOC} says both spans and fences are removed"
    )


# ── Wikilink targets (docs/linking.md) ───────────────────────────────────────


def test_a_title_works_as_a_wikilink_target():
    """The target is slugified before lookup, so a title resolves like a slug."""
    assert meta.extract_links("see [[Markdown Cheatsheet]]") == ["Markdown Cheatsheet"]


def test_a_target_cannot_contain_an_opening_bracket():
    assert meta.extract_links("see [[a[b]]") == [], (
        "the bracket exclusion is what keeps the wikilink scan linear; see tests/test_meta_redos.py"
    )


def test_a_target_is_capped_at_200_characters():
    assert len(meta.extract_links("[[" + "a" * 200 + "]]")) == 1
    assert meta.extract_links("[[" + "a" * 201 + "]]") == []
