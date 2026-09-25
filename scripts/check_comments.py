"""Fails when a comment or docstring in tracked source contains Spanish characters.

    uv run python -m scripts.check_comments

Comments are English (CONTRIBUTING.md). A character check rather than language detection:
nearly every Spanish sentence has one of these, and it needs no dependency. Quoted text
inside a comment ("ñ", `ñ`) is an example, not prose, and is ignored.
"""

import argparse
import ast
import io
import re
import subprocess
import sys
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPANISH = re.compile(r"[áéíóúñü¿¡]", re.IGNORECASE)
QUOTED = re.compile(r"\"[^\"\n]*\"|'[^'\n]*'|`[^`\n]*`")
SKIP = ("app/static/vendor/", "app/static/app/")
HASH_FILES = {"Makefile", "Dockerfile", ".env.example"}
HASH_SUFFIXES = {".yaml", ".yml", ".toml"}
C_SUFFIXES = {".js", ".jsx", ".mjs", ".css"}


def python_comments(src: str) -> list[tuple[int, str]]:
    found = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(src).readline):
            if tok.type == tokenize.COMMENT:
                found.append((tok.start[0], tok.string))
        tree = ast.parse(src)
    except (tokenize.TokenError, SyntaxError):
        return found
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            doc = ast.get_docstring(node, clean=False)
            if doc is not None:
                found.append((node.body[0].lineno, doc))
    return found


def c_comments(src: str) -> list[tuple[int, str]]:
    """`//` and `/* */` comments, skipping string, template and regex literals."""
    found = []
    i, n, prev = 0, len(src), ""
    while i < n:
        c = src[i]
        if c in "'\"`":
            i += 1
            while i < n and src[i] != c:
                i += 2 if src[i] == "\\" else 1
            i, prev = i + 1, c
            continue
        if src.startswith("//", i):
            end = src.find("\n", i)
            end = n if end < 0 else end
            found.append((src.count("\n", 0, i) + 1, src[i:end]))
            i = end
            continue
        if src.startswith("/*", i):
            end = src.find("*/", i + 2)
            end = n if end < 0 else end + 2
            found.append((src.count("\n", 0, i) + 1, src[i:end]))
            i = end
            continue
        if c == "/" and prev in "(,=:[!&|?{};":
            i += 1
            while i < n and src[i] not in "/\n":
                i += 2 if src[i] == "\\" else 1
            i += 1
            continue
        if not c.isspace():
            prev = c
        i += 1
    return found


def html_comments(src: str) -> list[tuple[int, str]]:
    found = [
        (src.count("\n", 0, m.start()) + 1, m.group(0))
        for m in re.finditer(r"<!--.*?-->|\{#.*?#\}", src, flags=re.S)
    ]
    for m in re.finditer(r"<script[^>]*>(.*?)</script>", src, flags=re.S):
        offset = src.count("\n", 0, m.start(1))
        found += [(line + offset, text) for line, text in c_comments(m.group(1))]
    return found


def hash_comments(src: str) -> list[tuple[int, str]]:
    """`#` comments outside quotes, at the start of a line or after whitespace."""
    found = []
    for number, line in enumerate(src.splitlines(), 1):
        quote = None
        for i, c in enumerate(line):
            if quote:
                quote = None if c == quote else quote
            elif c in "'\"":
                quote = c
            elif c == "#" and (i == 0 or line[i - 1].isspace()):
                found.append((number, line[i:]))
                break
    return found


def comments(path: str, src: str) -> list[tuple[int, str]]:
    name, suffix = Path(path).name, Path(path).suffix
    if suffix == ".py":
        return python_comments(src)
    if suffix in C_SUFFIXES:
        return c_comments(src)
    if suffix == ".html":
        return html_comments(src)
    if suffix in HASH_SUFFIXES or name in HASH_FILES:
        return hash_comments(src)
    return []


def findings(path: str, src: str) -> list[tuple[int, str]]:
    hits = []
    for line, text in comments(path, src):
        for offset, part in enumerate(text.splitlines()):
            if SPANISH.search(QUOTED.sub("", part)):
                hits.append((line + offset, part.strip()))
    return hits


def tracked_files() -> list[str]:
    try:
        out = subprocess.run(
            ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        sys.exit(f"comments: cannot list tracked files: {exc}")
    return [f for f in out.splitlines() if not f.startswith(SKIP)]


def main() -> int:
    argparse.ArgumentParser(description=__doc__.splitlines()[0]).parse_args()
    failed = 0
    for path in tracked_files():
        try:
            src = (ROOT / path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for line, text in findings(path, src):
            print(f"{path}:{line}: {text}")
            failed += 1
    if failed:
        print(f"comments: {failed} comment line(s) with Spanish characters; write them in English")
        return 1
    print("comments: all comments and docstrings are free of Spanish characters")
    return 0


if __name__ == "__main__":
    sys.exit(main())
