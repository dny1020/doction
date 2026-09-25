"""Tests for the check that tracked documentation reaches only tracked files.

`CLAUDE.md` and `.claude/` are gitignored on purpose, so a versioned document citing them
dead-ends for everyone but the maintainer. Skipped where the tree is stripped: the Docker
`test` stage has no git index and no markdown to compare.
"""

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

needs_checkout = pytest.mark.skipif(
    not (ROOT / ".git").exists() or not (ROOT / "README.md").exists(),
    reason="árbol recortado: sin índice de git o sin documentación que comparar",
)


def _run(cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "scripts.check_docs_reachable"],
        cwd=cwd or ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )


@needs_checkout
def test_passes_on_the_real_tree():
    r = _run()
    assert r.returncode == 0, r.stdout + r.stderr
    assert "all reachable" in r.stdout


@needs_checkout
def test_it_actually_examined_something():
    """A check that finds no references would pass for being empty, not for being right."""
    r = _run()
    count = int(r.stdout.split("docs: ")[1].split()[0])
    assert count > 20, f"solo examinó {count} referencias; ¿dejó de encontrarlas?"


@needs_checkout
def test_catches_a_reference_to_a_gitignored_file(tmp_path):
    """The motivating case: citing CLAUDE.md, which exists but does not ship."""
    doc = ROOT / "CONTRIBUTING.md"
    original = doc.read_text(encoding="utf-8")
    try:
        doc.write_text(original + "\nSee [the notes](CLAUDE.md).\n", encoding="utf-8")
        r = _run()
        assert r.returncode == 1
        assert "CLAUDE.md" in r.stderr
        assert "untracked" in r.stderr
    finally:
        doc.write_text(original, encoding="utf-8")


@needs_checkout
def test_catches_a_reference_to_a_file_that_does_not_exist():
    doc = ROOT / "CONTRIBUTING.md"
    original = doc.read_text(encoding="utf-8")
    try:
        doc.write_text(original + "\nSee [nothing](docs/does-not-exist.md).\n", encoding="utf-8")
        r = _run()
        assert r.returncode == 1
        assert "does not exist" in r.stderr
    finally:
        doc.write_text(original, encoding="utf-8")


@needs_checkout
def test_external_links_and_anchors_are_not_checked():
    """The gate has to pass with no route out, so URLs are not validated."""
    doc = ROOT / "CONTRIBUTING.md"
    original = doc.read_text(encoding="utf-8")
    try:
        doc.write_text(
            original
            + "\n[web](https://example.org/x) [ancla](#una-seccion) [correo](mailto:a@b.c)\n",
            encoding="utf-8",
        )
        assert _run().returncode == 0
    finally:
        doc.write_text(original, encoding="utf-8")


def test_skips_cleanly_outside_a_checkout(tmp_path):
    """With no git index there is nothing to compare against: a skip, not a failure."""
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts/__init__.py").touch()
    (tmp_path / "scripts/check_docs_reachable.py").write_text(
        (ROOT / "scripts/check_docs_reachable.py").read_text(encoding="utf-8"), encoding="utf-8"
    )
    r = _run(cwd=tmp_path)
    assert r.returncode == 0
    assert "SKIPPED" in r.stdout
