"""Parsing markdown-como-API: frontmatter, tags, wikilinks y chunking.

Sin dependencias: la "estructura" sale del propio markdown (filosofía Unix). Estas
funciones son puras; el indexado en SQLite vive en app.db.
"""

import re

from app.models import Chunk

_FRONTMATTER_RE = re.compile(r"^---[ \t]*\n(.*?)\n---[ \t]*\n?", re.DOTALL)
_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`[^`]*`")
_TAG_RE = re.compile(r"(?:^|\s)#([A-Za-z][\w-]*)")
_WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]")


def normalize_tag(tag: str) -> str:
    return tag.strip().lstrip("#").lower()


def strip_code(text: str) -> str:
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
    return meta, content[match.end() :]


def extract_tags(content: str) -> list[str]:
    """Tags normalizados desde frontmatter `tags:` y `#tags` inline (ignora código)."""
    meta, body = parse_frontmatter(content)
    found: list[str] = []

    fm_tags = meta.get("tags")
    if isinstance(fm_tags, list):
        found.extend(fm_tags)
    elif isinstance(fm_tags, str) and fm_tags:
        found.extend(fm_tags.split(","))

    for m in _TAG_RE.finditer(strip_code(body)):
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
    for m in _WIKILINK_RE.finditer(strip_code(content)):
        target = m.group(1).strip()
        if target and target not in seen:
            seen.add(target)
            out.append(target)
    return out


UNTITLED = "Untitled"


def derive_title(content: str, *, max_len: int = 80) -> str:
    """Título a partir de la primera línea con texto; UNTITLED si no hay ninguna.

    Para la captura rápida: una nota de una línea no debería obligar a inventar
    un título. Se ignora el frontmatter y se limpia el marcado de encabezado.
    """
    _, body = parse_frontmatter(content)
    for line in body.splitlines():
        line = line.strip().lstrip("#").strip()
        if line:
            return line[:max_len].rstrip()
    return UNTITLED


def page_type(content: str) -> str | None:
    """Valor de `type:` del frontmatter, o None."""
    meta, _ = parse_frontmatter(content)
    value = meta.get("type")
    if isinstance(value, list):
        value = value[0] if value else None
    return value if isinstance(value, str) and value else None


# Identidad del troceador. Va grabada junto a los vectores igual que el modelo:
# dos formas de partir una página producen fragmentos distintos, así que compararlos
# por coseno significa tan poco como mezclar dos encoders. Cambiar el algoritmo
# obliga a subir esto, y eso es lo que dispara el reindexado.
CHUNKER_ID = "markdown-header-v1"

# Vallas de código. Se cierran con la misma marca con la que abren.
_FENCES = ("```", "~~~")


def _heading_level(stripped: str) -> int:
    """Nivel de un encabezado ATX (1-6), o 0 si la línea no lo es."""
    level = len(stripped) - len(stripped.lstrip("#"))
    if not 1 <= level <= 6:
        return 0
    rest = stripped[level:]
    # `#tag` al principio de línea es una etiqueta, no un encabezado de nivel 1.
    return level if rest == "" or rest[0] == " " else 0


def _sections(body: str) -> list[tuple[list[str], list[str]]]:
    """Parte el cuerpo por encabezados: (cadena de encabezados, líneas) por sección.

    Los encabezados dentro de una valla de código no cuentan — un comentario `# TODO`
    en un bloque de Python abría una sección donde no la hay.
    """
    sections: list[tuple[list[str], list[str]]] = []
    stack: list[tuple[int, str]] = []
    lines: list[str] = []
    fence: str | None = None

    def flush() -> None:
        if any(line.strip() for line in lines):
            sections.append(([text for _, text in stack], lines[:]))
        lines.clear()

    for line in body.split("\n"):
        stripped = line.strip()
        if fence is not None:
            lines.append(line)
            if stripped.startswith(fence):
                fence = None
            continue
        opening = next((f for f in _FENCES if stripped.startswith(f)), None)
        if opening is not None:
            fence = opening
            lines.append(line)
            continue
        level = _heading_level(stripped)
        if level:
            flush()
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, stripped[level:].strip()))
            continue
        lines.append(line)

    flush()
    return sections


def _atomic_blocks(lines: list[str]) -> list[str]:
    """Agrupa las líneas en bloques que no se pueden partir por dentro.

    Un bloque es una valla de código entera o un párrafo. Las tablas GFM y los
    diagramas Mermaid salen gratis de esa definición: la tabla no lleva líneas en
    blanco, así que ya es un párrafo, y el diagrama vive dentro de una valla. Una
    valla sin cerrar se queda entera igualmente — media valla es peor que una larga.
    """
    blocks: list[str] = []
    current: list[str] = []
    fence: str | None = None

    def flush() -> None:
        joined = "\n".join(current).strip()
        if joined:
            blocks.append(joined)
        current.clear()

    for line in lines:
        stripped = line.strip()
        if fence is not None:
            current.append(line)
            if stripped.startswith(fence):
                flush()
                fence = None
            continue
        opening = next((f for f in _FENCES if stripped.startswith(f)), None)
        if opening is not None:
            flush()
            fence = opening
            current.append(line)
            continue
        if not stripped:
            flush()
            continue
        current.append(line)

    flush()
    return blocks


def _pack(blocks: list[str], max_chars: int) -> list[str]:
    """Junta bloques hasta el techo. Un bloque que no cabe va solo y lo desborda."""
    chunks: list[str] = []
    current = ""
    for block in blocks:
        if len(block) > max_chars:
            if current:
                chunks.append(current)
                current = ""
            # El techo cede: un fragmento largo es un embedding peor, media tabla
            # es una respuesta equivocada.
            chunks.append(block)
            continue
        if current and len(current) + len(block) + 2 > max_chars:
            chunks.append(current)
            current = block
        else:
            current = f"{current}\n\n{block}" if current else block
    if current:
        chunks.append(current)
    return chunks


