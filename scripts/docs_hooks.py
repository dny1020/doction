"""MkDocs hooks: serve the landing page at the site root, and keep the site offline.

The staged tree keeps `README.md` at the top and `docs/` underneath so every relative link
resolves (see scripts/build_docs.py). That makes the README the root page and puts
`docs/index.md` at `/docs/`. This hook only changes where the two are written; MkDocs
resolves links by source path, so both pages' links keep working and stay checked by
`--strict`.

Runs after MkDocs' own README/index conflict check, which is why the root README does not
trip it.

The README's badges are remote images (shields.io, GitHub). They belong to the repository
page, not to a site that must load nothing from a third-party host, so they are dropped from
the site's copy only.
"""

from mkdocs.structure.files import File

# source path -> output path
DESTINATIONS = {
    "docs/index.md": "index.html",
    "README.md": "introduction/index.html",
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


def on_page_markdown(markdown, page, **_):
    if page.file.src_uri != "README.md":
        return markdown
    kept = []
    for line in markdown.splitlines():
        # A line that is only a remote image, e.g. `[![CI](https://…/badge.svg)](…)`.
        remote_image = line.startswith(("![", "[![")) and "://" in line.split("](", 1)[-1]
        if not remote_image:
            kept.append(line)
    return "\n".join(kept)
