# Agents and MCP

doction speaks MCP (Model Context Protocol) natively at `POST /api/mcp`: JSON-RPC 2.0,
stateless, no SDK. 34 tools over the same data the REST API and the web UI see.

The division of labour is the important part. **doction retrieves; your agent generates.**
There is no language model inside doction, so no tool here writes prose — `summarize_page`
is extractive TextRank, selecting sentences that already exist.

## Authentication

`initialize` and `tools/list` are open, so a client can discover the server without
credentials. `tools/call` requires a Bearer token.

`initialize` also returns `instructions`, which MCP clients show to the model: pages connect
only through `[[slug]]` / `[[slug|label]]` wikilinks, nesting a page under a parent does not
link them, `suggest_links` finds what is worth linking, and pages are written for people in
natural prose. An agent learns this on connect, so a prompt does not have to repeat it.

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

Three tools return "relevant pages" and they are not interchangeable.

| Tool | Ranking | Reach for it when |
| --- | --- | --- |
| `search_pages` | Postgres full-text, `ts_rank` | you know the term that appears in the page |
| `search_knowledge` | lexical and vector fused by reciprocal rank | general purpose; the best default |
| `get_rag_context` | passages, not pages, with provenance | you are about to synthesize an answer and need passages |

Their semantic half needs `SEMANTIC_SEARCH=1`. With it off they degrade to full-text search
rather than failing, so a tool call still returns something useful — check the `mode` field
in the response to know which path answered.

Unlike the web UI's sidebar, `search_knowledge` returns the whole ranked list unfiltered. That is
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

## Structured memory

The original page tools remain available. The following tools add structured memory without
requiring agents to rewrite existing pages. REST clients can call the same operations at
`POST /api/knowledge/{operation}`, passing the MCP arguments as the JSON body.

| Tool | Arguments and result |
| --- | --- |
| `get_knowledge_object` | `workspace`, `slug`: stable page `id`, Markdown, parsed properties, aliases, relations, revision and Git status |
| `read_page_sections` | `workspace`, `slug`, optional `heading`, `offset`, `limit`, `newest_first`: whole sections and `next_offset` |
| `get_knowledge_history` | `workspace`, `slug`, optional `offset`, `limit`: durable Markdown revisions with actor and recording date |
| `set_knowledge_metadata` | `workspace`, `slug`, `properties`, optional `expected_revision`: update frontmatter and return the object |
| `relate_knowledge` | `workspace`, `slug`, `target`, `kind`, optional `evidence`: create a typed edge within one workspace |
| `remove_knowledge_relation` | `workspace`, `slug`, `relation_id`: remove an outgoing typed edge |
| `add_entity_alias` | `workspace`, `slug`, `alias`: identify the same entity by another normalized name; collisions fail |
| `query_knowledge_context` | `query`, optional `workspaces`, `type`, `status`, `entity`, `as_of`, `budget`, `limit`: passages across workspaces with one shared budget |
| `retry_page_version` | `workspace`, `slug`: retry a pending Git snapshot |

Types are `Project`, `Service`, `Runbook`, `Incident`, `Decision`, `Conversation`, `Person`,
`Event`, `Task`, `Concept` and `Research`. Existing custom frontmatter types remain readable.
Statuses are `active`, `draft`, `superseded` and `archived`. Additional supported properties are
`source`, `source_revision`, `external_id`, `observed_at`, `valid_from`, `valid_until` and
`reviewed_at`. Date properties accept ISO dates or timestamps. Unknown frontmatter fields
are retained when metadata is edited.

Typed edges support `affects`, `belongs_to`, `derived_from`, `supersedes`, `decided_by` and
`related_to`. They are stored in PostgreSQL and returned in the object's JSON; they do not
rewrite Markdown or replace wikilinks. Database backups must include these tables. A Markdown-only
export cannot reconstruct typed edges. Aliases resolve within a workspace and do not merge entities.

`query_knowledge_context` defaults to active objects, including legacy pages without a status.
Metadata and direct typed-neighbor constraints apply before retrieval ranking and limits. `entity`
selects an entity plus its direct typed neighbors, in either direction. `as_of` filters the stored
validity interval; it does not reconstruct historical Markdown. Candidates from each workspace are
combined by local rank with deterministic workspace/slug tie breaking, then deduplicated and packed
into the global character budget. This combines existing lexical/vector retrieval with graph filters;
it is not a graph inference engine. Use `get_knowledge_history` for actual recorded revisions.

### Concurrent writes and retries

- `upsert_page_section` locks the page before reading and changing it, preserving concurrent edits
  to different sections. The last completed write to the same section wins.
- `get_page` and `get_knowledge_object` return `revision`. Pass it as `expected_revision` to
  `update_page` (also REST `PUT /api/pages/{slug}`) to detect stale full-page edits. Omission preserves
  the legacy last-writer-wins behavior. Metadata edits automatically check the revision they read.
- `create_page` accepts `idempotency_key` (also REST `POST /api/pages`). Keys are workspace-scoped;
  identical retries return the same page, while changed payloads or a trashed target return conflict.
  Use a stable conversation/event ID, not a timestamp generated again on every retry.
- MCP errors keep the original human-readable text and add
  `structuredContent.error` with `code` and `message`. Codes include `FORBIDDEN`, `CONFLICT`,
  `NOT_FOUND` and `INVALID_ARGUMENT`. Successful object results also provide `structuredContent`.
- New content revisions are recorded in PostgreSQL in the same transaction as the content change,
  with `user:<id>` or `token:<id>` provenance. Existing pages receive a baseline marked `legacy:user:`;
  this does not invent earlier history. Git remains a separate Markdown backup: `git_status` is
  `synced` only when its snapshot matches the current revision, otherwise `pending`.

### Token capabilities

`POST /api/tokens` accepts an optional `policy`. Existing tokens and tokens created without a policy
retain their original membership-based access. An empty grant list denies all knowledge access.
A restricted token cannot mint tokens, change accounts, manage memberships or administer workspaces.
Bearer credentials take precedence over session cookies when both are supplied.

```json
{
  "name": "agent_rpi",
  "policy": {
    "grants": [
      {"workspace": "agente", "actions": ["read", "create", "update", "relate"]},
      {"workspace": "personal", "actions": ["read"]},
      {"workspace": "work", "actions": ["read"]},
      {"workspace": "work", "actions": ["update"], "pages": ["inbox"]},
      {"workspace": "bussisnes", "actions": ["read"]},
      {"workspace": "bussisnes", "actions": ["update"], "pages": ["inbox"]}
    ]
  }
}
```

Actions are `read`, `create`, `update`, `delete` and `relate`. Grants add permissions and never
bypass workspace membership. `pages` restricts an action to exact slugs; creation is workspace-wide.
Tools exposing neighbors or workspace-wide information require workspace-wide read access. Capability
restrictions apply equally to REST and MCP. Human confirmation remains the calling agent's responsibility.

For `agent_rpi`, migrate to one idempotent `Conversation` object and `Service` objects linked by
`affects`; do not copy conversation summaries into each service. Preserve source IDs and label LLM
summaries as unverified summaries. Archive conversations explicitly instead of deleting their evidence.
Retrieve with `query_knowledge_context`, and follow `next_offset` when reading long pages. Existing
clients continue to work, but must adopt these operations to gain this behavior. Deploy Doction first,
then update clients and issue separate restricted tokens for infra, Claude Code and Codex. No client
configuration or running deployment is changed by this server update.
