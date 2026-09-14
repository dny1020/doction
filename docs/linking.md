# Linking pages

A wikilink is how one page points at another. Two forms:

```markdown
[[sip-trunk-runbook]]                    the slug, shown as-is
[[sip-trunk-runbook|the runbook]]        the slug, shown as "the runbook"
```

Links are parsed on every save into a table of edges, which is what backlinks, the graph and the
workspace insights are built from. Nothing about linking happens at read time, so the graph is
always as current as the last save.

## What counts as a target

The target is turned into a slug before it is looked up. That means a **title works as a
target**, because a title becomes a slug the same way:

```markdown
[[Markdown Cheatsheet]]     resolves to markdown-cheatsheet
```

Two links that reduce to the same slug are one edge. `[[SIP Trunk Runbook]]` and
`[[sip-trunk-runbook]]` on the same page produce a single link.

A target is also looked up among the aliases a rename leaves behind, so a link written against a
page's old slug keeps resolving after the page is renamed. Verified: a page renamed from
`links-demo` is still reached by `[[links-demo]]`.

Two limits, both measured:

- A target cannot contain `[`. `[[a[b]]` produces no link at all.
- A target is at most 200 characters, and a label at most 200. Longer produces no link.

Neither is cosmetic. Both come from the pattern that finds wikilinks: without them, a page of
unclosed `[[` sequences made the scan quadratic, and 24 KB of it cost 7.9 seconds of CPU inside
the save path. The reasoning is in `app/meta.py` and in the archived change that fixed it.

Links inside code are not links. Both an inline span and a fenced block are removed before the
scan, so `` `[[example]]` `` in a page about wikilinks stays an example.

## A broken link is information, not an error

Linking to a page that does not exist is allowed and is recorded. The edge is stored with its
target slug and no resolved page, which is the only representation a broken link has.

Two things follow, and the second is the useful one:

1. `GET /api/insights` reports `broken_links`, and `GET /api/graph` marks the edge
   `"broken": true`. So you can find every dangling link in a workspace.
2. **The link heals by itself when the target is created.** Measured: a page linking to
   `[[does-not-exist]]` had an unresolved edge; creating a page with that slug resolved the
   existing edge with no second save of the linking page.

That makes it reasonable to write links to pages you have not written yet. It is the wiki way
round: the link is the note that the page should exist.

## Backlinks and neighbourhood

`GET /api/pages/{slug}/view` returns what the reading view needs in one request, `backlinks`
included, so opening a page tells you what points at it without a second call.

For walking further out, `GET /api/graph` returns the drawable graph and the MCP tool
`get_linked_knowledge` walks the link graph in both directions to a bounded depth. See
[the graph](graph.md) for the shape of the graph response and its limits.

## What the reader sees

Wikilinks are rendered by the client, not the server. The server stores and serves raw markdown
and renders nothing, so a wikilink in a `raw` response is still `[[text]]`.

The client turns them into anchors with a markdown-it inline rule that emits tokens rather than
building an HTML string. That is deliberate: splicing a target taken from a document into an
`href` is how the stored cross-site scripting bug in this project's first hardening change
happened. If you are writing your own client, take the same care.

## Where to go next

- [Tags and metadata](tags-and-metadata.md), the other way pages group together
- [The graph](graph.md), which is these links drawn
- [Writing pages](writing-pages.md) for slugs, renames and aliases
