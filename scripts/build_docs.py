#!/usr/bin/env python3
"""Builds the documentation site, strictly, from the tracked documentation.

Links inside `docs/` point above it, at the README, `CONTRIBUTING.md` and the rest. MkDocs
cannot reach outside its `docs_dir`, and rewriting those links to github.com would make the build
pass by removing them from `scripts/check_docs_reachable.py` — trading one check for the other
instead of satisfying both.

The staged set is larger than the links out of `docs/` alone, because once a root document is in
the site its own links have to resolve too: the README reaches `ROADMAP.md`, `AGENTS.md`,
`openspec/README.md` and `LICENSE`, and `CONTRIBUTING.md` adds `CODE_OF_CONDUCT.md`. The strict
build is what found each of them.

So the build stages a tree: the root documents at its top, `docs/` underneath, which is exactly
the shape the relative links already assume. The staged copies are build output, never committed,
so there is still one copy of each document in the repository.

    uv run --group docs python -m scripts.build_docs          # build into site/
    uv run --group docs python -m scripts.build_docs --serve   # local preview

`--strict` is always on: a link that does not resolve fails the build rather than publishing.
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STAGE = ROOT / "build" / "docs"
SITE = ROOT / "site"

# Documents outside `docs/` that the site needs, each because something in the site links to it.
# Paths are repository-relative and keep their shape in the staged tree, so `openspec/README.md`
# is staged at `openspec/README.md` and the links to it resolve unchanged.
ROOT_DOCS = [
    "README.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "DESIGN.md",
    "CHANGELOG.md",
    "ROADMAP.md",
    "AGENTS.md",
    "CODE_OF_CONDUCT.md",
    "openspec/README.md",
    # Sin extensión, así que MkDocs lo trata como archivo estático y el enlace resuelve igual.
    "LICENSE",
]


def stage() -> None:
    if STAGE.exists():
        shutil.rmtree(STAGE)
    STAGE.mkdir(parents=True)
    shutil.copytree(ROOT / "docs", STAGE / "docs")
    for name in ROOT_DOCS:
        source = ROOT / name
        if not source.exists():
            print(f"error: {name} is missing; the site expects it", file=sys.stderr)
            raise SystemExit(2)
        target = STAGE / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


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
    if not args.serve:
        print(f"docs: site built into {SITE.relative_to(ROOT)}/, strict mode, no broken links")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
