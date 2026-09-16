"""Markdown as an API: frontmatter, tags, wikilinks and chunking.

Dependency-free and pure — the structure comes out of the markdown itself. Indexing
lives in app.db.
"""

import re

from app.models import Chunk

_FRONTMATTER_RE = re.compile(r"^---[ \t]*\n(.*?)\n---[ \t]*\n?", re.DOTALL)
_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`[^`]*`")
_TAG_RE = re.compile(r"(?:^|\s)#([A-Za-z][\w-]*)")
# Excluding `[` from both classes is what keeps the scan linear: a bad start fails at
# the next `[` instead of running to the end of the input. The length caps are extra
# defence, and true — a wikilink target is a title, not a document.
# See tests/test_meta_redos.py.
_WIKILINK_RE = re.compile(r"\[\[([^\]|\[]{1,200})(?:\|[^\]\[]{0,200})?\]\]")


def normalize_tag(tag: str) -> str:
    return tag.strip().lstrip("#").lower()


def strip_code(text: str) -> str:
    """Strip fenced blocks and inline spans so code comments are not read as #tags."""
    text = _FENCE_RE.sub(" ", text)
    return _INLINE_CODE_RE.sub(" ", text)


def _parse_scalar_or_list(value: str):
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1]
        return [v.strip().strip("\"'") for v in inner.split(",") if v.strip()]
    return value.strip("\"'")


def parse_frontmatter(content: str) -> tuple[dict, str]:
    """Split a leading YAML-lite block off the body, returning (meta, body).

    Scalars and inline lists (`tags: [a, b]`) only. With no frontmatter the body comes
    back untouched.
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
    """Normalized tags from frontmatter `tags:` and inline `#tags`, ignoring code."""
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
    """Raw `[[target]]` / `[[target|label]]` targets, ignoring code."""
    seen: set[str] = set()
    out: list[str] = []
    for m in _WIKILINK_RE.finditer(strip_code(content)):
        target = m.group(1).strip()
        if target and target not in seen:
            seen.add(target)
            out.append(target)
    return out


_SENTENCE_END = ".!?\n"


def mention_context(content: str, target: str, *, width: int = 160) -> tuple[str, str, str] | None:
    """The sentence linking to `target`, split into (before, link, after).

    The link part is the label text, which is what a reader sees, not `[[target]]`.
    None when there is no mention.
    """
    text = strip_code(content)
    for m in _WIKILINK_RE.finditer(text):
        if m.group(1).strip() != target:
            continue
        inner = m.group(0)[2:-2]
        bar = inner.find("|")
        label = (inner[bar + 1 :].strip() if bar != -1 else "") or inner.strip()

        lo = max(0, m.start() - width)
        cut = max(text.rfind(c, lo, m.start()) for c in _SENTENCE_END)
        start = cut + 1 if cut != -1 else lo

        hi = min(len(text), m.end() + width)
        ends = [i for i in (text.find(c, m.end(), hi) for c in _SENTENCE_END) if i != -1]
        end = min(ends) + 1 if ends else hi

        # Only the outer edges are stripped: the space next to the link belongs to the
        # document.
        return text[start : m.start()].lstrip(), label, text[m.end() : end].rstrip()
    return None


UNTITLED = "Untitled"


def derive_title(content: str, *, max_len: int = 80) -> str:
    """Title from the first line with text, so a one-line note needs no title of its own."""
    _, body = parse_frontmatter(content)
    for line in body.splitlines():
        line = line.strip().lstrip("#").strip()
        if line:
            return line[:max_len].rstrip()
    return UNTITLED


def page_type(content: str) -> str | None:
    """The frontmatter `type:` value, or None."""
    meta, _ = parse_frontmatter(content)
    value = meta.get("type")
    if isinstance(value, list):
        value = value[0] if value else None
    return value if isinstance(value, str) and value else None


# Stored alongside the vectors like the model name is: two ways of splitting a page
# produce chunks that mean as little to compare as two encoders would. Bumping this is
# what triggers a reindex.
CHUNKER_ID = "section-heading-v1"

_FENCES = ("```", "~~~")


def _heading_level(stripped: str) -> int:
    """ATX heading level (1-6), or 0 when the line is not one."""
    level = len(stripped) - len(stripped.lstrip("#"))
    if not 1 <= level <= 6:
        return 0
    rest = stripped[level:]
    # `#tag` at the start of a line is a tag, not a level-1 heading.
    return level if rest == "" or rest[0] == " " else 0


def _sections(body: str) -> list[tuple[list[str], list[str]]]:
    """Split the body at headings into (heading chain, lines) per section.

    Headings inside a code fence do not count: a `# TODO` in a Python block is not one.
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
    """Group lines into blocks that must not be split internally.

    A block is a whole code fence or a paragraph. GFM tables and Mermaid diagrams come
    free from that: a table has no blank lines, and a diagram lives inside a fence.
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
    """Pack blocks up to the ceiling; a block that does not fit goes alone and overflows."""
    chunks: list[str] = []
    current = ""
    for block in blocks:
        if len(block) > max_chars:
            if current:
                chunks.append(current)
                current = ""
            # The ceiling gives: a long chunk embeds worse, half a table answers wrong.
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
    """Split a page into indexable chunks along its headings.

    One chunk per section, carrying the heading chain that places it. No overlap: between
    sections it would duplicate content, and within one the cuts already fall on paragraph
    boundaries. Frontmatter stays out of the body — it is metadata, not prose.
    """
    _, body = parse_frontmatter(text or "")
    chunks: list[Chunk] = []
    for headings, lines in _sections(body):
        for piece in _pack(_atomic_blocks(lines), max_chars):
            chunks.append(Chunk(text=piece, headings=headings))
    return chunks


# ── Section writes ───────────────────────────────────────────────────────────


class AmbiguousSection(ValueError):
    """More than one heading matches: which one was meant is not guessed for the caller."""


def _headings(body: str) -> list[tuple[int, int, str]]:
    """(line index, level, text) for each heading, skipping fenced blocks."""
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
    """Locate a section by heading: (start line, end line, level).

    The end is exclusive and falls at the next heading of equal or higher level, where
    what hangs off this one stops. Raises `AmbiguousSection` or `LookupError`.
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
    """Return `content` with section `heading` set to `body`.

    An existing section has only its body replaced and the rest of the document stays
    byte for byte identical; a missing one is appended, under `parent` when given.
    Frontmatter is never touched.
    """
    front, page_body = _split_frontmatter(content or "")
    heading = heading.strip()
    body = body.strip("\n")

    try:
        start, end, found_level = find_section(page_body, heading)
        lines = page_body.split("\n")
        block = [lines[start], "", body] if body else [lines[start]]
        rest = lines[end:]
        # A blank line between the section and whatever follows, except at the end.
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
    """(frontmatter block verbatim, rest); the block is empty when there is none."""
    match = _FRONTMATTER_RE.match(content)
    if not match:
        return "", content
    return match.group(0), content[match.end() :]
