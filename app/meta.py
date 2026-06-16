"""Parsing markdown-como-API: frontmatter, tags, wikilinks y chunking.

Sin dependencias: la "estructura" sale del propio markdown (filosofía Unix). Estas
funciones son puras; el indexado en SQLite vive en app.db.
"""

from __future__ import annotations

import re

_FRONTMATTER_RE = re.compile(r"^---[ \t]*\n(.*?)\n---[ \t]*\n?", re.DOTALL)
_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`[^`]*`")
_TAG_RE = re.compile(r"(?:^|\s)#([A-Za-z][\w-]*)")
_WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]")


def normalize_tag(tag: str) -> str:
    return tag.strip().lstrip("#").lower()


def _strip_code(text: str) -> str:
    """Quita bloques ``` y spans `inline` para no confundir comentarios con #tags."""
    text = _FENCE_RE.sub(" ", text)
    return _INLINE_CODE_RE.sub(" ", text)


def _parse_scalar_or_list(value: str):
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1]
        return [v.strip().strip("\"'") for v in inner.split(",") if v.strip()]
    return value.strip("\"'")


def parse_frontmatter(content: str) -> tuple[dict, str]:
    """Extrae un bloque YAML-lite inicial (--- ... ---) y devuelve (meta, cuerpo).

    Parser plano sin dependencia: soporta `clave: valor` escalar y listas inline
    `tags: [a, b]`. Si no hay frontmatter devuelve ({}, content) sin tocar el cuerpo.
    """
    if not content:
        return {}, content
    match = _FRONTMATTER_RE.match(content)
    if not match:
        return {}, content
    meta: dict = {}
    for line in match.group(1).splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or ":" not in line:
            continue
        key, _, raw = line.partition(":")
        key = key.strip().lower()
        if key:
            meta[key] = _parse_scalar_or_list(raw)
    return meta, content[match.end():]


def extract_tags(content: str) -> list[str]:
    """Tags normalizados desde frontmatter `tags:` y `#tags` inline (ignora código)."""
    meta, body = parse_frontmatter(content)
    found: list[str] = []

    fm_tags = meta.get("tags")
    if isinstance(fm_tags, list):
        found.extend(fm_tags)
    elif isinstance(fm_tags, str) and fm_tags:
        found.extend(fm_tags.split(","))

    for m in _TAG_RE.finditer(_strip_code(body)):
        found.append(m.group(1))

    seen: set[str] = set()
    out: list[str] = []
    for raw in found:
        tag = normalize_tag(raw)
        if tag and tag not in seen:
            seen.add(tag)
            out.append(tag)
    return out


def extract_links(content: str) -> list[str]:
    """Targets crudos de wikilinks `[[target]]` o `[[target|texto]]` (sin código)."""
    seen: set[str] = set()
    out: list[str] = []
    for m in _WIKILINK_RE.finditer(_strip_code(content)):
        target = m.group(1).strip()
        if target and target not in seen:
            seen.add(target)
            out.append(target)
    return out


def page_type(content: str) -> str | None:
    """Valor de `type:` del frontmatter, o None."""
    meta, _ = parse_frontmatter(content)
    value = meta.get("type")
    if isinstance(value, list):
        value = value[0] if value else None
    return value if isinstance(value, str) and value else None


def chunk_markdown(text: str, *, max_chars: int = 1000, overlap: int = 150) -> list[str]:
    """Parte el cuerpo en ventanas ~max_chars respetando límites de párrafo.

    Tonto y rápido (no usa el tokenizer): el modelo trunca de todos modos. El
    frontmatter se descarta para no contaminar los embeddings.
    """
    _, body = parse_frontmatter(text or "")
    body = body.strip()
    if not body:
        return []

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        if len(para) > max_chars:
            # Párrafo enorme (p.ej. bloque de código): trocea por ventanas con solape.
            if current:
                chunks.append(current)
                current = ""
            step = max_chars - overlap
            for i in range(0, len(para), step):
                chunks.append(para[i : i + max_chars])
            continue
        if current and len(current) + len(para) + 2 > max_chars:
            chunks.append(current)
            current = para
        else:
            current = f"{current}\n\n{para}" if current else para
    if current:
        chunks.append(current)
    return chunks
