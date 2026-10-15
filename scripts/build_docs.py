#!/usr/bin/env python3
"""Builds the documentation site, strictly, from the tracked documentation.

    uv run --group docs python -m scripts.build_docs          # build into site/
    uv run --group docs python -m scripts.build_docs --serve  # local preview, English
    uv run python -m scripts.build_docs --stamp install       # record a reviewed translation

Stages root documents above `docs/` so their relative links resolve, refuses a Spanish page set
that drifted from the English one, builds both languages with `--strict` (Spanish into `site/es/`),
then `check_site()` verifies metadata, robots.txt, hreflang and that nothing loads off-site.
"""

import argparse
import hashlib
import shutil
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
STAGE = ROOT / "build" / "docs"
SITE = ROOT / "site"
# The Spanish sources mirror docs/ one to one; mkdocs.es.yml builds them into site/es/.
DOCS = ROOT / "docs"
ES_DOCS = DOCS / "es"
STAGE_ES = ROOT / "build" / "docs-es"
SITE_ES = SITE / "es"
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

    # Its own copy of the assets, so the Spanish site works when built or served alone.
    if STAGE_ES.exists():
        shutil.rmtree(STAGE_ES)
    shutil.copytree(ES_DOCS, STAGE_ES / "docs")
    shutil.copytree(DOCS / "assets", STAGE_ES / "docs" / "assets")
    shutil.copytree(FONTS, STAGE_ES / "docs" / "assets" / "fonts")


def source_hash(english: Path) -> str:
    return hashlib.sha256(english.read_bytes()).hexdigest()


def recorded_hash(spanish: Path) -> str:
    """The `source_sha256` in a Spanish page's front matter, or "" when it has none."""
    lines = spanish.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != "---":
        return ""
    for line in lines[1:]:
        if line == "---":
            break
        if line.startswith("source_sha256:"):
            return line.split(":", 1)[1].strip()
    return ""


def drift(english_dir: Path, spanish_dir: Path) -> list[str]:
    """Every way the Spanish pages disagree with the English ones, one line per page."""
    english = {p.stem for p in english_dir.glob("*.md")}
    spanish = {p.stem for p in spanish_dir.glob("*.md")}
    failures = [f"{name}: no Spanish counterpart in docs/es/" for name in sorted(english - spanish)]
    failures += [
        f"{name}: Spanish page with no English source" for name in sorted(spanish - english)
    ]
    for name in sorted(english & spanish):
        if recorded_hash(spanish_dir / f"{name}.md") != source_hash(english_dir / f"{name}.md"):
            failures.append(
                f"{name}: English page changed since the translation was reviewed "
                f"(update docs/es/{name}.md, then --stamp {name})"
            )
    # Agreement means pages were compared, not that there was nothing to compare.
    if not english & spanish:
        failures.append("no page compared: docs/ and docs/es/ share no page")
    return failures


def stamp(english: Path, spanish: Path) -> None:
    """Records in the Spanish page that it was reviewed against the current English text."""
    field = f"source_sha256: {source_hash(english)}"
    text = spanish.read_text(encoding="utf-8")
    lines = text.splitlines()
    if lines and lines[0] == "---" and "---" in lines[1:]:
        end = lines.index("---", 1)
        kept = [line for line in lines[1:end] if not line.startswith("source_sha256:")]
        lines = ["---", field, *kept, *lines[end:]]
    else:
        lines = ["---", field, "---", *lines]
    spanish.write_text("\n".join(lines) + ("\n" if text.endswith("\n") else ""), encoding="utf-8")


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
        self.links: list[str] = []
        self.hreflang: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k: v or "" for k, v in attrs}
        if tag == "title":
            self.title = True
        elif tag == "meta":
            self.meta.add(a.get("name") or a.get("property") or "")
        elif tag == "a" and a.get("href"):
            self.links.append(a["href"])
        elif tag == "link" and a.get("rel") == "alternate" and a.get("hreflang"):
            self.hreflang[a["hreflang"]] = a.get("href", "")
        attr = LOADING_TAGS.get(tag)
        if attr and a.get(attr):
            if tag == "link" and not LOADING_RELS & set(a.get("rel", "").split()):
                return
            self.loads.append(a[attr])


