"""Tests for the check that keeps the Spanish documentation in step with the English one."""

from scripts.build_docs import drift, source_hash, stamp


def pages(tmp_path, english, spanish):
    en, es = tmp_path / "docs", tmp_path / "docs" / "es"
    es.mkdir(parents=True)
    for name, text in english.items():
        (en / f"{name}.md").write_text(text, encoding="utf-8")
    for name, text in spanish.items():
        (es / f"{name}.md").write_text(text, encoding="utf-8")
    return en, es


def test_all_agree_after_stamping(tmp_path):
    en, es = pages(tmp_path, {"install": "# Install\n"}, {"install": "# Instalación\n"})
    stamp(en / "install.md", es / "install.md")
    assert drift(en, es) == []


def test_missing_counterpart_names_the_page(tmp_path):
    en, es = pages(tmp_path, {"install": "# Install\n", "backups": "# Backups\n"}, {"install": ""})
    stamp(en / "install.md", es / "install.md")
    assert drift(en, es) == ["backups: no Spanish counterpart in docs/es/"]


def test_orphan_spanish_page_names_the_page(tmp_path):
    en, es = pages(tmp_path, {"install": "x"}, {"install": "y", "copias": "z"})
    stamp(en / "install.md", es / "install.md")
    assert drift(en, es) == ["copias: Spanish page with no English source"]


def test_edited_english_page_is_stale(tmp_path):
    en, es = pages(tmp_path, {"install": "# Install\n"}, {"install": "# Instalación\n"})
    stamp(en / "install.md", es / "install.md")
    (en / "install.md").write_text("# Install, edited\n", encoding="utf-8")
    [failure] = drift(en, es)
    assert failure.startswith("install: English page changed")


def test_nothing_to_compare_is_not_agreement(tmp_path):
    en, es = pages(tmp_path, {}, {})
    assert drift(en, es) == ["no page compared: docs/ and docs/es/ share no page"]


def test_stamp_changes_only_the_hash(tmp_path):
    en, es = pages(
        tmp_path,
        {"index": "# Home\n"},
        {"index": "---\nsource_sha256: old\nhide:\n  - toc\n---\n# Inicio\n"},
    )
    stamp(en / "index.md", es / "index.md")
    field = f"source_sha256: {source_hash(en / 'index.md')}"
    expected = f"---\n{field}\nhide:\n  - toc\n---\n# Inicio\n"
    assert (es / "index.md").read_text(encoding="utf-8") == expected


def test_stamp_adds_front_matter_when_absent(tmp_path):
    en, es = pages(tmp_path, {"api": "# API\n"}, {"api": "# API\n\nTexto.\n"})
    stamp(en / "api.md", es / "api.md")
    text = (es / "api.md").read_text(encoding="utf-8")
    assert text == f"---\nsource_sha256: {source_hash(en / 'api.md')}\n---\n# API\n\nTexto.\n"
