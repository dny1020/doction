"""Tests for the licence-consistency check itself.

The check exists because seven declarations of one fact drifted and nobody noticed. A check
nobody verifies is the same class of problem, so these tests break each declaration in a
temporary copy of the tree and assert the check reports the file that disagrees.

The network half (the published repository description) is not exercised here: it needs the
GitHub API, and the suite has to pass with no route out. It degrades to a visible skip, which
is asserted below.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DECLARATION_FILES = ("LICENSE", "README.md", "CONTRIBUTING.md", "pyproject.toml")


def _tree(tmp_path: Path) -> Path:
    """A copy of just the files the check reads, so a test can break one in isolation."""
    for name in DECLARATION_FILES:
        shutil.copy(ROOT / name, tmp_path / name)
    (tmp_path / "frontend").mkdir()
    shutil.copy(ROOT / "frontend/package.json", tmp_path / "frontend/package.json")
    (tmp_path / "scripts").mkdir()
    shutil.copy(ROOT / "scripts/check_license.py", tmp_path / "scripts/check_license.py")
    (tmp_path / "scripts/__init__.py").touch()
    return tmp_path


def _run(tree: Path) -> subprocess.CompletedProcess[str]:
    # --repo con un nombre inexistente evita depender de la red: la mitad remota se salta
    # y las comprobaciones de ficheros, que son lo que se prueba aquí, siguen corriendo.
    return subprocess.run(
        [sys.executable, "-m", "scripts.check_license", "--repo", "invalid/does-not-exist-404"],
        cwd=tree,
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_passes_on_the_real_tree(tmp_path):
    r = _run(_tree(tmp_path))
    assert r.returncode == 0, r.stdout + r.stderr
    assert "declared consistently" in r.stdout


def test_unreachable_api_skips_loudly_instead_of_failing(tmp_path):
    r = _run(_tree(tmp_path))
    assert r.returncode == 0
    # Un skip silencioso reproduce el fallo que el check existe para cazar.
    assert "SKIPPED" in r.stdout


def test_catches_a_disagreeing_package_json(tmp_path):
    tree = _tree(tmp_path)
    p = tree / "frontend/package.json"
    pkg = json.loads(p.read_text())
    pkg["license"] = "MIT"
    p.write_text(json.dumps(pkg, indent=2) + "\n")

    r = _run(tree)
    assert r.returncode == 1
    assert "frontend/package.json" in r.stderr


def test_catches_a_disagreeing_license_text(tmp_path):
    tree = _tree(tmp_path)
    (tree / "LICENSE").write_text("MIT License\n\nPermission is hereby granted...\n")

    r = _run(tree)
    assert r.returncode == 1
    assert "LICENSE" in r.stderr


@pytest.mark.parametrize("name", ["README.md", "CONTRIBUTING.md"])
def test_catches_a_stale_prose_declaration(tmp_path, name):
    tree = _tree(tmp_path)
    p = tree / name
    p.write_text(p.read_text().replace("AGPL-3.0-only", "GPL-3.0-only"))

    r = _run(tree)
    assert r.returncode == 1
    assert name in r.stderr


def test_reports_an_unknown_license_rather_than_passing(tmp_path):
    """A licence with no known title must fail loudly, not silently skip the LICENSE check."""
    tree = _tree(tmp_path)
    p = tree / "pyproject.toml"
    p.write_text(p.read_text().replace('license = "AGPL-3.0-only"', 'license = "WTFPL"'))

    r = _run(tree)
    assert r.returncode == 1
    assert "LICENSE_TITLES" in r.stderr
