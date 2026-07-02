# SPEC.md

## Problem

Backend/DevOps engineers (and the AI agents they run) need a shared, self-hosted place
for runbooks and notes that:

- agents can read and write through a standard protocol, not a bespoke scraping integration;
- keeps full history without bolting on a separate versioning system;
- runs fully offline on modest hardware (a Raspberry Pi), with no cloud services or
  API keys required to operate — self-hosted PostgreSQL is fine, a SaaS DB is not;
- doesn't hand notes to a third-party SaaS.

## Non-goals

- Not a general-purpose CMS or blog platform.
- doction does not generate text (no summarization, no chat). It does **retrieval only**;
  the language model lives in the connected agent.
- Not a multi-tenant SaaS. One self-hosted deployment per team/homelab.

## Chosen approach

- A single FastAPI app exposes JSON `/api` + a native MCP server (`/api/mcp`) as the only
  backend surfaces. The React SPA (`/app`) is a thin client of that same API, authenticated
  with the same session cookie — no separate backend-for-frontend.
- Storage is deliberately boring: PostgreSQL (native full-text search via `tsvector`/GIN)
  for structured data (users, workspaces, page metadata, search index), plain markdown
  files in a git repository for content. Every page save is a git commit —
  history/diff/restore come for free instead of a bespoke revisions table.
- Semantic search (ONNX MiniLM) is optional and off by default; it degrades to FTS
  when disabled or unindexed, so the base product never depends on it.
- App container + a Postgres container, no Redis, no broker. The deployment target is a
  Raspberry Pi pulling images over a 5-minute systemd timer, not a cluster; Postgres isn't
  reachable from outside the app container (internal-only network).

## Key decisions and why

- **PostgreSQL instead of SQLite.** Migrated in v0.15 to the team's standard backend
  store: PostgreSQL's `tsvector`/GIN full-text search replaces FTS5 with a generated
  column instead of triggers, MVCC removes SQLite's single-writer file-lock ceiling, and
  ops tooling (`pg_dump`/`pg_restore`, `psql`) is more familiar than SQLite's online
  backup API. Trade-off: no longer a single container — the Pi now runs an app container
  + a Postgres container instead of one, and `/data` no longer holds *all* state (see
  Requirements below).
- **No ORM.** `app/db.py` is raw SQL against PostgreSQL. The schema is small and stable;
  an ORM or generic repository layer would add abstraction the project doesn't need
  (see the "avoid generic repositories" rule in engineering guidelines).
- **Native MCP implementation, no SDK.** `app/mcp.py` implements JSON-RPC 2.0 by hand.
  One fewer dependency, full control over the stateless HTTP contract, and it keeps
  the tool surface (13 tools) explicit and auditable in one file.
- **Git-backed pages instead of a version table.** Reuses a tool operators already
  know (`git log`, `git diff`) instead of reinventing versioning in SQL. `git_repo.py`
  failures never block a save — git is an enhancement, not a dependency of the write path.
- **Workspaces + membership, not per-page ACLs.** `owner`/`member` roles at the
  workspace level match how small teams actually share a wiki; page-scoped queries
  filter by `workspace_id` only, keeping authorization simple to reason about.
- **Retrieval-only, no LLM inside doction.** Keeps the server cheap enough to run on a
  Pi and avoids owning API keys/inference cost. `rag`/`sgrep` return ranked chunks with
  provenance; synthesis is the connected agent's job.
- **React SPA replacing server-rendered Jinja/HTMX.** One JSON API surface serves both
  the browser and agents instead of maintaining two rendering paths. This finished in
  v0.13.0; the legacy templated UI is fully retired.

## Architecture (summary)

See `CLAUDE.md` → "App layout" for the authoritative file-by-file breakdown. At a glance:

- `app/main.py` — FastAPI app, all routes, auth middleware, SPA host
- `app/db.py` — PostgreSQL access (psycopg3, connection pool), schema
- `app/git_repo.py` — per-save git commit, history/diff/restore
- `app/meta.py` — markdown metadata parsing (frontmatter, tags, wikilinks, chunking)
- `app/embeddings.py` — optional local semantic search (ONNX)
- `app/mcp.py` — MCP JSON-RPC server
- `app/logging_config.py` — stdout + rotated-file logging setup
- `frontend/` — React SPA (Vite, plain JSX), built into `app/static/app/`

## Requirements / constraints

- Must run on ARM (Raspberry Pi): app container + Postgres container, no inbound ports
  exposed besides the reverse proxy — Postgres sits on an internal-only network, never
  reachable from outside the app container.
- Must not require API keys or cloud/SaaS services; Postgres is self-hosted alongside
  the app, same as SQLite was.
- Runtime stays pure Python; Node is only needed at build time for the SPA bundle.
- Mutable state now lives in two places: Postgres's own data directory (all structured
  data) and the `/data` volume (git repo of pages + uploads). Both are covered by
  `infra/backup.sh`/`restore.sh` (`pg_dump`/`pg_restore` + tar), but it's two volumes to
  back up, not the single-directory guarantee SQLite gave.

## Status

Current stable line: v0.14.x. React SPA migration is complete; the legacy Jinja/HTMX UI
has been retired. PostgreSQL replaced SQLite in v0.15 (see
`scripts/migrate_sqlite_to_postgres.py` for the one-time data migration). See
`CHANGELOG.md` for release-by-release detail.
