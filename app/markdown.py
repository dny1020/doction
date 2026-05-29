"""Markdown -> HTML rendering for doction."""

from __future__ import annotations

from markdown_it import MarkdownIt

_md = MarkdownIt("commonmark", {"html": True, "linkify": True, "typographer": True})
_md.enable(["table", "strikethrough"])


def render_markdown(text: str) -> str:
    return _md.render(text or "")
