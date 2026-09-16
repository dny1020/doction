"""Page versioning with git: silent, and never blocks a save."""

import logging
import os
import re
import subprocess
from pathlib import Path

from app.models import HistoryEntry

logger = logging.getLogger(__name__)

# SHAs come from the URL, so hex only — never something starting with `-` that
# `git show` would read as an option.
_SHA_RE = re.compile(r"[0-9a-fA-F]{4,64}")


def _pages_dir() -> Path:
    from app.db import data_dir

    return data_dir() / "pages"


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
    subprocess.run(["git", "-C", str(pages), "config", "user.name", "doction"], capture_output=True)


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
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        logger.warning("git add failed: %s", result.stderr)
        return None

    # Nothing staged: return the file's last known SHA.
    diff = subprocess.run(
        ["git", "-C", str(pages), "diff", "--cached", "--quiet"],
        capture_output=True,
    )
    if diff.returncode == 0:
        last = subprocess.run(
            ["git", "-C", str(pages), "log", "-1", "--format=%h", "--", rel_path],
            capture_output=True,
            text=True,
        )
        return last.stdout.strip() or None

    env = os.environ.copy()
    env.setdefault("GIT_COMMITTER_NAME", "doction")
    env.setdefault("GIT_COMMITTER_EMAIL", "doction@localhost")

    result = subprocess.run(
        ["git", "-C", str(pages), "commit", "-m", message, f"--author={author} <{author}>"],
        capture_output=True,
        text=True,
        env=env,
    )
    if result.returncode != 0:
        logger.warning("git commit failed: %s", result.stderr)
        return None

    sha = subprocess.run(
        ["git", "-C", str(pages), "log", "-1", "--format=%h"],
        capture_output=True,
        text=True,
    )
    return sha.stdout.strip() or None


def rename_page_file(ws_slug: str, old_slug: str, new_slug: str, author: str) -> str | None:
    """`git mv` the .md and commit; None if anything fails.

    A git failure never breaks the operation: the rename already happened in Postgres,
    which is the source of truth.
    """
    pages = _pages_dir()
    old_rel = f"{ws_slug}/{old_slug}.md"
    new_rel = f"{ws_slug}/{new_slug}.md"
    if not (pages / old_rel).exists():
        logger.warning("git: %s does not exist, nothing to rename", old_rel)
        return None

    moved = subprocess.run(
        ["git", "-C", str(pages), "mv", old_rel, new_rel],
        capture_output=True,
        text=True,
    )
    if moved.returncode != 0:
        logger.warning("git mv failed: %s", moved.stderr)
        return None

    env = os.environ.copy()
    env.setdefault("GIT_COMMITTER_NAME", "doction")
    env.setdefault("GIT_COMMITTER_EMAIL", "doction@localhost")
    done = subprocess.run(
        [
            "git",
            "-C",
            str(pages),
            "commit",
            f"--author={author} <{author}>",
            "-m",
            f"Rename: {old_slug} -> {new_slug}",
        ],
        capture_output=True,
        text=True,
        env=env,
    )
    if done.returncode != 0:
        logger.warning("git commit failed after rename: %s", done.stderr)
        return None

    last = subprocess.run(
        ["git", "-C", str(pages), "log", "-1", "--format=%h"],
        capture_output=True,
        text=True,
    )
    return last.stdout.strip() or None


def commit_and_record(
    workspace_id: int,
    ws_slug: str,
    page_slug: str,
    title: str,
    content: str,
    author: str,
) -> None:
    """Commit the save and store the resulting SHA on the page.

    The one point REST and MCP share.
    """
    from app import db

    sha = commit_page(ws_slug, page_slug, content, author, f"Save: {title}")
    if sha:
        db.set_page_git_commit(workspace_id, page_slug, sha)


def get_page_history(ws_slug: str, page_slug: str, limit: int = 50) -> list[HistoryEntry]:
    pages = _pages_dir()
    if not (pages / ".git").exists():
        return []
    rel_path = f"{ws_slug}/{page_slug}.md"
    result = subprocess.run(
        [
            "git",
            "-C",
            str(pages),
            "log",
            f"--max-count={limit}",
            "--follow",
            "--format=%H|%ai|%an|%s",
            "--",
            rel_path,
        ],
        capture_output=True,
        text=True,
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
    if not _SHA_RE.fullmatch(sha) or not (pages / ".git").exists():
        return None
    rel_path = f"{ws_slug}/{page_slug}.md"
    result = subprocess.run(
        ["git", "-C", str(pages), "show", f"{sha}:{rel_path}"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout


def diff_page(ws_slug: str, page_slug: str, sha: str) -> str | None:
    """The unified diff `sha` introduced; `git show` handles the root commit."""
    pages = _pages_dir()
    if not _SHA_RE.fullmatch(sha) or not (pages / ".git").exists():
        return None
    rel_path = f"{ws_slug}/{page_slug}.md"
    result = subprocess.run(
        ["git", "-C", str(pages), "show", "--format=", "--no-color", sha, "--", rel_path],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout
