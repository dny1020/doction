---
hide:
  - toc
---

<div class="dx-hero" markdown>

<p class="dx-eyebrow">self-hosted · markdown-first · REST + MCP</p>

# doction

<p class="dx-lead">A markdown-first knowledge base for humans and coding agents. Write plain
markdown in the browser, keep every change in git, and let your agents search, read and write
the same pages over a REST API or a native MCP server — on your own hardware.</p>

<div class="dx-actions" markdown>

[Get started](install.md){ .md-button .md-button--primary }
[REST API](api.md){ .md-button }
[MCP](mcp.md){ .md-button }

</div>

</div>

## Why doction

Engineering knowledge ends up split between a wiki people read and whatever an agent was told
in its last prompt. doction keeps one copy: pages are plain markdown in a git repository, search
runs locally, and an agent reaches the same pages a person does through a standard interface.

It is boring on purpose. doction does **retrieval** — the language model lives in your agent,
not here. There is no LLM, no API key and no SaaS inside it.

## Built for humans and coding agents

<div class="grid cards" markdown>

-   **Markdown**

    ---

    Pages, workspaces, `[[wikilinks]]`, `#tags` and a frontmatter block. Rendered in the
    browser from the markdown as stored.

-   **API-first**

    ---

    The server is JSON only. The same endpoints serve the browser, `curl` and an agent.

-   **MCP**

    ---

    A native MCP server at `/api/mcp` with 27 tools, from search and RAG context to writing
    one section of a page.

-   **Search**

    ---

    PostgreSQL full-text search by default, with opt-in local semantic search that runs
    fully offline.

-   **Knowledge graph**

    ---

    Wikilinks become edges. Backlinks, broken links, orphans and a drawable graph of the
    whole workspace.

-   **Self-hosted**

    ---

    An app container and a Postgres container. Multi-arch image, amd64 and arm64, with no
    external request at runtime.

</div>

## How it works

```text
   Human        Coding agent      Script
 (browser)         (MCP)          (curl)
     │               │               │
   /app          /api/mcp          /api
     └───────────────┼───────────────┘
                     │
                  doction
                     │
   markdown in git · Postgres · embeddings
                     │
   knowledge · search · graph · history
```

The browser app and scripts use the REST API under `/api`; agents use MCP at `/api/mcp`.
On every save, doction commits the page to git and extracts its frontmatter, tags and
wikilinks into indexed tables. With semantic search on, a background worker chunks and embeds
the page without blocking the save. The details, and why the odd-looking decisions are what
they are, are in [Architecture](architecture.md).

## Features

- **Per-page git history** — every save is a commit; browse diffs and previous versions.
- **Full-text search** — PostgreSQL `tsvector`/GIN with accent folding, ranked by `ts_rank`.
- **Local semantic search** (opt-in) — ONNX MiniLM embeddings baked into the image, no API
  keys; degrades to full-text search when off.
- **A graph you can see** — wikilinks are followable, every page lists what links to it, and
  the graph view draws the workspace with orphans and broken links called out.
- **Local ML, no LLM** — link and tag suggestions, near-duplicate detection, extractive
  summaries and workspace insights, computed with numpy.
- **Shared workspaces** — collaborators join as `owner` or `member`.
- **Outgoing webhooks** — page events delivered to a URL you control, signed with
  HMAC-SHA256.
- **OCR for uploads** (opt-in) — tesseract indexes the text inside pasted screenshots.

## API + MCP

doction is consumed by programs in two ways, over the same pages and the same auth.

<div class="grid cards" markdown>

-   **[REST API](api.md)**

    ---

    Every endpoint the application serves, grouped, with the authentication each one needs.
    Use it from scripts, CI jobs and `curl`.

-   **[MCP](mcp.md)**

    ---

    JSON-RPC 2.0 at `/api/mcp`, no SDK. Connect an agent with a personal access token and
    choose among the 27 tools.

</div>

```bash
claude mcp add --transport http doction $DOCTION/api/mcp \
  --header "Authorization: Bearer doction_..."
```

## Self-hosted

doction runs as two containers — the app and Postgres — on modest hardware you control.
Everything the browser loads is served by your instance, so it works on a LAN, over a VPN or
with no route to the internet. Your pages stay plain markdown in a git repository you own.

[Installation](install.md) covers Docker Compose, a plain `docker run` behind a reverse proxy,
and running from source. [Configuration](configuration.md) lists every environment variable
and what breaks if you skip it.

## Architecture

A FastAPI application, a Postgres database and a git repository of markdown files. That is the
whole system. [Architecture](architecture.md) explains how the three relate: where a page
lives, how search is built, why the schema converges instead of migrating, and why there is no
ORM.

## Documentation

### Using doction

| Page | What it answers |
| --- | --- |
| [Writing pages](writing-pages.md) | Creating pages, the tree, renames, history, and getting a deleted page back |
| [Linking pages](linking.md) | `[[wikilinks]]`, what resolves as a target, and why a broken link is kept |
| [Tags and metadata](tags-and-metadata.md) | `#tags`, the block at the top of a page, and the one spelling of it that is silently ignored |
| [Searching](search.md) | The three modes, and what a query actually does to what you typed |
| [The graph](graph.md) | The link graph, its limits, and the insights that read it without drawing it |

### Developer

| Page | What it answers |
| --- | --- |
| [REST API](api.md) | Every endpoint the application serves, grouped, with the auth each needs |
| [Agents and MCP](mcp.md) | Connecting an agent, the auth model, and which of the 27 tools to reach for |
| [Architecture](architecture.md) | How the pieces fit, and why the odd-looking decisions are what they are |

### Running doction

| Page | What it answers |
| --- | --- |
| [Introduction](../README.md) | Features, screenshots and a quick start |
| [Installation](install.md) | Getting a working instance, from Compose to a bare `docker run` behind a proxy |
| [Configuration](configuration.md) | Every environment variable, what it does, and what breaks if you skip it |
| [Operations](operations.md) | Upgrades, backup and restore, logs, capacity, what to do at 3am |
| [Troubleshooting](troubleshooting.md) | Symptom-first index of the failures people actually hit |

### Project

- [Contributing](../CONTRIBUTING.md) — local setup, the check gate, and how to get a change
  merged.
- [Security](../SECURITY.md) — the security model, the reporting channel, and the hardening
  checklist.
- [Design](../DESIGN.md) — the visual system, describing what is *implemented*.
- [Changelog](../CHANGELOG.md) — what changed per release.
- `evals/results/` — the retrieval measurements behind the search constants: why the reranker
  ships off and why the stemmer is English.

### Conventions used here

- Commands assume the container. Prefix with `docker compose exec doction` if you are running
  the Compose stack.
- `$DOCTION` is the base URL of your instance, e.g. `https://wiki.example.com`.
- Anything marked **opt-in** is off unless you set its flag. doction starts with everything
  expensive disabled.

## Get started

Two containers, one `.env`, and a first user.

[Install doction](install.md){ .md-button .md-button--primary }
[Read the introduction](../README.md){ .md-button }
