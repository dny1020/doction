# Contributing to doction

Thanks for your interest in improving doction! This project favors a small, sharp,
Unix-style codebase: zero-dependency-native over SDKs, plain markdown, local-first.

## Development setup

doction uses [uv](https://docs.astral.sh/uv/) and targets Python 3.13.

```bash
uv sync --dev
uv run uvicorn app.main:app --reload   # dev server on :8000
```

Useful commands:

```bash
make test           # pytest
make lint           # ruff check
make test-image     # build + smoke-test /health locally
```

To exercise semantic search without the real ONNX model, the test suite uses a
deterministic stub:

```bash
EMBED_STUB=1 SEMANTIC_SEARCH=1 uv run pytest tests/
```

## Project layout

- `app/main.py` — FastAPI app, all routes (REST `/api` + MCP) + the `/app` SPA host, auth middleware, lifespan.
- `app/db.py` — SQLite layer (no ORM): users, workspaces, pages, tokens, FTS5, chunks.
- `app/mcp.py` — native MCP server (JSON-RPC 2.0) at `POST /api/mcp`.
- `app/meta.py` — pure markdown parsers: frontmatter, tags, wikilinks, chunking.
- `app/embeddings.py` — opt-in local semantic search (ONNX MiniLM).
- `app/git_repo.py` — silent git commit on every page save.
- `app/i18n.py` — EN/ES translation catalog, served to the SPA via `/api/i18n`.
- `frontend/` — React SPA (Vite, plain JSX); built into `app/static/app/` and served at `/app`.

## Guidelines

- **Keep dependencies minimal.** Prefer the standard library and small, well-understood
  libraries. New runtime dependencies should be justified in the PR.
- **Tests are required** for behavior changes. Tests live in `tests/` and must be named
  `test_*.py`. Run `make test` and `make lint` before pushing.
- **Match the surrounding style.** ruff enforces formatting/linting; let it guide you.
- **Database schema migrations** must be defensive (`IF NOT EXISTS` + rebuild on legacy
  state) and run on startup — never assume a fresh database.
- **On a release**, bump the version in **both** `pyproject.toml` and `SERVER_INFO` in
  `app/mcp.py`, and add a `CHANGELOG.md` entry.

## Pull requests

1. Fork and create a feature branch off `main`.
2. Make your change with tests; keep the diff focused.
3. Ensure `make test` and `make lint` pass.
4. Open a PR describing the change and the motivation. CI runs lint + tests in-image on
   every PR.

By contributing, you agree that your contributions are licensed under the MIT License.
