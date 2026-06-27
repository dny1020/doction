"""Versionado de páginas con git — silencioso, nunca bloquea un guardado."""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path

from app.models import HistoryEntry

logger = logging.getLogger(__name__)


def _pages_dir() -> Path:
    from app.db import db_path
    return db_path().parent / "pages"


def ensure_repo() -> None:
    pages = _pages_dir()
    pages.mkdir(parents=True, exist_ok=True)
    if (pages / ".git").exists():
        return
    result = subprocess.run(["git", "init", str(pages)], capture_output=True, text=True)
    if result.returncode != 0:
        logger.warning("git init failed: %s", result.stderr)
        return
    subprocess.run(
        ["git", "-C", str(pages), "config", "user.email", "doction@localhost"], capture_output=True
    )
    subprocess.run(
        ["git", "-C", str(pages), "config", "user.name", "doction"], capture_output=True
    )


def commit_page(
    ws_slug: str, page_slug: str, content: str, author: str, message: str
) -> str | None:
    pages = _pages_dir()
    ws_dir = pages / ws_slug
    try:
        ws_dir.mkdir(parents=True, exist_ok=True)
        md_file = ws_dir / f"{page_slug}.md"
        md_file.write_text(content, encoding="utf-8")
    except OSError as exc:
        logger.warning("git: could not write page file: %s", exc)
        return None

    rel_path = f"{ws_slug}/{page_slug}.md"

    result = subprocess.run(
        ["git", "-C", str(pages), "add", rel_path],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        logger.warning("git add failed: %s", result.stderr)
        return None

    # Sin cambios staged → devuelve el último SHA conocido del archivo.
    diff = subprocess.run(
        ["git", "-C", str(pages), "diff", "--cached", "--quiet"],
        capture_output=True,
    )
    if diff.returncode == 0:
        last = subprocess.run(
            ["git", "-C", str(pages), "log", "-1", "--format=%h", "--", rel_path],
            capture_output=True, text=True,
        )
        return last.stdout.strip() or None

    env = os.environ.copy()
    env.setdefault("GIT_COMMITTER_NAME", "doction")
    env.setdefault("GIT_COMMITTER_EMAIL", "doction@localhost")

    result = subprocess.run(
        ["git", "-C", str(pages), "commit", "-m", message,
         f"--author={author} <{author}>"],
        capture_output=True, text=True, env=env,
    )
    if result.returncode != 0:
        logger.warning("git commit failed: %s", result.stderr)
        return None

    sha = subprocess.run(
        ["git", "-C", str(pages), "log", "-1", "--format=%h"],
        capture_output=True, text=True,
    )
    return sha.stdout.strip() or None


def get_page_history(ws_slug: str, page_slug: str, limit: int = 50) -> list[HistoryEntry]:
    pages = _pages_dir()
    if not (pages / ".git").exists():
        return []
    rel_path = f"{ws_slug}/{page_slug}.md"
    result = subprocess.run(
        ["git", "-C", str(pages), "log", f"--max-count={limit}",
         "--follow", "--format=%H|%ai|%an|%s", "--", rel_path],
        capture_output=True, text=True,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return []
    history = []
    for line in result.stdout.strip().splitlines():
        parts = line.split("|", 3)
        if len(parts) == 4:
            history.append(
                HistoryEntry(
                    sha=parts[0][:7],
                    timestamp=parts[1],
                    author=parts[2],
                    message=parts[3],
                )
            )
    return history


def get_page_at_commit(ws_slug: str, page_slug: str, sha: str) -> str | None:
    pages = _pages_dir()
    if not (pages / ".git").exists():
        return None
    rel_path = f"{ws_slug}/{page_slug}.md"
    result = subprocess.run(
        ["git", "-C", str(pages), "show", f"{sha}:{rel_path}"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout


def diff_page(ws_slug: str, page_slug: str, sha: str) -> str | None:
    """Diff unificado que introdujo `sha` en la página. `git show` maneja el commit raíz."""
    pages = _pages_dir()
    if not (pages / ".git").exists():
        return None
    rel_path = f"{ws_slug}/{page_slug}.md"
    result = subprocess.run(
        ["git", "-C", str(pages), "show", "--format=", "--no-color", sha, "--", rel_path],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout
