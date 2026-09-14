#!/usr/bin/env python3
"""Fails when tracked documentation points at a file a clone does not contain.

Orientation that depends on an untracked file is orientation nobody else can follow. This
project deliberately gitignores `CLAUDE.md` and `.claude/`, which is the right policy and
also the trap: a document that tells a reader to consult them dead-ends for everyone but the
maintainer. The same applies to a link written before the file it names.

    uv run python -m scripts.check_docs_reachable

Scope is narrow on purpose: markdown links to paths inside the repository. No URLs, no
anchors, no external targets — the gate has to pass on a machine with no route out, and a
network link checker fails for reasons that have nothing to do with this.
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Un enlace markdown cuyo destino parece una ruta del repositorio: sin esquema, sin
# protocolo relativo, y sin empezar por `#` (ancla dentro del mismo documento).
LINK_RE = re.compile(r"\[[^\]]*\]\(\s*(?!https?:|mailto:|#|//)([^)\s#]+)")


def tracked_files() -> set[str]:
    out = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, text=True, timeout=30
    )
    if out.returncode != 0:
        return set()
    return {p for p in out.stdout.split("\0") if p}


def tracked_markdown(tracked: set[str]) -> list[str]:
    # openspec/changes/archive queda fuera: son registros históricos, y una referencia que
    # era válida cuando se escribió no debe romper la puerta si el fichero se movió después.
    return sorted(
        p for p in tracked if p.endswith(".md") and not p.startswith("openspec/changes/archive/")
    )


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
            # Resolver relativo al documento, y normalizar sin tocar el disco.
            try:
                resolved = (base / target).resolve().relative_to(ROOT)
            except (ValueError, OSError):
                continue
            checked += 1
            rel = str(resolved)
            # Un directorio cuenta si el repositorio versiona algo dentro.
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
