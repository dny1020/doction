# The graph

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
  because [a broken link is information](linking.md#a-broken-link-is-information-not-an-error).
- `pages` is the workspace's page count, so you can tell whether you are looking at all of it.
- `truncated` says whether you are not. Above 300 nodes the response is trimmed to the
  highest-PageRank subgraph, so a large workspace returns its most connected part rather than a
  payload nobody can draw or read.

The trimming is by PageRank rather than by recency or alphabet because the question a graph
answers is which pages matter and how they connect. Dropping the periphery keeps that readable;
dropping the middle would not.

## The graph view

The interface draws this at `/w/<workspace>/graph`, as SVG the application writes itself rather
than through a charting library. Every colour is a design token, which is what makes both themes
work without a second palette.

**The layout is currently poor.** The force simulation collapses nodes toward the centre with
labels overlapping, and on a small workspace the labels are already hard to read. It is a known
defect with an entry on the [roadmap](../ROADMAP.md) and an open issue, and it is the reason
there is no graph screenshot in the project README. The data is correct; the drawing is not.

## Reading the graph without drawing it

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

- [Linking pages](linking.md) for the links this is made of
- [Agents and MCP](mcp.md) for `get_linked_knowledge` and the other tools
