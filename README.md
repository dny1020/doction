# doction

[![CI](https://github.com/dny1020/doction/actions/workflows/ci.yaml/badge.svg)](https://github.com/dny1020/doction/actions/workflows/ci.yaml)
![Python](https://img.shields.io/badge/python-3.13-blue)
[![License: AGPL v3](https://img.shields.io/badge/license-AGPL--3.0--only-blue)](LICENSE)
[![GHCR](https://img.shields.io/badge/ghcr.io-dny1020%2Fdoction-blue?logo=docker)](https://github.com/dny1020/doction/pkgs/container/doction)

A self-hosted, markdown-first wiki and knowledge base built for humans **and** AI agents.
Markdown pages with per-page git history, PostgreSQL full-text search plus optional local
semantic search, a REST API, and a **native MCP server** to plug agents in. Runs as an app
container + a Postgres container — no API keys, no SaaS, no LLM inside doction itself.

> **Why doction?** Unix-style and boring by design. Your notes are plain markdown in a git
> repo; search runs locally; agents talk to it over a standard MCP interface. doction does
> *retrieval* — the language model lives in your agent, not here.

![doction reading a page: sidebar page tree, table of contents, a mermaid diagram and a highlighted SQL block, all rendered client-side from stored markdown](docs/assets/ui.png)

Every save is a git commit, so any page's history is a real diff:

![The history view of a page, showing a git diff with one line removed and two added](docs/assets/history.png)

---

## Features

- **Markdown-first** — pages, workspaces, `[[wikilinks]]`, `#tags`, and YAML frontmatter.
- **Per-page git history** — every save is a commit; browse diffs and previous versions.
- **A knowledge graph you can see** — backlinks with the sentence they sit in, and a graph
  view of the whole workspace with orphans and broken links called out.
- **Search** — PostgreSQL full-text search, plus opt-in local semantic search (MiniLM ONNX,
  baked into the image, no API keys).
- **Local ML, no LLM** — link and tag suggestions, near-duplicate detection, extractive
  summaries and workspace insights, computed with numpy.
- **REST API** and a **native MCP server** (JSON-RPC 2.0, 27 tools) for agents.
- **Self-hosted and offline** — an app container and a Postgres container, amd64 + arm64,
  with no CDN and no external request at runtime.

## Quick start

```bash
cp .env.example .env   # edit POSTGRES_PASSWORD and SECRET_KEY
mkdir -p data/logs     # the container runs non-root as uid 1000
docker compose up      # then open http://localhost:8000 and register
```

Sign-up is open by default: register your own account, then set `DISABLE_REGISTRATION=1`
and restart. Connecting an agent is one command with a personal access token:

```bash
claude mcp add --transport http doction $DOCTION/api/mcp \
  --header "Authorization: Bearer doction_..."
```

## Documentation

The reference lives in [`docs/`](docs/index.md) and is published as a site.

| Page | What it answers |
| --- | --- |
| [Installation](docs/install.md) | Compose, a bare `docker run` behind a proxy, or from source |
| [Configuration](docs/configuration.md) | Every environment variable, and what breaks if you skip it |
| [Writing pages](docs/writing-pages.md), [Linking](docs/linking.md), [Tags](docs/tags-and-metadata.md), [Search](docs/search.md), [Graph](docs/graph.md) | Using the wiki, including the behaviour that differs from what you would guess |
| [REST API](docs/api.md) | Every endpoint the application serves, grouped, with the auth each needs |
| [Agents and MCP](docs/mcp.md) | Connecting an agent, the auth model, choosing among the 27 tools |
| [Architecture](docs/architecture.md) | How the pieces fit, and why the odd decisions are what they are |
| [Operations](docs/operations.md) | Upgrades, backup and restore, logs, capacity |
| [Troubleshooting](docs/troubleshooting.md) | Symptom-first index of the failures people actually hit |

Development setup and the check gate are in [CONTRIBUTING.md](CONTRIBUTING.md), the
security model and reporting channel in [SECURITY.md](SECURITY.md), release notes in
[CHANGELOG.md](CHANGELOG.md), and what is identified but not yet done in
[ROADMAP.md](ROADMAP.md).

## License

GNU Affero General Public License v3.0 only — see [LICENSE](LICENSE).

doction is free software: you can redistribute it and modify it under the terms of the GNU
Affero General Public License, version 3, as published by the Free Software Foundation. It
is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY, without even
the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.

### What this obliges you to do

doction is software you host for people, so the licence attaches to *operating* it and not
only to handing out copies. Three cases, which is the whole of it:

| What you are doing | What you owe |
| --- | --- |
| Running a published release, unmodified | Nothing further. |
| Modifying it, and keeping the instance to yourself or your team | Nothing further. |
| Modifying it, and letting other people use it over a network | Those users are entitled to your modified source. |

That third case is why the licence is AGPL and not GPL. Under the plain GPL, hosting a
modified version for other people is not distribution, so nothing would be triggered and a
fork could be sold as a service with its changes kept private.

The instance helps you comply rather than leaving it to memory: set `SOURCE_URL` to where
your source lives, and doction shows it to signed-in users in Settings. It defaults to this
repository, so an unmodified deployment is already compliant with no configuration. If you
run a modified fork, point it at your own source — the default would be a confidently
incorrect claim.

### Previous releases

Relicensing is not retroactive. Releases through 0.31.3 were published under MIT and 0.31.4
under GPL-3.0-only; both grants stand, and anyone who received those versions keeps those
terms. AGPL-3.0-only applies from 0.31.5 onwards.

### Dependencies

The bundled dependencies keep their own licences, all compatible with AGPL-3.0: MIT, BSD,
ISC, Apache-2.0, MPL-2.0, Blue Oak 1.0.0, CC0, and LGPL-3.0-only for `psycopg`.
