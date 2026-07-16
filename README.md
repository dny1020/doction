# doction

[![CI](https://github.com/dny1020/doction/actions/workflows/ci.yaml/badge.svg)](https://github.com/dny1020/doction/actions/workflows/ci.yaml)
![Python](https://img.shields.io/badge/python-3.13-blue)
![License](https://img.shields.io/badge/license-MIT-green)
[![GHCR](https://img.shields.io/badge/ghcr.io-dny1020%2Fdoction-blue?logo=docker)](https://github.com/dny1020/doction/pkgs/container/doction)

A self-hosted, markdown-first wiki and knowledge base built for humans **and** AI agents.
Markdown pages with per-page git history, PostgreSQL full-text search plus optional local
semantic search, a REST API, and a **native MCP server** to plug agents in. Runs as an app
container + a Postgres container — no API keys, no SaaS, no LLM inside doction itself.

> **Why doction?** Unix-style and boring by design. Your notes are plain markdown in a git
> repo; search runs locally; agents talk to it over a standard MCP interface. doction does
> *retrieval* — the language model lives in your agent, not here.

![doction — page view with sidebar, tags and git-tracked markdown](docs/assets/ui.png)
<!-- NOTE: this screenshot predates the React SPA (now served at /app); regenerate against the current UI. -->

---

## Features

- **Markdown-first** — pages, workspaces, `[[wikilinks]]`, `#tags`, and YAML frontmatter.
- **Full-text search** — PostgreSQL native FTS (`tsvector`/GIN), ranked with `ts_rank`.
- **Local semantic search** (opt-in) — ONNX embeddings (MiniLM) baked into the image:
  `sgrep` (meaning-based search) and `rag` (retrieval with provenance). Fully offline, no
  API keys; gracefully degrades to FTS when disabled.
- **Per-page git history** — every save is a commit; browse diffs and previous versions.
- **Local ML, no LLM** — wikilink & tag suggestions, near-duplicate detection, extractive
  summaries (TextRank) and workspace insights (PageRank, orphans, broken links, topic
  clusters), all computed locally with numpy over the existing embeddings/link graph.
- **OCR for uploads** (opt-in) — tesseract indexes the text inside pasted screenshots so
  they show up in search.
- **Cross-encoder reranker** (opt-in) — a second tiny ONNX model re-scores the top
  semantic hits for noticeably better precision.
- **REST API** + **native MCP server** (JSON-RPC 2.0, 17 tools) for agents.
- **No LLM inside doction** — retrieval only; the connected agent does the generation.

## How it works

```
            ┌──────────────── doction (app container) ─────────────────┐    ┌─── postgres ───┐
  Browser ──┤  React SPA at /app                                       │    │ pages, FTS      │
  curl    ──┤  REST  /api/*                                            ├────┤ (tsvector/GIN), │
  Agent   ──┤  MCP   /api/mcp        git repo (one commit per save)    │    │ tags, links,    │
            │                        embeddings worker (async, opt-in) │    │ chunk vectors   │
            │                                           MiniLM ONNX    │    └─────────────────┘
            └───────────────────────────────────────────────────────────┘
```

On every save, doction commits the page to git and extracts its metadata (frontmatter,
tags, wikilinks) into indexed tables. When semantic search is enabled, a background worker
chunks and embeds the page without blocking the app. doction handles **retrieval** and
light local ML (suggestions, insights, *extractive* summaries — it only selects existing
sentences, never writes new text); generative answers are the job of the agent connected
over MCP — there is no LLM inside doction.

---

## Quick start

doction needs a Postgres instance next to it. `compose.yaml` in this repo wires both
containers together (multi-arch image, amd64 + arm64):

```bash
cp .env.example .env   # edit POSTGRES_PASSWORD and SECRET_KEY
docker compose up
# open http://localhost:8000 and register the first user
```

### Configuration

| Variable | Description | Default |
|---|---|---|
| `SECRET_KEY` | Key used to sign JWTs. **Change in production.** | insecure dev value |
| `DATABASE_URL` | Postgres connection string. | `postgresql://doction:doction@postgres:5432/doction` |
| `DATA_DIR` | Directory for the git pages repo + uploads. | `/data` |
| `SECURE_COOKIES` | `1` when behind TLS (reverse proxy). | off |
| `SEMANTIC_SEARCH` | `1` enables local semantic search (`sgrep` / `rag`). | off |
| `RERANK` | `1` re-scores top `sgrep` hits with a local cross-encoder (requires `SEMANTIC_SEARCH=1`). | off |
| `OCR_UPLOADS` | `1` OCR-indexes uploaded images with tesseract so they appear in search. | off |
| `OCR_LANGS` | tesseract language packs used for OCR. | `eng+spa` |
| `LOG_LEVEL` | Root logger level (`DEBUG`/`INFO`/`WARNING`/…). | `INFO` |
| `LOG_DIR` | Directory for the rotated log file (also mirrored to stdout). | `/logs` |

> The embedding model (~22 MB) and the reranker (~23 MB) ship inside the image. Each is
> loaded into RAM only when its flag is on; when off, they cost nothing.

---

## REST API

### Authentication

```bash
DOCTION=http://localhost:8000

# JWT (valid 7 days)
TOKEN=$(curl -s -X POST $DOCTION/api/token \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"yourpass"}' | jq -r .token)

# Long-lived PAT (the plaintext is shown ONCE)
curl -s -X POST $DOCTION/api/tokens \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"name":"my-laptop"}'
# → {"id": 1, "name": "my-laptop", "token": "doction_..."}

export TOKEN=doction_...
```

### Endpoints

```
POST   /api/token                        JWT (7 days)
POST   /api/tokens                       create PAT
GET    /api/tokens                       list PATs
DELETE /api/tokens/{id}                  revoke PAT

GET    /api/workspaces                   list workspaces
POST   /api/workspaces                   create workspace
GET    /api/pages                        page tree
GET    /api/pages/{slug}                 read page (JSON)
GET    /api/pages/{slug}/raw             raw markdown
POST   /api/pages                        create page
PUT    /api/pages/{slug}                 update page
DELETE /api/pages/{slug}                 delete page
GET    /api/search?q=...                 full-text search (PostgreSQL FTS)
GET    /api/search?q=...&mode=semantic   semantic search (sgrep; reranked with RERANK=1)
GET    /api/search?q=...&uploads=1       also match OCR text of uploaded images
GET    /api/pages/{slug}/suggest-links   wikilink suggestions (embeddings / title mentions)
GET    /api/pages/{slug}/suggest-tags    tag suggestions (TF-IDF vs the workspace)
GET    /api/pages/{slug}/summary         extractive summary (TextRank, no LLM)
GET    /api/insights                     workspace health: graph + duplicates + clusters
GET    /api/pages/{slug}/history         git history
GET    /api/pages/{slug}/history/{sha}   content at a commit
POST   /api/mcp                          MCP (JSON-RPC 2.0)
GET    /health                           health check
```

All page routes accept `?ws=<slug>` to select a workspace.

### Examples

```bash
# create a page from a markdown file
curl -s -X POST $DOCTION/api/pages \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "$(jq -n --arg t 'K8s Runbook' --rawfile c runbook.md '{title:$t,content:$c}')"

# search
curl -s -H "Authorization: Bearer $TOKEN" "$DOCTION/api/search?q=kamailio" | jq

# git history
curl -s -H "Authorization: Bearer $TOKEN" \
  "$DOCTION/api/pages/k8s-runbook/history" | jq
```

---

## MCP — connecting agents

Native MCP server (JSON-RPC 2.0, stateless, no SDK). Use a PAT as the Bearer token:

```bash
claude mcp add --transport http doction $DOCTION/api/mcp \
  --header "Authorization: Bearer doction_..."
```

Once connected, the agent sees all 17 tools:

![doction MCP server connected inside an agent — authenticated](docs/assets/mcp.png)

| Tool | What it does |
|---|---|
| `list_workspaces` | list workspaces |
| `list_members` | list members of a workspace |
| `list_pages` | page tree |
| `get_page` | read a page (markdown + metadata) |
| `search_pages` | full-text search (PostgreSQL `tsvector`/`ts_rank`) |
| `create_page` | create a page + git commit |
| `update_page` | update a page + git commit |
| `get_page_history` | a page's git history |
| `extract` | structured query by frontmatter `type:` / tags (no LLM) |
| `list_backlinks` | pages linking here via `[[wikilink]]` |
| `related_pages` | neighbor pages by shared tags (knowledge graph) |
| `sgrep` | semantic search blended with keyword boost (reranked when `RERANK=1`) |
| `rag` | top-k chunks with provenance for the agent to synthesize |
| `suggest_links` | pages this page should link to but doesn't yet |
| `suggest_tags` | candidate tags via TF-IDF against the workspace corpus |
| `summarize_page` | extractive TextRank summary (no LLM) |
| `workspace_insights` | PageRank, orphans, hubs, broken links, duplicates, topic clusters |

`initialize` and `tools/list` are open; `tools/call` requires a Bearer token. Probe the
deployed version without auth:

```bash
curl -s -X POST $DOCTION/api/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26"}}' | jq
```

---

## Development

```bash
uv sync --dev
uv run uvicorn app.main:app --reload   # dev server on :8000
uv run pytest                          # tests
uv run ruff check . && uv run ruff format --check . && uv run pyright app tests
```

Stack: FastAPI (REST + native MCP) serving a React SPA (Vite, built into the image at
`/app`), PostgreSQL (no ORM, raw SQL), and ONNX embeddings via onnxruntime + tokenizers.
See [CONTRIBUTING.md](CONTRIBUTING.md) to get started.

## Deployment

A new image is published on every push to `main`: GitHub Actions runs lint + tests inside
the image (`docker build --target test`, Postgres embedded in that build stage) and pushes
`ghcr.io/dny1020/doction:{version}` and `:latest` (amd64 + arm64).

For production, run both containers on a shared network behind a TLS-terminating reverse
proxy:

```bash
docker network create doction-net
docker run -d --name doction-postgres --restart unless-stopped --network doction-net \
  -e POSTGRES_USER=doction -e POSTGRES_PASSWORD=$(openssl rand -hex 24) -e POSTGRES_DB=doction \
  -v /srv/doction/postgres:/var/lib/postgresql/data \
  postgres:16-alpine

docker run -d --name doction --restart unless-stopped --network doction-net \
  -p 127.0.0.1:8000:8000 \
  -e SECRET_KEY=$(openssl rand -hex 32) \
  -e DATABASE_URL=postgresql://doction:<same-password-as-above>@doction-postgres:5432/doction \
  -e SECURE_COOKIES=1 \
  -e SEMANTIC_SEARCH=1 \
  -v /srv/doction:/data \
  -v /srv/doction/logs:/logs \
  ghcr.io/dny1020/doction:latest
```

Terminate TLS in nginx/Caddy/Traefik pointing at `http://127.0.0.1:8000`. Page content
(git repo + uploads) lives in `/data`; the database lives in Postgres's own volume — back
up both. Logs (console + rotated file) live in the separate `/logs` volume; diagnostic
only, not part of the backup.

Pushing to `main` publishes the image to GHCR; deploying is a plain `docker compose pull`
and `docker compose up -d` on the host, with your own compose file.

## License

MIT — see [LICENSE](LICENSE).
