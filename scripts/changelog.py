#!/usr/bin/env python3
"""Prints a version's CHANGELOG.md section, or fails when it has none.

    uv run python -m scripts.changelog 0.31.5      # prints the section
    uv run python -m scripts.changelog --check     # gate: the declared version has one

Shared by the gate and the release workflow. Range headings (`## 0.28.0 – 0.30.0`) match
no single version.
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

    The version must be followed by a boundary, so `0.31` never matches `## 0.31.5`.
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

    # `parser.error()` exits, but a static analyser cannot know that and sees `version`
    # as possibly unassigned; the `return` makes it explicit.
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

    if version.lower() == "unreleased":
        print("changelog: Unreleased is not a version; it has no release notes", file=sys.stderr)
        return 1

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
