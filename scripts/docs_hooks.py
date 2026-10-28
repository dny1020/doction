"""MkDocs hooks: page destinations, link previews and keeping the site offline.

- Writes `docs/index.md` at `/` and the README at `/introduction/`; links still resolve by
  source path.
- Drops the README's remote badge images from the site's copy.
- Gives a page without a `description` one from its first paragraph.
"""

import re

from mkdocs.structure.files import File

DESCRIPTION_MAX = 160
# Blocks that are not a paragraph of prose: headings, HTML, fences, tables, lists, quotes,
# admonitions and images.
NOT_PROSE = ("#", "<", "```", "~~~", "|", "- ", "* ", "+ ", ">", "!!!", "???", "![", "[![", "---")

# source path -> output path
DESTINATIONS = {
    "docs/index.md": "index.html",
    "README.md": "introduction/index.html",
    "docs/robots.txt": "robots.txt",
}


def on_files(files, config):
    for src, dest in DESTINATIONS.items():
        current = files.get_file_from_path(src)
        if current is None:
            raise SystemExit(f"docs_hooks: {src} is missing from the staged tree")
        # A new File rather than assigning dest_uri: `url` and `abs_dest_path` are cached.
        moved = File(
            src,
            config["docs_dir"],
            config["site_dir"],
            config["use_directory_urls"],
            dest_uri=dest,
        )
        files.remove(current)
        files.append(moved)
    return files


def first_paragraph(markdown):
    for block in markdown.split("\n\n"):
        block = block.strip()
        if not block or block.startswith(NOT_PROSE) or block[0].isdigit():
            continue
        text = " ".join(block.split())
        text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", text)  # [label](target) -> label
        return text.replace("`", "").replace("**", "").replace("*", "")
    return ""


def describe(text):
    # A paragraph ending in a colon introduces a list; describe with what comes before it.
    if text.endswith(":"):
        if ". " in text:
            text = text[: text.rindex(". ") + 1]
        elif ", " in text:
            text = text[: text.rindex(", ")] + "."
    if len(text) <= DESCRIPTION_MAX:
        return text
    return text[: DESCRIPTION_MAX - 1].rsplit(" ", 1)[0].rstrip(",;:") + "…"


def on_page_markdown(markdown, page, **_):
    if not page.meta.get("description"):
        text = first_paragraph(markdown)
        if text:
            page.meta["description"] = describe(text)
    if page.file.src_uri != "README.md":
        return markdown
    kept = []
    for line in markdown.splitlines():
        # A line that is only a remote image, e.g. `[![CI](https://…/badge.svg)](…)`.
        remote_image = line.startswith(("![", "[![")) and "://" in line.split("](", 1)[-1]
        if not remote_image:
            kept.append(line)
    return "\n".join(kept)
