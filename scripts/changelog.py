#!/usr/bin/env python3
"""Prints a version's CHANGELOG.md section, or fails when it has none.

One parser, two callers. `make changelog` runs it against the version declared in
pyproject.toml and throws the output away, so a version bump cannot be merged without its
entry. The release workflow runs it against a pushed tag and uses the output as the release
notes. A separate "does an entry exist" check would be a second implementation of the same
heading rule, and the two would eventually disagree about the format.

    uv run python -m scripts.changelog 0.31.5      # prints the section
    uv run python -m scripts.changelog --check     # gate: the declared version has one

Range headings such as `## 0.28.0 – 0.30.0` are deliberately not a match for any single
version. They describe history that was reconstructed in bulk, and matching one would give
a new release notes about three old versions.
"""

import argparse
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHANGELOG = ROOT / "CHANGELOG.md"


def declared_version() -> str:
    with (ROOT / "pyproject.toml").open("rb") as f:
        return tomllib.load(f)["project"]["version"]


def section(version: str) -> str | None:
    """The body under `## <version>`, up to the next `## ` heading.

    The heading may carry a date (`## 0.31.5 — 2026-09-12`), so the version has to be
    followed by a boundary rather than the end of the line. Requiring that boundary is also
    what stops `0.31` from matching `## 0.31.5`.
    """
    try:
        lines = CHANGELOG.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None

    head = re.compile(rf"^## {re.escape(version)}(?:\s|$)")
    body: list[str] = []
    inside = False
    for line in lines:
        if inside:
            if line.startswith("## "):
                break
            body.append(line)
        elif head.match(line):
            inside = True

    if not inside:
        return None
    return "\n".join(body).strip() or None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("version", nargs="?", help="e.g. 0.31.5, or a tag like v0.31.5")
    parser.add_argument(
        "--check",
        action="store_true",
        help="the version in pyproject.toml; confirm instead of printing the section",
    )
    args = parser.parse_args()

    # `parser.error()` sale del proceso, pero un análisis estático no lo sabe y ve
    # `version` posiblemente sin asignar. El `return` lo hace explícito, y el mensaje
    # nombra `--check`: decía `--declared`, una bandera que dejó de existir al renombrarla.
    if args.check:
        try:
            version = declared_version()
        except (OSError, KeyError, tomllib.TOMLDecodeError) as exc:
            print(f"error: no version declared in pyproject.toml ({exc})", file=sys.stderr)
            return 2
    elif args.version:
        version = args.version.removeprefix("v")
    else:
        print("error: give a version or --check", file=sys.stderr)
        return 2

    body = section(version)
    if body is None:
        print(
            f"changelog: {version} has no section in CHANGELOG.md.\n"
            f"  Add a '## {version}' heading describing what changed. A version nobody\n"
            f"  described is a release nobody can read, and the release notes are taken\n"
            f"  from this file rather than written again elsewhere.",
            file=sys.stderr,
        )
        return 1

    if args.check:
        print(f"changelog: {version} is described")
    else:
        print(body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
