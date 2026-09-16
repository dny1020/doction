#!/usr/bin/env python3
"""Fails when the licence is not declared identically everywhere it is declared.

    uv run python -m scripts.check_license
    uv run python -m scripts.check_license --repo dny1020/doction

The licence lives in seven places and nobody remembers all seven; the published repository
description said "MIT licensed" for two releases after MIT was replaced. `pyproject.toml` is
the single authored source and everything else must agree with it.

The repository description is the one declaration a commit cannot reach, so it is checked
over the network. With no route out that half prints a SKIP as loudly as a failure — a
silent skip would reproduce the very failure this exists to catch.
"""

import argparse
import json
import re
import subprocess
import sys
import tomllib
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# The title line each licence text opens with. Checking the title rather than a hash lets a
# licence be updated to a newer FSF revision of the same licence without editing this table.
LICENSE_TITLES = {
    "AGPL-3.0-only": "GNU AFFERO GENERAL PUBLIC LICENSE",
    "GPL-3.0-only": "GNU GENERAL PUBLIC LICENSE",
    "MIT": "MIT License",
    "Apache-2.0": "Apache License",
}

# Tokens that name a licence in prose. Used only against the repository description, which is
# one sentence: a stale name there is the bug. They are deliberately NOT used against the
# README, which legitimately names MIT, BSD and Apache when listing dependency licences.
LICENSE_TOKENS = ("AGPL", "GPL", "LGPL", "MIT", "Apache", "BSD", "MPL", "ISC")


def declared_license() -> str:
    with (ROOT / "pyproject.toml").open("rb") as f:
        return tomllib.load(f)["project"]["license"]


def badge_form(spdx: str) -> str:
    """shields.io escapes a literal hyphen by doubling it."""
    return spdx.replace("-", "--")


def check_files(spdx: str) -> list[str]:
    failures = []

    title = LICENSE_TITLES.get(spdx)
    if title is None:
        failures.append(
            f"LICENSE: no known title for {spdx}; add it to LICENSE_TITLES in this script"
        )
    else:
        first = (ROOT / "LICENSE").read_text(encoding="utf-8").strip().splitlines()[0].strip()
        if first != title:
            failures.append(f"LICENSE: opens with {first!r}, expected {title!r} for {spdx}")

    pkg = json.loads((ROOT / "frontend/package.json").read_text(encoding="utf-8"))
    if pkg.get("license") != spdx:
        failures.append(
            f"frontend/package.json: license is {pkg.get('license')!r}, expected {spdx!r}"
        )

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    if badge_form(spdx) not in readme:
        failures.append(f"README.md: no badge for {spdx} (expected {badge_form(spdx)!r})")
    section = readme.partition("## License")[2]
    if not section:
        failures.append("README.md: no '## License' section")
    elif spdx not in section:
        failures.append(f"README.md: the '## License' section does not name {spdx}")

    contributing = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    if spdx not in contributing:
        failures.append(f"CONTRIBUTING.md: does not name {spdx}")

    return failures


def repo_slug(explicit: str | None) -> str | None:
    if explicit:
        return explicit
    try:
        url = subprocess.run(
            ["git", "remote", "get-url", "github"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=ROOT,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    m = re.search(r"[:/]([^/:]+/[^/]+?)(?:\.git)?$", url)
    return m.group(1) if m else None


def check_description(spdx: str, slug: str | None) -> tuple[list[str], str | None]:
    """Returns (failures, skip_reason). A skip is not a failure but must be visible."""
    if slug is None:
        return [], "no github remote, so there is no repository description to check"

    try:
        req = urllib.request.Request(
            f"https://api.github.com/repos/{slug}",
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "doction-license-check",
            },
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            description = json.loads(r.read()).get("description") or ""
    except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError) as exc:
        return (
            [],
            f"could not reach the GitHub API ({exc.__class__.__name__}), description unverified",
        )

    family = spdx.split("-")[0]
    stale = [
        tok
        for tok in LICENSE_TOKENS
        if tok in description and tok != family and not (tok == "GPL" and family == "AGPL")
    ]
    if stale:
        return [
            f"repository description names {', '.join(stale)} but the licence is {spdx}: "
            f"{description!r}"
        ], None
    return [], None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", help="owner/name; defaults to the `github` git remote")
    args = parser.parse_args()

    try:
        spdx = declared_license()
    except (OSError, KeyError, tomllib.TOMLDecodeError) as exc:
        print(f"error: no license declared in pyproject.toml ({exc})", file=sys.stderr)
        return 2

    failures = check_files(spdx)
    desc_failures, skip = check_description(spdx, repo_slug(args.repo))
    failures += desc_failures

    if skip:
        print(f"license: SKIPPED one check — {skip}")
    if failures:
        print(f"license: {spdx} is not declared consistently:\n", file=sys.stderr)
        for f in failures:
            print(f"  {f}", file=sys.stderr)
        return 1

    print(f"license: {spdx}, declared consistently everywhere")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
