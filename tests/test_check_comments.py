"""Tests for the check that keeps comments and docstrings in English."""

from scripts.check_comments import findings


def test_spanish_python_comment_is_reported():
    src = "x = 1\n# esto está en español\n"
    assert findings("a.py", src) == [(2, "# esto está en español")]


def test_spanish_docstring_is_reported():
    src = 'def f():\n    """Devuelve la página."""\n'
    assert [line for line, _ in findings("a.py", src)] == [2]


def test_spanish_in_string_data_is_allowed():
    src = 'STOPWORDS = {"también", "según"}\nLABEL = "Añadir página"  # UI label\n'
    assert findings("a.py", src) == []


def test_quoted_example_inside_a_comment_is_allowed():
    src = '# "ñ" is 2 bytes in UTF-8\n# the `¿` mark opens a question\n'
    assert findings("a.py", src) == []


def test_js_url_in_a_string_is_not_a_comment():
    src = "const url = 'https://example.com/página' // English comment\n"
    assert findings("a.js", src) == []


def test_js_regex_is_not_a_comment():
    src = "const re = /a\\/*b/ // matches\n/* también */\n"
    assert findings("a.js", src) == [(2, "/* también */")]


def test_jsx_block_comment_is_reported():
    src = "return (\n  <div>\n    {/* barra lateral del menú */}\n  </div>\n)\n"
    assert [line for line, _ in findings("a.jsx", src)] == [3]


def test_css_comment_is_reported_but_content_string_is_not():
    src = ".a::after { content: 'é'; }\n/* Corrección */\n"
    assert findings("a.css", src) == [(2, "/* Corrección */")]


def test_multiline_block_reports_the_offending_line():
    src = "/* English first line\n   segunda línea */\n"
    assert findings("a.css", src) == [(2, "segunda línea */")]


def test_yaml_hash_inside_quotes_is_not_a_comment():
    src = 'name: "ci #1 información"\nkey: value  # comentario sí\n'
    assert findings("ci.yaml", src) == [(2, "# comentario sí")]


def test_html_comment_and_inline_script_are_reported():
    src = "<!-- página -->\n<script>\n  /* tema guardado sí */\n</script>\n"
    assert [line for line, _ in findings("index.html", src)] == [1, 3]


def test_untracked_kinds_are_ignored():
    assert findings("notes.md", "# Título en español\n") == []
