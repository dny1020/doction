# Agents and MCP

doction speaks MCP (Model Context Protocol) natively at `POST /api/mcp`: JSON-RPC 2.0,
stateless, no SDK. 38 tools over the same data the REST API and the web UI see.

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

### Required relationships for new typed pages

Agents receive the rules through MCP `initialize` and the descriptions of `create_page`,
`get_page`, `read_page_raw` and `relate_knowledge`. Page reads also include a bounded
`graph_context` containing readable typed edges, the applicable requirement, whether it is
enforced, and guidance for retrieving related evidence. Reading never creates relationships.
Instructions guide clients; validation is enforced by the server through REST and MCP.

New pages declaring `type: Decision` require at least one outgoing `belongs_to` edge to an
existing `Project`. New pages declaring `type: Incident` require at least one outgoing
`affects` edge to an existing `Service`. These four type names are matched without case
sensitivity for graph validation. Other types and pages without a type remain unrestricted.
Subpage nesting, tags and wikilinks do not satisfy these requirements.

Create the target first, then use `create_page` with a `relations` array:

```json
{
  "title": "Use PostgreSQL",
  "content": "---\ntype: Decision\n---\nWe selected PostgreSQL for this project.",
  "idempotency_key": "decision:postgresql:project-x",
  "relations": [
    {"kind": "belongs_to", "target": "project-x", "evidence": "Architecture review"}
  ]
}
```

Each relation has `kind`, an existing target slug or alias in the same workspace, and optional
`evidence`. The REST equivalent is `POST /api/pages` with the same JSON. Page creation, relations,
metadata, revision and event queue commit together or roll back together. Relations participate in
idempotency matching; their order does not matter. An explicit `relate` token grant and read access
to each target are required in addition to creation permission.

A missing mandatory relationship produces an actionable `RELATION_REQUIRED` MCP error. REST writes
return a client error with the explanation. No incomplete new typed page is left behind. For an
existing untyped page, call `relate_knowledge` before promoting it with `set_knowledge_metadata`
or a Markdown edit. Existing typed pages from before this feature remain editable without a forced
migration; their reads show `enforced: false`. Changing a legacy page to a different constrained type
activates the contract. Merely reading a legacy page never modifies it.

For enforced pages, removing the last qualifying relation, trashing its last qualifying target,
or changing that target's type is rejected. Add a replacement relation before removing the old one.
Restoring a trashed enforced page checks its requirements again. Ordinary page creation retains its
existing response shape; read the result with `get_page` or `get_knowledge_object` to inspect the graph.

The server cannot force a client to follow instructions, declare a type or consult evidence. It can
require valid relationships for the declared constrained types and make the next retrieval step clear.

## Reminders

Reminders are workspace records with a title, Markdown notes, a responsible member and a schedule.
They can link to multiple documents in that workspace by stable page ID. They do not create pages
in the wiki tree or add graph nodes. Renaming a linked document preserves the relationship; a trashed
document is shown as unavailable. Permanent document deletion removes its current link, retaining
the reminder and its recorded revisions.

| Tool | Purpose |
| --- | --- |
| `create_reminder` | Create in `workspace` with `title`, optional `notes`, exactly one of `due_date` or `due_at`, `timezone`, optional `assignee_id`, `page_slugs` and `idempotency_key` |
| `list_reminders` | Query authorized workspaces with exact status/date filters; no search text required |
| `update_reminder` | Pass `workspace`, `id`, `expected_revision` and changed fields; supports `pending`, `completed`, `cancelled`, reassignment and rescheduling |
| `get_reminder_history` | Read recorded revisions with previous schedules, status and actor; accepts `workspace`, `id`, `limit`, `offset` |

For example, after identifying the relevant backup document:

```json
{
  "workspace": "personal",
  "title": "Review backup recovery",
  "notes": "Follow the recovery steps and record the result.",
  "due_at": "2026-12-01T09:00:00",
  "timezone": "America/Bogota",
  "page_slugs": ["backup-runbook"],
  "idempotency_key": "backup-review:2026-12-01"
}
```

Dates use `due_date: "2026-12-01"` for an all-day reminder, or `due_at` for an instant. A local time
without an offset is interpreted in the supplied IANA timezone. Ambiguous or nonexistent DST clock
times are rejected; provide an explicit offset to disambiguate. The default timezone is
`America/Bogota`; clients should supply the user's intended zone. UTC instants are stored together
with that zone. A date-only reminder is overdue only on the following local day. A timed reminder
is overdue after its instant. Pending items are grouped into disjoint `overdue`, `today`, `upcoming`
buckets, computed at query time; no process needs to run at midnight.

`list_reminders` defaults to `status: pending`, `scope: mine` (assigned to the authenticated user)
and all authorized workspaces. Select one workspace, or use `workspace: all`; `scope: workspace`
includes other responsible members and unassigned records. Use `period: overdue|today|upcoming|all`,
`page_slug` with one workspace for document-related pending actions, and `limit`/`offset` for paging.
Results include `total`, `next_offset`, workspace, document links and revision. Do not use semantic
retrieval to answer whether the user has pending reminders.

Read access is workspace-wide. Creation requires `read` + `create`; updates require `read` + `update`.
These checks apply to REST and MCP and never bypass membership. Responsibility defaults to the
calling user, and can be assigned only to a member of the workspace. Agents using a separate account
must explicitly assign the human's user ID when appropriate. Page-restricted grants do not grant
workspace-wide reminder access.

The REST surface is `GET /api/reminders`, `POST /api/reminders?workspace=<slug>`,
`PUT /api/reminders/{id}?workspace=<slug>` and
`GET /api/reminders/{id}/history?workspace=<slug>`. Writes accept the same fields as MCP, excluding
`workspace`/`id` from the JSON body. Changing scheduling mode requires clearing the other field with
`null`. Revision mismatches return conflict; a successful creation retry returns its original response.
Content, document links, recorded revision and change event are saved atomically.

The UI lives at `/app/w/<workspace>/reminders`, with workspace/all-workspaces filters and a separate
responsible-person filter. A document shows its pending reminders and a create action that preselects
that document. Reminder notes support Markdown. Completing, cancelling, reopening and changing dates
do not erase recorded history.

This version stores and retrieves reminders; it does not send scheduled notifications or implement
recurrence. Existing webhooks can receive `reminder.created`/`reminder.updated` change events, which
are not due-time alerts. No action is executed when a reminder becomes overdue.