def is_remote(url: str, own_host: str) -> bool:
    host = urlsplit(url.strip("'\" ")).netloc
    return bool(host) and host != own_host


def site_path(url: str) -> Path:
    """The file in the built site that serves an own-host URL."""
    path = urlsplit(url).path.lstrip("/")
    return SITE / path / "index.html" if path == "" or path.endswith("/") else SITE / path


def check_site() -> int:
    """Fails the build on a page missing its metadata, a broken own-host link, a translated page
    not declaring its counterpart, or any resource from another host."""
    site_url = ""
    for line in (ROOT / "mkdocs.yml").read_text(encoding="utf-8").splitlines():
        if line.startswith("site_url:"):
            site_url = line.split(":", 1)[1].strip()
    own_host = urlsplit(site_url).netloc

    failures: list[str] = []
    robots = SITE / "robots.txt"
    if not robots.is_file():
        failures.append("robots.txt: missing from the site root")
    else:
        text = robots.read_text(encoding="utf-8")
        for sitemap in (f"{site_url}sitemap.xml", f"{site_url}es/sitemap.xml"):
            if f"Sitemap: {sitemap}" not in text:
                failures.append(f"robots.txt: does not list {sitemap}")
            elif not site_path(sitemap).is_file():
                failures.append(f"robots.txt: lists {sitemap}, which the build did not write")

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
        if page.name != "404.html":
            for key in REQUIRED_META:
                if key not in scan.meta:
                    failures.append(f"{name}: no {key}")
        for url in scan.loads:
            if is_remote(url, own_host):
                failures.append(f"{name}: loads {url} from another host")
        # Links to the other language are absolute, so MkDocs cannot validate them.
        for url in scan.links:
            if urlsplit(url).netloc == own_host and not site_path(url).is_file():
                failures.append(f"{name}: links to {url}, which the site does not have")
        # A page and its counterpart in the other language name each other.
        spanish = name.startswith("es/")
        counterpart = name.removeprefix("es/") if spanish else f"es/{name}"
        other_lang = "en" if spanish else "es"
        if page.name != "404.html" and (SITE / counterpart).is_file():
            expected = site_url + counterpart.removesuffix("index.html")
            if scan.hreflang.get(other_lang) != expected:
                failures.append(
                    f"{name}: does not declare {expected} as its {other_lang} alternate"
                )

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
    parser.add_argument(
        "--stamp",
        metavar="PAGE",
        help="record that docs/es/PAGE.md was reviewed against the current docs/PAGE.md",
    )
    args = parser.parse_args()

    if args.stamp:
        english, spanish = DOCS / f"{args.stamp}.md", ES_DOCS / f"{args.stamp}.md"
        if not english.is_file() or not spanish.is_file():
            print(
                f"error: {args.stamp} needs both docs/{args.stamp}.md and docs/es/{args.stamp}.md",
                file=sys.stderr,
            )
            return 2
        stamp(english, spanish)
        print(f"docs: docs/es/{args.stamp}.md stamped against the current English text")
        return 0

    failures = drift(DOCS, ES_DOCS)
    if failures:
        print(
            f"docs: the Spanish pages drifted from the English ones ({len(failures)}):",
            file=sys.stderr,
        )
        for failure in failures:
            print(f"  {failure}", file=sys.stderr)
        return 1

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
    if args.serve:
        commands = [["mkdocs", "serve", "--strict"]]
    else:
        # English first: it cleans site/, and the Spanish build then writes site/es/.
        commands = [
            ["mkdocs", "build", "--strict"],
            ["mkdocs", "build", "--strict", "-f", "mkdocs.es.yml"],
        ]
    for command in commands:
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
