# SPEC — doction v2 model

Design document. **Nothing here is implemented yet.**

## Problem

doction is drifting from "wiki" towards "personal knowledge system": a tree of pages that a
human, a CLI and an agent all address, fed by capture from several clients. The current model
mostly supports that already — but one thing blocks it, and it is not the thing that looked
like the blocker.

## What already exists (and what the earlier sketch got wrong)

The prior design note assumed the page tree was the work to be done. It is already there:

- `pages.parent_id` is a self-referencing FK with arbitrary depth. `workspace → page → page →
  page` is implemented; there is no artificial "page vs subpage" distinction to remove.
- The git repo is **flat**: `git_repo.py` writes `{workspace_slug}/{page_slug}.md`. Hierarchy
  lives only in Postgres.

That second fact makes the operation the sketch called "de primera clase" the cheapest in the
system: **moving a page is one `UPDATE pages SET parent_id`**. No file moves, no commit, no
slug change. It is missing from the API, not hard.

`type: memo`-style filtering also already works: `meta.page_type()` reads frontmatter into
`page_meta.type`, and `db.extract_pages()` returns a filtered, `updated_at DESC` list. An Inbox
needs no schema.

## The actual problem: the slug does four jobs

`slug` is simultaneously:

1. the URL (`/api/pages/{slug}` — all 13 page routes),
2. the filename in git (`{ws}/{slug}.md`, hence `UNIQUE(workspace_id, slug)`),
3. the wikilink target (`page_links.dst_slug` is **TEXT, not a foreign key**),
4. the identity used by every read and write in `db.py`.

Today this is harmless, because **there is no rename**. `update_page` changes title and content
and its docstring says so explicitly: *"manteniendo el slug estable"*. Nothing in the codebase
issues `UPDATE page_links`, and nothing needs to.

The moment a page can be renamed, job 3 breaks silently: every `[[old-slug]]` in every other
page stops resolving, with no error anywhere. That is the coupling v2 has to break.

## Decisions

### Git stays flat

Nesting files to mirror the tree was considered and rejected. Workspaces already partition the
namespace — `homelab/mikrotik` and `work/mikrotik` coexist today — so collisions only occur
inside one workspace, where the existing `-2` suffix resolves them. Nesting would turn every
move into a `git mv`, require migrating existing files, and make `--follow` the only way to
read history. The cost is real and the benefit is cosmetic.

**Consequence:** `slug` remains unique per workspace, and moving a page remains free.

### Rename creates an alias; it never rewrites content

The obvious implementation of rename — rewriting `[[old]]` to `[[new]]` across every linking
page — is wrong here. It would produce git commits on pages the user did not edit, polluting a
history whose whole value is that it reflects human edits.

Instead, **old slugs stay resolvable forever**:

```sql
CREATE TABLE IF NOT EXISTS page_aliases (
    workspace_id BIGINT NOT NULL,
    slug         TEXT   NOT NULL,
    page_id      BIGINT NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
    created_at   TEXT   NOT NULL,
    PRIMARY KEY (workspace_id, slug)
);
```

`get_page(slug, workspace_id)` falls back to `page_aliases` on a miss. Existing markdown keeps
working untouched, and the alias table doubles as the rename audit trail.

An alias must not collide with a live slug: the uniqueness check on create/rename has to
consider `pages.slug` **and** `page_aliases.slug` together.

### Links resolve to an id, keeping the slug as a fallback

```sql
ALTER TABLE page_links ADD COLUMN IF NOT EXISTS dst_page_id BIGINT
    REFERENCES pages(id) ON DELETE SET NULL;
```

`dst_slug` stays — it is the only representation a **broken** link has, and broken links are a
feature (`graph.link_insights` reports them). The rules:

- On save, `db._index_page_meta()` resolves each wikilink to `dst_page_id`, leaving it `NULL`
  when the target does not exist yet.
- **On page create**, resolve pending forward references:
  `UPDATE page_links SET dst_page_id = :new_id WHERE dst_page_id IS NULL AND dst_slug = :slug
  AND workspace_id = :ws`. Without this, a link written before its target exists stays broken
  forever.
- On rename, `dst_page_id` needs no maintenance — that is the point.
- `db.backlinks()` switches to `dst_page_id`, with `dst_slug` as fallback for unresolved ones.

### Capture is `POST /api/pages`, not a new endpoint

