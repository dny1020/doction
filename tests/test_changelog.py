"""Tests for the changelog parser behind release notes.

Range headings (`## 0.28.0 – 0.30.0`) must match no single version. Two tests read the real
CHANGELOG.md and skip on a stripped tree.
"""

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

# Only for the cases that read the real CHANGELOG.md; the parametrized ones write their own
# in a temporary tree and run anywhere.
needs_real_changelog = pytest.mark.skipif(
    not (ROOT / "CHANGELOG.md").exists(),
    reason="árbol recortado: CHANGELOG.md no está presente",
)


def _run(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "scripts.changelog", *args],
        cwd=cwd or ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )


@needs_real_changelog
def test_prints_the_section_for_a_described_version():
    r = _run("0.31.5")
    assert r.returncode == 0, r.stderr
    assert "AGPL-3.0-only" in r.stdout
    # Must stop at the next heading rather than dragging in the previous version.
    assert "## 0.31.4" not in r.stdout


@needs_real_changelog
def test_accepts_a_tag_prefix():
    assert _run("v0.31.5").stdout == _run("0.31.5").stdout


@needs_real_changelog
def test_fails_for_a_version_with_no_section():
    r = _run("9.9.9")
    assert r.returncode == 1
    assert "9.9.9" in r.stderr


@needs_real_changelog
def test_does_not_match_a_version_inside_a_range_heading():
    """`## 0.28.0 – 0.30.0` describes three versions; it is nobody's release notes."""
    r = _run("0.29.0")
    assert r.returncode == 1, f"0.29.0 matched a range heading:\n{r.stdout}"


@needs_real_changelog
def test_does_not_match_a_version_prefix():
    """`0.31` must not pick up `## 0.31.5`."""
    assert _run("0.31").returncode == 1


@needs_real_changelog
def test_skips_the_unreleased_section():
    r = _run("Unreleased")
    # `Unreleased` is not a version and must never come out as one's release notes.
    if r.returncode == 0:
        assert "Nothing yet" in r.stdout or not r.stdout.strip()


@needs_real_changelog
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