def chunk_markdown(text: str, *, max_chars: int = 1000) -> list[Chunk]:
    """Parte una página en fragmentos indexables siguiendo sus encabezados.

    Antes esto partía por líneas en blanco en ventanas de tamaño fijo, con solape.
    Un encabezado y el párrafo que introducía caían en fragmentos distintos cada vez
    que la ventana cortaba entre ellos, y una valla de código más larga que la
    ventana se troceaba por posición de carácter. El fragmento recuperado decía
    «corre `certbot renew`» sin decir de qué runbook.

    Ahora cada sección es un fragmento y lleva encima la cadena de encabezados que la
    sitúa. El solape desaparece: entre secciones duplicaría contenido, y dentro de
    una sección los cortes ya caen en límites de párrafo.

    El frontmatter sigue fuera del cuerpo — es metadato, no prosa — pero ya no se
    pierde: `parse_frontmatter` lo devuelve aparte y quien indexa lo guarda.
    """
    _, body = parse_frontmatter(text or "")
    chunks: list[Chunk] = []
    for headings, lines in _sections(body):
        for piece in _pack(_atomic_blocks(lines), max_chars):
            chunks.append(Chunk(text=piece, headings=headings))
    return chunks


# ── Escritura por secciones ──────────────────────────────────────────────────
# Un agente que aprende un dato tenía que leer la página entera, empalmar el texto
# él mismo y devolverla completa, pisando lo que hubiera cambiado otro por el
# camino. Estas funciones acotan la escritura a una sección.


class AmbiguousSection(ValueError):
    """La página tiene más de un encabezado que encaja: no se elige por el llamante."""


def _headings(body: str) -> list[tuple[int, int, str]]:
    """(índice de línea, nivel, texto) de cada encabezado, saltándose las vallas."""
    found: list[tuple[int, int, str]] = []
    fence: str | None = None
    for i, line in enumerate(body.split("\n")):
        stripped = line.strip()
        if fence is not None:
            if stripped.startswith(fence):
                fence = None
            continue
        opening = next((f for f in _FENCES if stripped.startswith(f)), None)
        if opening is not None:
            fence = opening
            continue
        level = _heading_level(stripped)
        if level:
            found.append((i, level, stripped[level:].strip()))
    return found


def find_section(body: str, heading: str, *, level: int | None = None) -> tuple[int, int, int]:
    """Localiza una sección por su encabezado: (línea inicial, línea final, nivel).

    El final es exclusivo y cae en el siguiente encabezado de nivel igual o superior,
    que es donde termina lo que cuelga de este. Lanza `AmbiguousSection` si encajan
    varios y `LookupError` si no encaja ninguno.
    """
    wanted = heading.strip().casefold()
    all_headings = _headings(body)
    matches = [
        (i, lvl, text)
        for i, lvl, text in all_headings
        if text.casefold() == wanted and (level is None or lvl == level)
    ]
    if not matches:
        raise LookupError(heading)
    if len(matches) > 1:
        levels = sorted({lvl for _, lvl, _ in matches})
        raise AmbiguousSection(
            f"{len(matches)} headings match {heading!r} (levels {levels}); "
            "pass `level` to disambiguate, or rename one of them"
        )

    start, found_level, _ = matches[0]
    end = len(body.split("\n"))
    for i, lvl, _ in all_headings:
        if i > start and lvl <= found_level:
            end = i
            break
    return start, end, found_level


def upsert_section(
    content: str,
    heading: str,
    body: str,
    *,
    level: int = 2,
    parent: str | None = None,
) -> str:
    """Devuelve `content` con la sección `heading` puesta a `body`.

    Si la sección existe se reemplaza solo su cuerpo, hasta el siguiente encabezado
    de nivel igual o superior, y el resto del documento queda byte a byte igual. Si
    no existe se añade: bajo `parent` cuando se indica y se encuentra, y si no al
    final del documento.

    El frontmatter no se toca nunca: es metadato de la página entera, no de ninguna
    sección.
    """
    front, page_body = _split_frontmatter(content or "")
    heading = heading.strip()
    body = body.strip("\n")

    try:
        start, end, found_level = find_section(page_body, heading)
        lines = page_body.split("\n")
        block = [lines[start], "", body] if body else [lines[start]]
        rest = lines[end:]
        # Una línea en blanco entre la sección y lo que venga detrás, salvo al final.
        if rest:
            block.append("")
        new_body = "\n".join([*lines[:start], *block, *rest])
        return front + new_body
    except LookupError:
        pass

    marker = "#" * max(1, min(level, 6))
    section = f"{marker} {heading}\n\n{body}".rstrip() + "\n"

    if parent:
        try:
            _, parent_end, _ = find_section(page_body, parent)
        except LookupError:
            parent_end = None
        if parent_end is not None:
            lines = page_body.split("\n")
            head = "\n".join(lines[:parent_end]).rstrip("\n")
            tail = "\n".join(lines[parent_end:])
            return front + f"{head}\n\n{section}\n{tail}".rstrip("\n") + "\n"

    return front + page_body.rstrip("\n") + f"\n\n{section}"


def _split_frontmatter(content: str) -> tuple[str, str]:
    """(bloque de frontmatter tal cual, resto). El bloque va vacío si no hay."""
    match = _FRONTMATTER_RE.match(content)
    if not match:
        return "", content
    return match.group(0), content[match.end() :]
