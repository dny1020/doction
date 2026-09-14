"""Tests for the check that tracked documentation reaches only tracked files.

The failure it guards against is specific to this repository: `CLAUDE.md` and `.claude/` are
gitignored on purpose, so a versioned document citing them dead-ends for everyone but the
maintainer. The same applies to a link written before its target exists.

Skipped where the tree is stripped. The Docker `test` stage copies only `app/`, `tests/`,
`scripts/` and `pyproject.toml`, so there is no git index and no markdown to compare — a
lesson from the previous two changes, where tests like these turned `main` red twice.
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
    """Un check que no encuentra referencias pasaría por vacío, no por correcto."""
    r = _run()
    count = int(r.stdout.split("docs: ")[1].split()[0])
    assert count > 20, f"solo examinó {count} referencias; ¿dejó de encontrarlas?"


@needs_checkout
def test_catches_a_reference_to_a_gitignored_file(tmp_path):
    """El caso que motiva el check: citar CLAUDE.md, que existe pero no viaja."""
    doc = ROOT / "AGENTS.md"
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
    doc = ROOT / "AGENTS.md"
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
    """El gate tiene que pasar sin salida a internet, así que no se validan URLs."""
    doc = ROOT / "AGENTS.md"
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
    """Sin índice de git no hay nada contra lo que comparar; eso es un skip, no un fallo."""
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts/__init__.py").touch()
    (tmp_path / "scripts/check_docs_reachable.py").write_text(
        (ROOT / "scripts/check_docs_reachable.py").read_text(encoding="utf-8"), encoding="utf-8"
    )
    r = _run(cwd=tmp_path)
    assert r.returncode == 0
    assert "SKIPPED" in r.stdout
