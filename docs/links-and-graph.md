# Links and the graph

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
[the graph](#the-graph) for the shape of the graph response and its limits.

## What the reader sees

Wikilinks are rendered by the client, not the server. The server stores and serves raw markdown
and renders nothing, so a wikilink in a `raw` response is still `[[text]]`.

The client turns them into anchors with a markdown-it inline rule that emits tokens rather than
building an HTML string. That is deliberate: splicing a target taken from a document into an
`href` is how the stored cross-site scripting bug in this project's first hardening change
happened. If you are writing your own client, take the same care.

## The graph

Every wikilink in a workspace is an edge, and `GET /api/graph` serves the whole thing as
something drawable:

```bash
curl -s -H "authorization: Bearer $TOKEN" $DOCTION/api/graph
```

```json
{
  "nodes": [{"slug": "welcome", "title": "Welcome", "incoming": 0, "outgoing": 0, "orphan": true}],
  "edges": [{"source": "links-demo", "target": "does-not-exist", "broken": true}],
  "pages": 15,
  "truncated": false
}
```

Four things worth knowing about that payload:

- `orphan` means no links in and none out. On a young workspace most pages are orphans, which is
  accurate rather than a defect: measured on a 15-page workspace, 10 were orphans.
- `broken` on an edge means the target does not exist yet. The edge is still in the graph,
  because [a broken link is information](#a-broken-link-is-information-not-an-error).
- `pages` is the workspace's page count, so you can tell whether you are looking at all of it.
- `truncated` says whether you are not. Above 300 nodes the response is trimmed to the
  highest-PageRank subgraph, so a large workspace returns its most connected part rather than a
  payload nobody can draw or read.

The trimming is by PageRank rather than by recency or alphabet because the question a graph
answers is which pages matter and how they connect. Dropping the periphery keeps that readable;
dropping the middle would not.

### The graph view

The interface draws this at `/w/<workspace>/graph`, as SVG the application writes itself rather
than through a charting library. Every colour is a design token, which is what makes both themes
work without a second palette.

Each label sits centred under its node, and a title longer than 24 characters is elided. Up to
40 nodes every page is labelled; above that, only pages with links are. The layout sizes itself
to the titles it has to place, so labels do not overlap — `frontend/src/graphLayout.test.js`
settles the simulation and fails if any two label boxes intersect.

### Reading the graph without drawing it

`GET /api/insights` answers the same questions as prose instead of geometry, and it is usually
the more useful call:

| Field | What it tells you |
| --- | --- |
| `central`, `authorities`, `hubs` | which pages the link structure points at |
| `orphans` | pages nothing links to and which link nowhere |
| `broken_links` | every link whose target does not exist |
| `duplicates` | pages that look like near-copies of each other |
| `clusters` | groups the link structure suggests |

For an agent walking outward from one page, the MCP tool `get_linked_knowledge` does a
breadth-first walk of the link graph in both directions, bounded to depth 3 and 100 nodes. Those
bounds exist because an unbounded walk of a well-linked wiki returns the wiki.

The graph maths is plain numpy, no graph library: PageRank, a deterministic k-means for the
clusters, and the link statistics above. That keeps the dependency list short and the results
reproducible between runs.

## Where to go next

- [Writing pages](writing-pages.md) for slugs, renames, aliases and tags
- [Agents and MCP](mcp.md) for `get_linked_knowledge` and the other tools
