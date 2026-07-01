# SPEC.md

## Problem

Backend/DevOps engineers (and the AI agents they run) need a shared, self-hosted place
for runbooks and notes that:

- agents can read and write through a standard protocol, not a bespoke scraping integration;
- keeps full history without bolting on a separate versioning system;
- runs fully offline on modest hardware (a Raspberry Pi), with no external services or
  API keys required to operate;
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
- Storage is deliberately boring: SQLite (FTS5) for structured data (users, workspaces,
  page metadata, search index), plain markdown files in a git repository for content.
  Every page save is a git commit — history/diff/restore come for free instead of a
  bespoke revisions table.
- Semantic search (ONNX MiniLM) is optional and off by default; it degrades to FTS5
  when disabled or unindexed, so the base product never depends on it.
- Single container, no external services (no Postgres, no Redis, no broker). The
  deployment target is a Raspberry Pi pulling images over a 5-minute systemd timer,
  not a cluster.

## Key decisions and why

- **No ORM.** `app/db.py` is raw SQL against SQLite. The schema is small and stable;
  an ORM or generic repository layer would add abstraction the project doesn't need
  (see the "avoid generic repositories" rule in engineering guidelines) and would
  complicate the FTS5 triggers this project relies on.
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
- `app/db.py` — SQLite access, schema, defensive migrations
- `app/git_repo.py` — per-save git commit, history/diff/restore
- `app/meta.py` — markdown metadata parsing (frontmatter, tags, wikilinks, chunking)
- `app/embeddings.py` — optional local semantic search (ONNX)
- `app/mcp.py` — MCP JSON-RPC server
- `frontend/` — React SPA (Vite, plain JSX), built into `app/static/app/`

## Requirements / constraints

- Must run on ARM (Raspberry Pi) as a single container with no exposed inbound ports
  besides the reverse proxy.
- Must not require API keys or external services in the default configuration.
- Runtime stays pure Python; Node is only needed at build time for the SPA bundle.
- All mutable state (SQLite DB, git repo, uploads) lives under one `/data` volume so a
  single directory backup/restore captures everything.

## Status

Current stable line: v0.13.x. React SPA migration is complete; the legacy Jinja/HTMX UI
has been retired. See `CHANGELOG.md` for release-by-release detail.
