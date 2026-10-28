# Writing pages

Everything in doction is a page of markdown. The server stores it raw, renders nothing, and
commits every save to git. This page covers creating pages, organising them, tagging them, changing
them and getting them back.

Examples use `$DOCTION` as the base URL and a personal access token in `$TOKEN`. See
[Agents and MCP](mcp.md#authentication) for how to get one.

## Creating a page

```bash
curl -s -X POST $DOCTION/api/pages \
  -H "authorization: Bearer $TOKEN" -H 'content-type: application/json' \
  -d '{"title": "SIP Trunk Runbook", "content": "# SIP Trunk\n\nSteps here.\n"}'
# → {"slug": "sip-trunk-runbook", "title": "SIP Trunk Runbook"}
```

The slug comes from the title, lowercased with spaces turned into hyphens. It is the page's
identity everywhere: the URL, the API path, the filename in the git repo and the target of a
wikilink. Pass `slug` explicitly to choose it yourself.

`title` is optional. Leave it out and the title is taken from the first line of the content,
which is what makes a one-line capture worth saving without inventing a heading for it.

Slugs are unique per workspace. Workspace slugs are unique globally, because a workspace slug is
also a directory name in the git repo.

## Organising: the page tree

A page becomes a subpage by naming its parent at creation:

```bash
curl -s -X POST $DOCTION/api/pages -H "authorization: Bearer $TOKEN" \
  -H 'content-type: application/json' \
  -d '{"title": "Dialplan notes", "content": "...", "parent_slug": "sip-trunk-runbook"}'
```

`GET /api/pages` returns the whole tree as a flat list, each entry carrying `slug`, `title` and
`depth`. It is flat on purpose: the client draws the indentation from `depth`, and a flat list
costs one query no matter how deep the tree is. `GET /api/pages/{slug}/children` returns one
level.

Reparenting later is a move. Passing `null` moves the page to the top level:

```bash
curl -s -X POST $DOCTION/api/pages/dialplan-notes/move \
  -H "authorization: Bearer $TOKEN" -H 'content-type: application/json' \
  -d '{"parent_slug": null}'
```

A move is cheap and does not rewrite anything on disk. The git repo is flat, so the hierarchy is
a parent pointer in the database rather than a directory layout.

## Changing a page

`PUT /api/pages/{slug}` is a partial update. Send `content`, `title`, or both, and what you leave
out is left alone:

```bash
# retitle without touching the body
curl -s -X PUT $DOCTION/api/pages/sip-trunk-runbook \
  -H "authorization: Bearer $TOKEN" -H 'content-type: application/json' \
  -d '{"title": "SIP Trunk Runbook v2"}'
```

Changing the *slug* is a rename, and it is a different operation because it changes the page's
identity:

```bash
curl -s -X POST $DOCTION/api/pages/sip-trunk-runbook/rename \
  -H "authorization: Bearer $TOKEN" -H 'content-type: application/json' \
  -d '{"slug": "sip-trunk-runbook-v2"}'
```

A rename leaves an alias behind, so the old slug keeps resolving and links written against it do
not break. Verified: after the rename above, `GET /api/pages/sip-trunk-runbook` still answers
200.

A page's content is capped at 1 MiB. Over that the save is refused with 400 and a message naming
both sizes:

```
page content is 1,048,586 bytes, over the 1,048,576-byte limit
```

The limit is enforced in the storage layer rather than at the HTTP edge, so it applies equally to
the REST API and to an agent writing through MCP.

## Tags

A page can carry tags two ways: inline in the text, or in a metadata block at the top. Both are
parsed on every save into the same place, so a tag written either way behaves the same
afterwards.

### Inline tags

Write `#tag` anywhere in the body:

```markdown
Notes on #kamailio and #sip-trunk.
```

The rules, all measured:

| Written | Becomes | Why |
| --- | --- | --- |
| `#Kamailio` | `kamailio` | tags are lowercased |
| `#sip-trunk` | `sip-trunk` | hyphens and underscores are part of a tag |
| `#2026` | nothing | a tag must start with a letter |
| `` `#incode` `` | nothing | inline code is removed before the scan |
| `#infence` inside ``` fences | nothing | fenced blocks are removed too |

The exclusion of code is the reason a shell comment, a CSS colour or a C preprocessor directive
in a fenced block does not become a tag. It is also why a page documenting tags can show
examples.

### The metadata block

A page may open with a block delimited by `---`:

```markdown
---
title: SIP Trunk Runbook
tags: [kamailio, sip]
---

The body starts here.
```

**This block is not YAML.** It is a small dependency-free parser, and it understands exactly two
shapes: `key: value`, and an inline list `key: [a, b]`. That distinction is the single most
common way to lose a tag without being told, so it is worth stating as a measurement:

```
---                           ---
tags:                         tags: [kamailio, sip]
  - kamailio                  ---
  - sip
---                           → tags: kamailio, sip        ✓

→ tags: (none)    ✗
```

The block-list form is valid YAML and is silently ignored. Nothing warns, the save succeeds, and
the page ends up with no tags. If you are used to Jekyll, Hugo or Obsidian, this is the one place
doction will surprise you, and the fix is to write the list inline.

A second consequence of the same parse: the lines that were not understood stay where they are.
`GET /api/pages/{slug}/raw` on a page with a block list shows the block exactly as written, list
items included.

The block is part of the page content. It is stored with the page and it is indexed for search,
so a word that appears only in the metadata block is still findable.

### Finding pages by tag

Tags are stored per page and are what the tag filters in the interface are built from. Note that
**search has no field syntax**: `tag:voip` in a query is not a tag filter, it is two ordinary
terms, one of which is the literal word "tag". See [searching](search.md#there-is-no-query-syntax).

### Suggested tags

`GET /api/pages/{slug}/suggest-tags` proposes tags by comparing the page's terms against the rest
of the workspace, using TF-IDF. It needs no embeddings and no model, so it works on any instance.

Every suggestion response carries a `mode` field saying how it was produced, which is the honest
answer to "why did it suggest that": a suggestion from term statistics and one from a semantic
model are not the same claim.

## History

Every save is a git commit, made silently and in the background. A git failure never fails a
save, which means history is best-effort by design: the page is the source of truth and the repo
is the record.

```bash
curl -s $DOCTION/api/pages/sip-trunk-runbook/history -H "authorization: Bearer $TOKEN"
# → [{"sha": "202540c", "timestamp": "...", "author": "you@example.org",
#     "message": "Save: SIP Trunk Runbook"}, ...]
```

From a `sha` you can read the content as it was, diff it against its parent, or put it back:

| Operation | What it gives you |
| --- | --- |
| `GET /api/pages/{slug}/history/{sha}` | the content at that commit |
| `GET /api/pages/{slug}/history/{sha}/diff` | the change that commit made |
| `POST /api/pages/{slug}/restore/{sha}` | that content as a new save, so the restore is itself in history |

## Deleting, and getting it back

`DELETE /api/pages/{slug}` answers 204 and the page stops resolving: a subsequent read is 404.
The row is not gone, it is marked deleted, and the page is in the trash:

| Operation | What it does |
| --- | --- |
| `GET /api/trash` | lists deleted pages |
| `POST /api/trash/{slug}/restore` | brings one back |
| `POST /api/trash/{slug}/purge` | deletes it for real, 204 |

So a delete is recoverable and a purge is not. The git history survives a purge, because the
commits are in the repo rather than in the database.

## Getting everything out

`GET /api/workspaces/{slug}/export` returns the workspace as a zip of markdown files, one per
page. It is the answer to "how do I leave", and it needs no tooling beyond `unzip`.

`GET /api/pages/{slug}/raw` returns one page as `text/plain` markdown, exactly as stored,
including the metadata block if the page has one.

## Where to go next

- [Links and the graph](links-and-graph.md) for `[[wikilinks]]` and what a broken link means
- [Searching](search.md) for finding any of it again
