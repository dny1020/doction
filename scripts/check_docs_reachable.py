#!/usr/bin/env python3
"""Fails when tracked documentation points at a file a clone does not contain.

    uv run python -m scripts.check_docs_reachable

`CLAUDE.md` and `.claude/` are gitignored. Only repository paths are checked, so the gate
works offline.
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# A markdown link whose target looks like a repository path: no scheme, not
# protocol-relative, not a `#` anchor.
LINK_RE = re.compile(r"\[[^\]]*\]\(\s*(?!https?:|mailto:|#|//)([^)\s#]+)")


def tracked_files() -> set[str]:
    out = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, text=True, timeout=30
    )
    if out.returncode != 0:
        return set()
    return {p for p in out.stdout.split("\0") if p}


def tracked_markdown(tracked: set[str]) -> list[str]:
    return sorted(p for p in tracked if p.endswith(".md"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.parse_args()

    tracked = tracked_files()
    if not tracked:
        print("docs: SKIPPED — not a git checkout, nothing to compare against")
        return 0

    failures: list[str] = []
    checked = 0
    for doc in tracked_markdown(tracked):
        text = (ROOT / doc).read_text(encoding="utf-8", errors="replace")
        base = Path(doc).parent
        for match in LINK_RE.finditer(text):
            target = match.group(1)
            # Resolve relative to the document and normalise without touching the disk.
            try:
                resolved = (base / target).resolve().relative_to(ROOT)
            except (ValueError, OSError):
                continue
            checked += 1
            rel = str(resolved)
            # A directory counts if the repository tracks something inside it.
            if rel in tracked or any(t.startswith(rel + "/") for t in tracked):
                continue
            exists = (ROOT / rel).exists()
            why = "exists but is untracked" if exists else "does not exist"
            failures.append(f"{doc} -> {target} ({rel} {why})")

    if failures:
        print(
            f"docs: {len(failures)} reference(s) point at something a clone does not have:\n",
            file=sys.stderr,
        )
        for f in failures:
            print(f"  {f}", file=sys.stderr)
        print(
            "\n  Orientation that depends on an untracked file cannot be followed by\n"
            "  anyone but the maintainer. Track the target, or drop the reference.",
            file=sys.stderr,
        )
        return 1

    docs = len(tracked_markdown(tracked))
    print(f"docs: {checked} repository reference(s) across {docs} files, all reachable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
