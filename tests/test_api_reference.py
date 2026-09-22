"""Holds `docs/api.md` to the surface the application actually serves.

The comparison is a set in both directions, so an undocumented endpoint fails and so does
an entry left behind after a route is removed. Skipped where the tree is stripped: the
Docker `test` stage has no `docs/` to read.
"""

import os
import re

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REFERENCE = os.path.join(ROOT, "docs", "api.md")

needs_docs = pytest.mark.skipif(
    not os.path.exists(REFERENCE),
    reason="stripped tree: docs/api.md does not reach the test stage",
)

# One operation per line, method first. A `# group` heading groups for the reader and the parser
# ignores it: the block has to serve both without becoming two sources of truth.
ENTRY_RE = re.compile(r"^(GET|POST|PUT|PATCH|DELETE)\s+(/\S*)$")

# If the block stopped parsing, the documented set would come out empty and the comparison would
# fail for being empty rather than for being incomplete. The minimum says something plausible
# was read.
MIN_ENTRIES = 50


def _documented() -> set[tuple[str, str]]:
    """Entries from the fenced blocks that carry no language.

    Scanned line by line: one expression over the whole text can pair a block's *closing*
    fence with the next block's opening one and capture the prose in between.
    """
    entries: set[tuple[str, str]] = set()
    in_block = False
    collecting = False
    for raw in open(REFERENCE, encoding="utf-8"):
        line = raw.rstrip("\n")
        if line.startswith("```"):
            if in_block:
                in_block, collecting = False, False
            else:
                # A fence toggles whatever its language; only language-less blocks carry
                # endpoints. Without separating the two, the close of a `bash` block is
                # indistinguishable from the open of a bare one.
                in_block, collecting = True, line.strip() == "```"
            continue
        if not collecting:
            continue
        match = ENTRY_RE.match(line.strip())
        if match:
            entries.add((match.group(1), match.group(2)))
    return entries


def _served() -> set[tuple[str, str]]:
    from app.main import app

    return {
        (method.upper(), path)
        for path, methods in app.openapi()["paths"].items()
        for method in methods
    }


@needs_docs
def test_the_reference_examined_a_plausible_number_of_entries():
    documented = _documented()
    assert len(documented) >= MIN_ENTRIES, (
        f"only parsed {len(documented)} entries out of docs/api.md; "
        "did the fenced block's format change?"
    )


@needs_docs
def test_every_served_operation_is_documented(main_module):
    missing = sorted(_served() - _documented())
    assert not missing, (
        "operations the application serves with no entry in docs/api.md: "
        + ", ".join(f"{m} {p}" for m, p in missing)
    )


@needs_docs
def test_every_documented_operation_is_served(main_module):
    extra = sorted(_documented() - _served())
    assert not extra, "entries in docs/api.md the application does not serve: " + ", ".join(
        f"{m} {p}" for m, p in extra
    )


def test_the_schema_declares_the_running_version(main_module):
    """FastAPI's default is 0.1.0, and a reference announcing a version the server never
    reports leaves the reader unable to tell which number is the software."""
    from app.version import VERSION

    declared = main_module.app.openapi()["info"]["version"]
    assert declared == VERSION, (
        f"the OpenAPI document declares {declared}, app.version is {VERSION}"
    )


def test_every_operation_carries_a_tag(main_module):
    """Without tags the reference is a flat list of every operation the application serves."""
    untagged = [
        f"{method.upper()} {path}"
        for path, methods in main_module.app.openapi()["paths"].items()
        for method, operation in methods.items()
        if not operation.get("tags")
    ]
    assert not untagged, "operations with no tag: " + ", ".join(untagged)
