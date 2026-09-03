"""Tests for app.meta — frontmatter / tags / wikilinks / chunking (puro, sin DB)."""

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
    content = "---\ntags: [alpha, beta]\n---\nTalking about #sip and #Kamailio here.\n"
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
    chunks = meta.chunk_markdown(body, max_chars=200)
    assert len(chunks) > 1
    assert all(len(c.text) <= 200 for c in chunks)


def test_chunk_markdown_drops_frontmatter():
    content = "---\ntype: note\n---\nActual body content here."
    chunks = meta.chunk_markdown(content)
    assert [c.text for c in chunks] == ["Actual body content here."]
    assert "type: note" not in "".join(c.text for c in chunks)


# ── Troceado por encabezados ─────────────────────────────────────────────────
# Antes esto partía en ventanas de tamaño fijo: un encabezado y su párrafo caían en
# fragmentos distintos cada vez que la ventana cortaba entre ellos, y una valla de
# código más larga que la ventana se troceaba por posición de carácter.


def test_each_section_is_its_own_chunk():
    doc = "# Uno\n\nCuerpo uno.\n\n# Dos\n\nCuerpo dos."
    chunks = meta.chunk_markdown(doc)
    assert [c.text for c in chunks] == ["Cuerpo uno.", "Cuerpo dos."]
    assert [c.headings for c in chunks] == [["Uno"], ["Dos"]]


def test_nested_headings_build_a_path():
    doc = "# Operaciones\n\n## TLS\n\n### Certbot\n\nCorre certbot renew."
    chunk = meta.chunk_markdown(doc)[-1]
    assert chunk.headings == ["Operaciones", "TLS", "Certbot"]


def test_a_sibling_heading_pops_the_path():
    doc = "# A\n\n## A1\n\nuno\n\n## A2\n\ndos\n\n# B\n\ntres"
    assert [c.headings for c in meta.chunk_markdown(doc)] == [["A", "A1"], ["A", "A2"], ["B"]]


def test_preamble_has_no_headings():
    doc = "Antes de todo.\n\n# Sección\n\nDespués."
    chunks = meta.chunk_markdown(doc)
    assert chunks[0].headings == []
    assert chunks[0].text == "Antes de todo."


def test_a_long_code_fence_stays_whole():
    fence = "```bash\n" + "\n".join(f"echo linea {i}" for i in range(60)) + "\n```"
    chunks = meta.chunk_markdown(f"# Sección\n\n{fence}", max_chars=100)
    fences = [c for c in chunks if "```" in c.text]
    assert len(fences) == 1, "la valla se partió en varios fragmentos"
    assert fences[0].text.count("```") == 2
    assert len(fences[0].text) > 100, "el techo debe ceder ante un bloque indivisible"


def test_headings_inside_a_fence_are_not_headings():
    doc = "# Real\n\n```python\n# esto es un comentario\nx = 1\n```"
    chunks = meta.chunk_markdown(doc)
    assert all(c.headings == ["Real"] for c in chunks)


def test_a_gfm_table_stays_whole():
    table = "| a | b |\n|:--|--:|\n| 1 | 2 |\n| 3 | 4 |"
    chunks = meta.chunk_markdown(f"# T\n\nintro\n\n{table}", max_chars=30)
    tables = [c for c in chunks if "|" in c.text]
    assert len(tables) == 1
    assert tables[0].text == table


def test_a_mermaid_block_stays_whole():
    diagram = "```mermaid\ngraph TD;\n  A-->B;\n\n  B-->C;\n```"
    chunks = meta.chunk_markdown(f"# D\n\n{diagram}", max_chars=20)
    assert [c.text for c in chunks] == [diagram]


def test_an_unclosed_fence_is_not_split():
    doc = "# X\n\n```bash\nuno\n\ndos\n\ntres"
    chunks = meta.chunk_markdown(doc, max_chars=10)
    assert len(chunks) == 1
    assert chunks[0].text.startswith("```bash")


def test_a_tag_at_the_start_of_a_line_is_not_a_heading():
    doc = "#infra y algo más"
    chunks = meta.chunk_markdown(doc)
    assert chunks[0].headings == []
    assert chunks[0].text == "#infra y algo más"


def test_an_empty_page_produces_no_chunks():
    assert meta.chunk_markdown("") == []
    assert meta.chunk_markdown("---\ntype: note\n---\n") == []
