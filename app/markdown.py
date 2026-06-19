from __future__ import annotations

from markdown_it import MarkdownIt

# html=False: el HTML crudo embebido en una página se escapa como texto en vez de
# renderizarse. Cierra el XSS almacenado (un <script> en una página compartida no se
# ejecuta para los demás miembros) y mantiene el servidor en CommonMark plano, sin
# dependencias de sanitización.
_md = MarkdownIt("commonmark", {"html": False, "linkify": True, "typographer": True})
_md.enable(["table", "strikethrough"])


def render_markdown(text: str) -> str:
    return _md.render(text or "")
