---
description: A self-hosted, markdown-first knowledge base for humans and coding agents. Plain markdown in git, local search, a REST API and a native MCP server.
hide:
  - toc
---

<div class="dx-hero" markdown>
<div class="dx-hero-text" markdown>

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

<div class="dx-hero-figure" role="img" aria-label="A browser, a coding agent and a script reach doction over /app, /api/mcp and /api; doction keeps pages in git, Postgres and embeddings."></div>

</div>

## Why doction

Engineering knowledge ends up split between a wiki people read and whatever an agent was told
in its last prompt. doction keeps one copy: pages are plain markdown in a git repository, search
runs locally, and an agent reaches the same pages a person does through a standard interface.

It is boring on purpose. doction does **retrieval** — the language model lives in your agent,
not here. There is no LLM, no API key and no SaaS inside it.

## What it does

<div class="grid cards" markdown>

-   **[Markdown in git](writing-pages.md)**

    ---

    Pages, workspaces, `#tags` and a metadata block, rendered in the browser from the markdown
    as stored. Every save is a commit: browse diffs, restore any version.

-   **[Links and a graph](links-and-graph.md)**

    ---

    `[[wikilinks]]` become edges: backlinks, broken links and orphans called out, and a drawn
    graph of the whole workspace.

-   **[Local search](search.md)**

    ---

    PostgreSQL full-text search with accent folding, plus opt-in semantic search from a model
    baked into the image. No API keys.

-   **[REST API](api.md) and [MCP](mcp.md)**

    ---

    The server is JSON only. Browsers, scripts and agents use the same pages and auth, and
    `/api/mcp` offers 27 tools, from search to writing one section of a page.

-   **[Local ML, no LLM](architecture.md#local-ml-without-an-llm)**

    ---

    Link and tag suggestions, near-duplicate detection, summaries and workspace insights,
    computed with numpy.

-   **[Self-hosted](install.md)**

    ---

    An app container and a Postgres container, amd64 and arm64, with no request leaving your
    network at runtime. Shared workspaces, signed webhooks, opt-in OCR.

</div>

Connect a coding agent with a personal access token:

```bash
claude mcp add --transport http doction $DOCTION/api/mcp \
  --header "Authorization: Bearer doction_..."
```

How the pieces fit, and why the odd-looking decisions are what they are, is in
[Architecture](architecture.md).

## Get started

Two containers, one `.env`, and a first user.

[Install doction](install.md){ .md-button .md-button--primary }
[Configuration](configuration.md){ .md-button }