The capture entry point the sketch wants already exists; what blocks it is that `title` is
mandatory and generates the slug. `db.create_page` forces `title.strip() or "Untitled"`, so a
hundred untitled notes become `untitled`, `untitled-2`, … `untitled-100`.

v2 makes `title` optional:

- title omitted → derived from the first non-empty line of `content`, trimmed;
- slug → a timestamp (`nota-YYYYMMDD-HHMMSS`), using the `requested_slug` parameter
  `create_page` already accepts.

No new route, no new auth surface, no second way to write a page. Any client — an iOS Shortcut,
the CLI, a bot — is then just an HTTP caller with a PAT.

### Inbox is a page, not a type

No `kind` column, no special-casing. An Inbox is a normal page used as a parent, and captured
notes carry `type: memo` in frontmatter, which `page_meta.type` and `extract_pages()` already
index. Triage (move out of Inbox into the tree) is exactly `move_page`.

**One thing this needs that does not exist:** `db.list_pages_tree()` returns *every* page in the
workspace, unpaginated, and the sidebar renders all of it. A few thousand memos make it
unusable. v2 adds a paginated, `created_at DESC` feed endpoint and keeps `type: memo` pages out
of the tree query.

## Contract changes

New operations, in REST and MCP alike (MCP is 3 lines per tool: a handler, a `TOOLS` schema
entry, a `TOOL_HANDLERS` key):

| Operation | REST | Notes |
|---|---|---|
| move | `POST /api/pages/{slug}/move` `{parent_slug\|null}` | one UPDATE; reject cycles |
| rename | `POST /api/pages/{slug}/rename` `{slug}` | writes `page_aliases`, `git mv` |
| delete | already exists | expose as an MCP tool too |
| children | `GET /api/pages/{slug}/children` | direct children only |
| feed | `GET /api/notes?limit&before` | paginated, `created_at DESC` |

**Addressing stays slug-based.** Dual `/api/pages/id/{id}` routes were considered and rejected:
with aliases in place, a slug is already a stable handle, and doubling 13 routes plus 17 MCP
tools buys little. Identity is `pages.id` internally, as it already is.

**Cycle check on move** is not optional: `parent_id` is a self-FK with no constraint against
loops, and `list_pages_tree`'s DFS would hang. Walk ancestors before writing.

## Migration

Everything is additive and fits the existing idempotent-DDL model in `SCHEMA_STATEMENTS` — one
`CREATE TABLE IF NOT EXISTS`, one `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`. No migration
ladder, no Alembic, consistent with `db.py` today.

Backfilling `dst_page_id` for existing rows is a single `UPDATE ... FROM pages` matching on
`(workspace_id, dst_slug)`. Rows that do not match are genuinely broken links and stay `NULL`.

Nothing in the existing contract changes meaning, so old clients and the current frontend keep
working untouched.

## Out of scope

- **Outbound webhooks.** doction makes no runtime HTTP calls at all (`httpx` is dev-only), has
  no hooks, no queue and no scheduler. Adding events is a separate, larger decision; the natural
  seams when it comes are `db._index_page_meta()` and `git_repo.commit_and_record()`, and
  `embeddings.enrichment_worker()` is the in-process async worker pattern to copy.
- **Token scopes.** A PAT is the full user. A capture-only credential would be real new work in
  `auth.py` and the middleware.
- **PWA / offline capture.** Making doction installable on a phone is a frontend concern, not a
  model one.
- **Retiring Memos.** Decide that after capture works here, not before.

## Verification

The gate is unchanged and self-contained: `docker build --target test` runs ruff, ruff format,
pyright and pytest against its own Postgres. Frontend: `npm run check`.

New tests, in the style of `tests/test_app.py` and `tests/test_meta.py`:

- move: reparents; rejects a cycle; a page moved out of Inbox keeps its slug and its history.
- rename: old slug still resolves through the alias; backlinks survive; a wikilink written
  before the target existed resolves once the target is created.
- alias collision: creating a page whose slug matches an existing alias is rejected.
- capture: no title derives one from the first line; a hundred untitled notes produce a hundred
  distinct slugs.
- feed: paginates, orders by `created_at DESC`, and `type: memo` pages are absent from
  `list_pages_tree`.

End to end on the Pi: capture from the CLI with a PAT, see it in the feed, move it into the
tree, rename it, and confirm an old wikilink still resolves and the git history is intact.
