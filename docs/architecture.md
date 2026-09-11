# Architecture

doction is a FastAPI application, a Postgres database, and a git repository of markdown
files. That is the whole system. This page explains how those three relate, and why
several deliberately odd choices are what they are.

## The shape

```
            ┌──────────────── doction (app container) ─────────────────┐    ┌─── postgres ───┐
  Browser ──┤  React SPA at /app                                       │    │ pages, FTS      │
  curl    ──┤  REST  /api/*                                            ├────┤ (tsvector/GIN), │
  Agent   ──┤  MCP   /api/mcp        git repo (one commit per save)    │    │ tags, links,    │
            │                        embeddings worker (async, opt-in) │    │ chunk vectors   │
            │                                           MiniLM ONNX    │    └─────────────────┘
            └───────────────────────────────────────────────────────────┘
```

The server is JSON only. It stores raw markdown and does no server-side rendering: the
browser gets the markdown and renders it. That is what lets the same endpoints serve a
browser, `curl`, and an agent without a separate API.

## Where a page lives

A saved page exists in two places at once, and they answer different questions.

**On disk**, as a markdown file in a git repo at `{DATA_DIR}/pages/<workspace>/<slug>.md`.
This is the source of truth for content and history. Every save is a commit, so
`GET /api/pages/{slug}/history` is `git log` and the diff view is `git diff`. Git failures
never break a save — the page is written and indexed either way, you just lose that
commit.

**In Postgres**, as a row plus its extracted metadata. This is the source of truth for
*queries*: search, the tag index, the link graph, the page tree. Nothing here is content
you would mourn; it is all derivable from the files.

That split is why the backup story has two halves. The database alone gives you an index
of pages you no longer have; the volume alone gives you pages with no search until they
are reindexed.

## The schema converges, it does not migrate

`init_db()` creates the entire schema with `CREATE TABLE IF NOT EXISTS`. There is no
migration ladder, no version table, and no `alembic upgrade head` in the deploy
procedure. Every boot runs the same code.

The interesting part is what happens when the *definition* changes. `search_vector` is a
generated column, so its expression is baked into the table. On boot,
`_converge_search_vectors()` compares each column's stored generation expression against
the one the code declares, and rebuilds the column and its GIN index only when they
differ.

That is what lets a change to the text-search configuration reach an existing database
with no manual SQL. It also makes rollback safe in both directions: an older image
compares the same way and converges the column *back* on its own.

The cost is honest: it is one table rewrite on the first boot after such a change. At
wiki scale that is instant.

## Search

Three modes on `GET /api/search?mode=`:

- **`keyword`** (the default) — Postgres full-text search over the generated `tsvector`
  column, ranked with `ts_rank`. Always available.
- **`semantic`** — cosine similarity over chunk embeddings, opt-in.
- **`hybrid`** — full-text hits first, then semantic hits above a score floor, deduped by
  slug.

**The sidebar uses `hybrid`, and the choice matters.** Semantic search alone lets an exact
term lose to a page that is merely about the same topic — you type a hostname and get an
essay. Putting lexical hits first fixes that without giving up conceptual recall.

**MCP's `sgrep` stays unfiltered on purpose.** A human wants the best answer at the top; an
agent wants the whole ranked list so it can decide. Truncating for an agent throws away
the context it was going to reason over.

### The text-search configuration

Search runs on a named Postgres configuration, `doction`: `unaccent` chained ahead of
`english_stem`. The reason is narrow and worth knowing.

`to_tsvector('english', 'Renovación')` indexes the accented token, so a search for
`renovacion` missed the page entirely. Accent folding fixes it — but `unaccent()` cannot
be called directly in a generated column, because it is `STABLE`, not `IMMUTABLE`. Inside
a named text-search configuration it can. That indirection is the entire reason the
configuration exists.

Every constant in the search path cites a measurement in `evals/results/`. The eval
harness lives outside pytest deliberately: a quality number that can fail a build is a
build that gets ignored.

## Embeddings, when enabled

- A MiniLM int8 ONNX model, ~23 MB, baked into the image. It loads lazily, so the flag off
  costs nothing and the flag on costs nothing until the first query.
- Vectors live in `page_chunks` as `BYTEA`. Similarity is numpy cosine plus a keyword
  boost. There is no vector extension and no vector database.
- A background worker embeds pages marked `embed_dirty` via `asyncio.to_thread`. No
  broker, no Celery, no Redis.
- Chunk reads are filtered by `model`, and the worker re-queues pages whose vectors came
  from a different encoder. **Two embedding spaces must never meet in one cosine** — the
  numbers would be meaningless, and silently so.

doction only retrieves. There is no LLM inside it; the connected agent generates.

## Wikilinks and the graph

`[[target]]` and `[[target|label]]` are parsed on every save into `page_links`, which keeps
both the raw `dst_slug` and the resolved `dst_page_id`.

Keeping the unresolved form is the point: **a broken link is information.** It is the only
representation a link to a page that does not exist yet can have, and surfacing it is how
`workspace_insights` reports broken links.

On the client, wikilinks become anchors through a markdown-it *inline rule* that emits
tokens — never an HTML string. Splicing a document-derived target into `<a href>` is
exactly the shape of a stored XSS, and this is the mitigation.

`GET /api/graph` serves the drawable graph, trimmed to the top-PageRank subgraph past a
node limit, and the `/graph` route draws it as SVG the application writes itself. That is
why both themes work with no palette bridging: every colour is a design token. mermaid,
which is a third-party renderer, needed exactly that bridging.

## Local ML without an LLM

`suggest.py` and `graph.py` do the work usually handed to a model:

| Feature | How |
| --- | --- |
| Link suggestions | TF-IDF similarity against the workspace corpus |
| Tag suggestions | TF-IDF, no vectors needed |
| Near-duplicate detection | cosine over chunk vectors |
| Summaries | TextRank — **extractive**, it selects existing sentences and never writes new text |
| Central pages, hubs, orphans | PageRank |
| Topic clusters | deterministic k-means |

numpy only. No NetworkX, no scikit-learn. Every result carries a `mode` field saying how
it was produced, so a caller can tell a vector-based answer from a keyword fallback.

## Collaboration and access

Workspaces are shared through `workspace_members(workspace_id, user_id, role)` with roles
`owner` and `member`. Access is gated when the workspace is resolved, which is why page
queries filter on `workspace_id` alone.

`pages.user_id` is the creator and `pages.updated_by` the last editor. **Both are
authorship, never an access gate.** Reading them as permissions is the mistake this
paragraph exists to prevent.

Workspace slugs are globally unique, because a slug is also a directory name in the git
repo.

## Why there is no ORM

Raw SQL over psycopg3 with a `ConnectionPool`. The queries here are mostly full-text
search, recursive tree walks, and generated-column maintenance — the three things an ORM
is worst at expressing and best at hiding. Reading the SQL is how you understand the
performance.

## Deliberate non-goals

- **No LLM inside doction.** Retrieval only.
- **No outbound network at runtime**, except webhooks you configure. Fonts, KaTeX,
  mermaid, highlight.js and d3-force are all served by the deployment; `npm run check`
  fails the build if a remote asset creeps in. doction runs air-gapped.
- **No SDKs.** The MCP server is JSON-RPC 2.0 written directly. No MCP SDK, no vector
  library, no graph library.
- **No multi-tenancy quotas.** Nothing limits how much one workspace can index. Known gap.
