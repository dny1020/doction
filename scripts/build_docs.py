#!/usr/bin/env python3
"""Builds the documentation site, strictly, from the tracked documentation.

    uv run --group docs python -m scripts.build_docs          # build into site/
    uv run --group docs python -m scripts.build_docs --serve  # local preview

Links inside `docs/` point above it and MkDocs cannot reach outside its `docs_dir`, so the
build stages a tree with the root documents at the top and `docs/` underneath — the shape
the relative links already assume. The staged copies are build output, never committed.

`--strict` is always on: a link that does not resolve fails the build rather than publishing.
After a build, `check_site()` inspects what was produced: every page carries its title,
description and social-preview tags, `robots.txt` exists, and nothing is loaded from another host.
"""

import argparse
import shutil
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
STAGE = ROOT / "build" / "docs"
SITE = ROOT / "site"
# The site uses the application's own vendored fonts, copied at build time so the binaries have
# one source and the site makes no request to a font CDN.
FONTS = ROOT / "app" / "static" / "vendor" / "fonts"

# Documents outside `docs/` that the site needs, each because something in the site links to it.
# Paths are repository-relative and keep their shape in the staged tree, so the relative links
# from `docs/` resolve unchanged.
ROOT_DOCS = [
    "README.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "DESIGN.md",
    "CHANGELOG.md",
    "CODE_OF_CONDUCT.md",
    # No extension, so MkDocs treats it as a static file and the link still resolves.
    "LICENSE",
]


def stage() -> None:
    if STAGE.exists():
        shutil.rmtree(STAGE)
    STAGE.mkdir(parents=True)
    shutil.copytree(ROOT / "docs", STAGE / "docs")
    shutil.copytree(FONTS, STAGE / "docs" / "assets" / "fonts")
    for name in ROOT_DOCS:
        source = ROOT / name
        if not source.exists():
            print(f"error: {name} is missing; the site expects it", file=sys.stderr)
            raise SystemExit(2)
        target = STAGE / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


# What a page must carry. 404.html is served for any missing path and only needs a title.
REQUIRED_META = ("description", "og:title", "og:description", "og:image", "twitter:card")
# Elements that load a resource, and the attribute naming it. `<a href>` is a link, not a load.
LOADING_TAGS = {"script": "src", "img": "src", "source": "src", "iframe": "src", "link": "href"}
LOADING_RELS = {"stylesheet", "icon", "preload", "modulepreload", "apple-touch-icon", "manifest"}


class PageScan(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = False
        self.meta: set[str] = set()
        self.loads: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k: v or "" for k, v in attrs}
        if tag == "title":
            self.title = True
        elif tag == "meta":
            self.meta.add(a.get("name") or a.get("property") or "")
        attr = LOADING_TAGS.get(tag)
        if attr and a.get(attr):
            if tag == "link" and not LOADING_RELS & set(a.get("rel", "").split()):
                return
            self.loads.append(a[attr])


def is_remote(url: str, own_host: str) -> bool:
    host = urlsplit(url.strip("'\" ")).netloc
    return bool(host) and host != own_host


def check_site() -> int:
    """Fails the build on a page missing its metadata or on any resource from another host."""
    site_url = ""
    for line in (ROOT / "mkdocs.yml").read_text(encoding="utf-8").splitlines():
        if line.startswith("site_url:"):
            site_url = line.split(":", 1)[1].strip()
    own_host = urlsplit(site_url).netloc

    failures: list[str] = []
    if not (SITE / "robots.txt").is_file():
        failures.append("robots.txt: missing from the site root")

    pages = sorted(SITE.rglob("*.html"))
    for page in pages:
        name = str(page.relative_to(SITE))
        scan = PageScan()
        try:
            scan.feed(page.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError) as exc:
            failures.append(f"{name}: unreadable ({exc})")
            continue
        if not scan.title:
            failures.append(f"{name}: no <title>")
        if name != "404.html":
            for key in REQUIRED_META:
                if key not in scan.meta:
                    failures.append(f"{name}: no {key}")
        for url in scan.loads:
            if is_remote(url, own_host):
                failures.append(f"{name}: loads {url} from another host")

    sheets = sorted(SITE.rglob("*.css"))
    for sheet in sheets:
        text = sheet.read_text(encoding="utf-8", errors="replace")
        for chunk in text.split("url(")[1:]:
            url = chunk.split(")", 1)[0]
            if is_remote(url, own_host):
                failures.append(f"{sheet.relative_to(SITE)}: loads {url} from another host")

    if failures:
        print(f"\ndocs: the built site failed {len(failures)} check(s):", file=sys.stderr)
        for failure in failures:
            print(f"  {failure}", file=sys.stderr)
        return 1
    print(
        f"docs: {len(pages)} pages and {len(sheets)} stylesheets checked: "
        "metadata complete, nothing off-site"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--serve", action="store_true", help="serve locally instead of building")
    args = parser.parse_args()

    try:
        import mkdocs  # noqa: F401
    except ImportError:
        print(
            "error: mkdocs is not installed. It lives in the `docs` dependency group, which is\n"
            "       not installed by default: uv sync --group docs",
            file=sys.stderr,
        )
        return 2

    stage()
    command = ["mkdocs", "serve", "--strict"] if args.serve else ["mkdocs", "build", "--strict"]
    try:
        result = subprocess.run(command, cwd=ROOT, timeout=None if args.serve else 300)
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"error: mkdocs failed to run: {exc}", file=sys.stderr)
        return 2
    if result.returncode != 0:
        print("\ndocs: the site build failed. A link that does not resolve is a failure here.")
        return 1
    if args.serve:
        return 0
    print(f"docs: site built into {SITE.relative_to(ROOT)}/, strict mode, no broken links")
    return check_site()


if __name__ == "__main__":
    raise SystemExit(main())
