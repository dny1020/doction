#!/usr/bin/env python3
"""Fails when a commit does not certify the terms it was contributed under.

    uv run python -m scripts.check_signoff origin/main..HEAD
    uv run python -m scripts.check_signoff            # defaults to the range CI provides

A `Signed-off-by` trailer keeps the record on the commit itself.
"""

import argparse
import os
import re
import subprocess
import sys

TRAILER_RE = re.compile(r"^Signed-off-by:\s*(.+?)\s*<([^>]+)>\s*$", re.M | re.I)

REMEDY = """
  How to fix it:

    git commit --amend -s --no-edit     # the most recent commit
    git rebase --signoff <base>         # every commit in the branch
    git push --force-with-lease

  `-s` adds a Signed-off-by trailer with your git name and email. It certifies that you
  wrote the change or have the right to submit it, and that you offer it under the
  project's licence (AGPL-3.0-only). It transfers no copyright.
"""


def commit_range() -> str:
    base = os.environ.get("GITHUB_BASE_REF")
    if base:
        return f"origin/{base}..HEAD"
    return "origin/main..HEAD"


def commits(rng: str) -> list[tuple[str, str, str]]:
    """(sha, subject, author email) for each commit in the range."""
    out = subprocess.run(
        ["git", "log", "--no-merges", "--format=%H%x1f%s%x1f%ae%x1e", rng],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if out.returncode != 0:
        print(f"error: cannot read {rng}: {out.stderr.strip()}", file=sys.stderr)
        raise SystemExit(2)
    rows = []
    for rec in out.stdout.split("\x1e"):
        rec = rec.strip("\n")
        if rec:
            rows.append(tuple(rec.split("\x1f")))  # type: ignore[arg-type]
    return rows


def body(sha: str) -> str:
    return subprocess.run(
        ["git", "log", "-1", "--format=%B", sha], capture_output=True, text=True, timeout=30
    ).stdout


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("range", nargs="?", help="commit range; defaults to the PR base")
    args = parser.parse_args()

    rng = args.range or commit_range()
    rows = commits(rng)
    if not rows:
        print(f"signoff: no commits in {rng}, nothing to certify")
        return 0

    failures = []
    for sha, subject, email in rows:
        trailers = TRAILER_RE.findall(body(sha))
        if not trailers:
            failures.append(f"{sha[:8]} {subject[:60]} — no Signed-off-by")
            continue
        # The sign-off has to be the author's: someone else's certifies nothing about them.
        if not any(e.strip().lower() == email.strip().lower() for _, e in trailers):
            signed = ", ".join(e for _, e in trailers)
            failures.append(f"{sha[:8]} {subject[:50]} — signed by {signed}, authored by {email}")

    if failures:
        print(
            f"signoff: {len(failures)} of {len(rows)} commit(s) not certified:\n", file=sys.stderr
        )
        for f in failures:
            print(f"  {f}", file=sys.stderr)
        print(REMEDY, file=sys.stderr)
        return 1

    print(f"signoff: {len(rows)} commit(s) certified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
