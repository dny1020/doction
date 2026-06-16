"""Tests for app.meta — frontmatter / tags / wikilinks / chunking (puro, sin DB)."""

from __future__ import annotations

from app import meta


def test_parse_frontmatter_scalar_and_list():
    content = (
        "---\n"
        "type: decision\n"
        "workspace: telco-core\n"
        "tags: [sip, kamailio]\n"
        "---\n"
        "We migrate SIP proxy to Kamailio.\n"
    )
    fm, body = meta.parse_frontmatter(content)
    assert fm["type"] == "decision"
    assert fm["workspace"] == "telco-core"
    assert fm["tags"] == ["sip", "kamailio"]
    assert body.strip() == "We migrate SIP proxy to Kamailio."


def test_parse_frontmatter_absent():
    fm, body = meta.parse_frontmatter("# Just a heading\nbody")
    assert fm == {}
    assert body == "# Just a heading\nbody"


def test_page_type():
    assert meta.page_type("---\ntype: runbook\n---\nx") == "runbook"
    assert meta.page_type("no frontmatter") is None


def test_extract_tags_frontmatter_and_inline():
    content = (
        "---\ntags: [alpha, beta]\n---\n"
        "Talking about #sip and #Kamailio here.\n"
    )
    assert meta.extract_tags(content) == ["alpha", "beta", "sip", "kamailio"]


def test_extract_tags_ignores_code_and_headings():
    content = (
        "# Heading not a tag\n"
        "Inline `#notatag` stays out.\n"
        "```bash\n# comment #alsonot\necho hi\n```\n"
        "But #real counts.\n"
    )
    assert meta.extract_tags(content) == ["real"]


def test_extract_links_wikilinks():
    content = "See [[SBC Runbook]] and [[failover|the failover doc]] plus [[SBC Runbook]] again."
    assert meta.extract_links(content) == ["SBC Runbook", "failover"]


def test_chunk_markdown_splits_on_paragraphs():
    body = "\n\n".join(f"Paragraph number {i} with some filler text." for i in range(20))
    chunks = meta.chunk_markdown(body, max_chars=200, overlap=20)
    assert len(chunks) > 1
    assert all(len(c) <= 200 for c in chunks)


def test_chunk_markdown_drops_frontmatter():
    content = "---\ntype: note\n---\nActual body content here."
    chunks = meta.chunk_markdown(content)
    assert chunks == ["Actual body content here."]
    assert "type: note" not in "".join(chunks)
