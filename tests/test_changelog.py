"""Tests for the changelog parser that produces release notes.

The parser is the only thing that knows the heading format, and both the gate and the
release workflow depend on it. The case worth guarding hardest is the range heading: the
changelog was reconstructed in bulk at 0.31.3, so sections like `## 0.28.0 – 0.30.0`
describe three versions at once. Matching one of those for a single version would give a
release notes about versions it has nothing to do with.

Unlike the licence tests, these do not need a tree: the parser reads CHANGELOG.md, which is
present wherever pytest runs, and the temporary cases write their own file.
"""

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _run(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "scripts.changelog", *args],
        cwd=cwd or ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_prints_the_section_for_a_described_version():
    r = _run("0.31.5")
    assert r.returncode == 0, r.stderr
    assert "AGPL-3.0-only" in r.stdout
    # Debe parar en el siguiente encabezado, no arrastrar la versión anterior.
    assert "## 0.31.4" not in r.stdout


def test_accepts_a_tag_prefix():
    assert _run("v0.31.5").stdout == _run("0.31.5").stdout


def test_fails_for_a_version_with_no_section():
    r = _run("9.9.9")
    assert r.returncode == 1
    assert "9.9.9" in r.stderr


def test_does_not_match_a_version_inside_a_range_heading():
    """`## 0.28.0 – 0.30.0` describes three versions; it is nobody's release notes."""
    r = _run("0.29.0")
    assert r.returncode == 1, f"0.29.0 matched a range heading:\n{r.stdout}"


def test_does_not_match_a_version_prefix():
    """`0.31` must not pick up `## 0.31.5`."""
    assert _run("0.31").returncode == 1


def test_skips_the_unreleased_section():
    r = _run("Unreleased")
    # `Unreleased` no es una versión; que case o no, nunca debe salir como notas de una.
    if r.returncode == 0:
        assert "Nothing yet" in r.stdout or not r.stdout.strip()


def test_check_mode_uses_the_declared_version():
    r = _run("--check")
    assert r.returncode == 0, r.stderr
    assert "is described" in r.stdout


@pytest.mark.parametrize(
    ("heading", "version", "expected_exit"),
    [
        ("## 1.2.3 — 2026-01-01", "1.2.3", 0),
        ("## 1.2.3", "1.2.3", 0),
        ("## 1.2.0 – 1.4.0 — 2026-01-01", "1.3.0", 1),
        ("## 1.2.30", "1.2.3", 1),
    ],
)
def test_heading_forms(tmp_path, heading, version, expected_exit):
    """The heading may or may not carry a date, and must not match by prefix or range."""
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts/__init__.py").touch()
    (tmp_path / "scripts/changelog.py").write_text(
        (ROOT / "scripts/changelog.py").read_text(encoding="utf-8"), encoding="utf-8"
    )
    (tmp_path / "pyproject.toml").write_text('[project]\nversion = "1.2.3"\n', encoding="utf-8")
    (tmp_path / "CHANGELOG.md").write_text(
        f"# Changelog\n\n## Unreleased\n\nNothing yet.\n\n{heading}\n\n- did a thing\n",
        encoding="utf-8",
    )

    assert _run(version, cwd=tmp_path).returncode == expected_exit
