# Contributing to doction

doction is deliberately small: a markdown wiki that stores plain files, answers over REST and
MCP, and has no LLM inside it. Changes that keep it that way get merged fastest. For anything
bigger than a bug fix, open an issue first: scope is cheaper to settle there than in a diff.

## Setting up

You need Docker (the tests start their own Postgres), [uv](https://docs.astral.sh/uv/) and Node.

```bash
make setup                # uv sync, npm ci, build the frontend
cp .env.example .env      # set POSTGRES_PASSWORD and SECRET_KEY
make dev                  # backend on :8000
make frontend             # Vite dev server, proxies /api to :8000
```

## Before you open a pull request

```bash
make check                # ruff, pytest, the frontend gate and the docs build
```

`make docs` needs `uv sync --group docs` once. Run `cd frontend && npm run test` when you touch
`frontend/src/`. Any change under `frontend/`, `app/static/style.css` included, shows up in
the app only after `make build-web`.

## What gets merged

- One concern per pull request, with tests for the behaviour it changes. The suite talks to a
  real Postgres; prefer that over mocks.
- Code, comments and docs in English. Comments say why, not what.
- Docs move with the code: update `README.md`, `docs/` or `DESIGN.md` in the same pull request.
- A new dependency says what it replaces and carries a licence compatible with AGPL-3.0-only.
- Commit messages are conventional commits: `fix(search): fold accents before stemming`.

## Releasing (maintainer)

Every push to `main` that changes the image publishes `ghcr.io/dny1020/doction:latest`. To
mark a version, bump it in `pyproject.toml` (the first push with a new version also publishes
that tag), then `gh release create vX.Y.Z --generate-notes`. Deploying is manual; see
[Operations](docs/operations.md).

Security problems go to [SECURITY.md](SECURITY.md), not issues. Contributions are accepted
under the [AGPL-3.0-only](LICENSE), the same terms as the rest of the project.
