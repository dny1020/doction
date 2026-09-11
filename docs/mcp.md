# Agents and MCP

doction speaks MCP (Model Context Protocol) natively at `POST /api/mcp`: JSON-RPC 2.0,
stateless, no SDK. 27 tools over the same data the REST API and the web UI see.

The division of labour is the important part. **doction retrieves; your agent generates.**
There is no language model inside doction, so no tool here writes prose — `summarize_page`
is extractive TextRank, selecting sentences that already exist.

## Authentication

`initialize` and `tools/list` are open, so a client can discover the server without
credentials. `tools/call` requires a Bearer token.

Two kinds work:

| Token | Lifetime | Get it from | Use for |
| --- | --- | --- | --- |
| Personal access token, `doction_…` | until revoked | `POST /api/tokens` | agents, scripts, anything long-lived |
| JWT | 7 days | `POST /api/token` | short-lived sessions |

Mint a personal access token:

```bash
curl -s -X POST $DOCTION/api/tokens \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $EXISTING_TOKEN" \
  -d '{"name":"my-laptop"}' | jq
# {"id":1,"name":"my-laptop","token":"doction_..."}
```

**The plaintext is shown once.** Only a SHA-256 hash is stored, so a lost token is
regenerated, never recovered. List them with `GET /api/tokens` and revoke with
`DELETE /api/tokens/{id}`, which takes effect immediately.

## Connecting an agent

Claude Code:

```bash
claude mcp add --transport http doction $DOCTION/api/mcp \
  --header "Authorization: Bearer doction_..."
```

Any other MCP client: point it at `$DOCTION/api/mcp` over HTTP with that same
`Authorization` header. There is no stdio transport and no local process to spawn — the
server is the deployment.

Verify the connection without a client:

```bash
curl -s -X POST $DOCTION/api/mcp \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26"}}' | jq
# {"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2025-03-26",
#  "capabilities":{"tools":{}},"serverInfo":{"name":"doction","version":"0.31.3"}}}
```

## The five tools that cover most work

An agent's loop is: find something, gather context, understand the shape of the workspace,
read a document exactly as stored, write back what it learned.

| Tool | What it does |
| --- | --- |
| `search_knowledge` | ranked pages for a query; lexical and vector rankings fused by reciprocal rank, filterable by tag and type |
| `get_rag_context` | the assembled top-k passages with provenance, within a character budget |
| `get_workspace_tree` | workspaces, pages and subpages as a hierarchy |
| `read_page_raw` | a page's markdown exactly as stored, frontmatter included |
| `upsert_page_section` | create or replace one section of a page without rewriting the rest |

`upsert_page_section` is the one to reach for when appending to a runbook. Rewriting a
whole page to add a paragraph produces a diff nobody can review.

## Choosing between the search tools

Four tools return "relevant pages" and they are not interchangeable.

| Tool | Ranking | Reach for it when |
| --- | --- | --- |
| `search_pages` | Postgres full-text, `ts_rank` | you know the term that appears in the page |
| `sgrep` | semantic, blended with a keyword boost | you know the *idea* but not the wording |
| `search_knowledge` | lexical and vector fused by reciprocal rank | general purpose; the best default |
| `rag` | top-k chunks, not pages, with provenance | you are about to synthesize an answer and need passages |

`sgrep` and `rag` need `SEMANTIC_SEARCH=1`. With it off they degrade to full-text search
rather than failing, so a tool call still returns something useful — check the `mode` field
in the response to know which path answered.

Unlike the web UI's sidebar, `sgrep` returns the whole ranked list unfiltered. That is
deliberate: an agent should decide what is relevant, not receive someone else's cutoff.

## Traversal: links versus tags

Three tools walk the graph, and confusing them gives wrong answers.

| Tool | Traverses | Answers |
| --- | --- | --- |
| `list_backlinks` | wikilinks, one hop, incoming | "what references this page?" |
| `get_linked_knowledge` | wikilinks, up to 3 hops, both directions | "what is the neighbourhood of this page?" — each result carries its distance, direction, path, and whether the target exists |
| `related_pages` | shared tags | "what else is about this subject?" |

Two pages can share every tag and never reference each other. Links are a claim someone
made; tags are a category someone assigned. Different questions, different tools.

`get_linked_knowledge` returning a page marked as non-existent is not an error — a broken
wikilink is information, and it is how you find the page someone meant to write.

## The full tool list

| Tool | What it does |
| --- | --- |
| `list_workspaces` | list workspaces |
| `list_members` | list members of a workspace |
| `list_pages` | page tree |
| `list_children` | direct subpages of a page |
| `get_page` | read a page (markdown + metadata) |
| `read_page_raw` | markdown exactly as stored, frontmatter included |
| `create_page` | create a page + git commit |
| `update_page` | update a page + git commit |
| `upsert_page_section` | create or replace one section |
| `move_page` | reparent a page (cycle-safe) |
| `rename_page` | change a slug, leaving an alias so old links resolve |
| `delete_page` | soft-delete to the trash |
| `get_page_history` | a page's git history |
| `search_pages` | full-text search |
| `search_knowledge` | fused lexical + vector ranking |
| `sgrep` | semantic search with keyword boost |
| `rag` | top-k chunks with provenance |
| `get_rag_context` | assembled passages within a character budget |
| `extract` | structured query by frontmatter `type:` / tags (no LLM) |
| `list_backlinks` | incoming wikilinks, one hop |
| `get_linked_knowledge` | wikilink neighbourhood up to 3 hops |
| `related_pages` | neighbours by shared tags |
| `get_workspace_tree` | hierarchy of workspaces, pages, subpages |
| `suggest_links` | pages this page should link to but does not |
| `suggest_tags` | candidate tags via TF-IDF |
| `summarize_page` | extractive TextRank summary (no LLM) |
| `workspace_insights` | PageRank, orphans, hubs, broken links, duplicates, topic clusters |

## Notes for writing an agent against this

- **Every intelligence result carries a `mode` field** saying how it was produced. A
  caller can tell a vector-based answer from a keyword fallback, which matters when
  `SEMANTIC_SEARCH` is off and you were expecting semantics.
- **Writes are commits.** `create_page` and `update_page` each produce one git commit, so a
  loop that saves after every token produces unreadable history. Batch the edit.
- **`rename_page` leaves an alias**, so existing wikilinks keep resolving. You do not need
  to rewrite every referring page.
- **`delete_page` is a soft delete.** The page is in the trash, recoverable through the
  REST API. An agent cannot permanently destroy content.
- **Newly written pages are not instantly semantically searchable.** The embedding worker
  is asynchronous. Full-text search sees the page immediately, because Postgres maintains
  the `tsvector` column itself.
- **Scope your writes to a workspace.** Access is by membership, and a token carries its
  user's memberships. A token cannot reach a workspace its user was never added to.
