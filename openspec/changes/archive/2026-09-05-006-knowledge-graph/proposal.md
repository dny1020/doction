## Why

doction already has a knowledge graph. It parses `[[wikilinks]]` on every save, stores every edge
in `page_links` with the destination resolved to a page id, keeps the edge alive across renames,
preserves unresolved targets because a broken link is information, and computes PageRank, orphans,
hubs, authorities and broken links over the whole workspace.

None of that is visible. The graph is a private fact of the database.

**A wikilink is not a link.** `[[kamailio-dispatcher]]` typed into a page renders as those literal
characters, brackets included. The edge is in the database; the reader gets text. This is the whole
of the gap: writing a link and following a link are the same gesture in a wiki, and today only the
first half works. Every other item below is downstream of it.

**The analysis has no reader.** `GET /api/insights` returns central pages, orphans, hubs,
authorities and every broken wikilink with the pages that point at it. No screen in the application
calls it. A broken link is reported to nobody, which means it is never fixed, which means the graph
decays quietly while looking healthy.

**An agent can walk one step and then stops.** `list_backlinks` answers who points here.
`related_pages` answers who shares tags. Neither answers what an exploring agent actually asks:
starting here, what is two steps away and how did I get there. The traversal has to happen in the
agent's head, one round trip per hop, and the agent has no way to know when it has left the
neighbourhood.

**There is no view of the whole.** A workspace is a tree in the sidebar and a list in search. The
shape of the knowledge — what clusters, what is isolated, what everything depends on — has no
representation, even though the data to draw it has been sitting in `workspace_links()` all along.

## What Changes

**Wikilinks become links, as a parser rule.** The client's markdown-it pipeline gains an inline
rule for `[[target]]` and `[[target|text]]` that emits a real anchor to `/w/<ws>/p/<target>`, and a
distinct class when the target does not exist in the workspace. A link to nothing looks different
from a link to something, in the reading view and in the editor preview alike.

**Mentions get provenance.** The reading view already lists backlinks. It gains the sentence each
mention sits in, so the reader can tell a passing reference from a real dependency without opening
the other page.

**Broken links surface where they can be fixed.** The insights the server already computes reach
two places: a count on the page that owns the broken link, and a workspace-level list.

**A graph view.** A new route `/w/<ws>/graph`, a `GET /api/workspaces/<ws>/graph` returning nodes
and edges, and a force-directed rendering in plain SVG. Nodes are pages, sized by incoming links;
edges are wikilinks; a broken edge ends in a marker rather than a node. Clicking a node opens the
page.

**One new MCP tool, not two.** `get_linked_knowledge(slug, depth=1)` returns the neighbourhood as a
map: each reachable page, its distance, and the path that reached it. `list_backlinks` already
answers the backlinks question and keeps its name.

## Deviations from the brief, and why

Three points of the brief describe work that is already done or that would make the product worse.
Each is called out here so the decision is yours, not mine.

**The relational engine exists.** `page_links` is already `(src_page_id, dst_slug, workspace_id,
dst_page_id)` with `ON DELETE CASCADE`, two indexes and rename handling — a superset of the table
in the brief, which omits the resolved id and would lose the distinction between a broken link and
a link to a page that moved. `meta.py` already parses both wikilink forms and strips code fences
first, and `db.create_page`/`update_page` already repopulate the edges on every save. Phase 1 of
the brief is therefore a **verification and test-hardening phase**, not construction. Building the
proposed table would be a regression.

**AST extraction belongs on the client, not the server.** The brief asks for AST-level extraction
during save. The server has no markdown AST and adding one means a new dependency for a parser that
already handles the only real ambiguity, which is code. Where an AST genuinely matters is the
client: turning `[[slug]]` into an anchor by string-replacing rendered HTML would inject markup
into sanitized output, which is the exact shape of the stored XSS closed in change 001. A
markdown-it inline rule produces a token, the sanitizer sees a normal anchor, and no HTML is ever
assembled by hand. So the AST requirement is honoured — on the side where it buys safety.

**`get_related_knowledge` collides with a tool that exists.** `related_pages` already returns
neighbours by shared tags. A second tool whose name is a synonym, returning neighbours by a
different relation, is a surface an agent has to guess at. The tool is proposed as
`get_linked_knowledge`, which says which relation it traverses, and the two remain distinct
because they answer different questions: tags say *this is about the same thing*, links say *this
one refers to that one*. Say the word and it ships under the brief's name.

## Impact

- **New capability spec**: `knowledge-graph`.
- **Modified specs**: `markdown-rendering` (the wikilink rule and its sanitization),
  `mcp-tools` (the traversal tool), `navigation` (the graph route), `self-hosting` (one more
  vendored asset).
- **Code**: `app/main.py`, `app/mcp.py`, `app/graph.py`, `frontend/src/markdown.js`,
  `frontend/src/pages/Reader.jsx`, a new graph page and a new vendored library.
  `app/meta.py` and `app/db.py` gain tests, not behaviour.
- **Air-gap**: one addition to `app/static/vendor/`. The candidate is `d3-force` alone, about 30 KB,
  with the drawing done in plain SVG rather than by the library. Two reasons over `vis-network` or
  `cytoscape`: those ship their own canvas renderer and their own theme system, which would have to
  be bridged to the design tokens the way mermaid's was, whereas an SVG the application draws itself
  inherits the tokens through ordinary CSS and gets dark mode for free. And 30 KB against the 3.2 MB
  mermaid already in the tree is not a budget question.
- **No new Python dependency. No model, no generation, no inference.** The graph is arithmetic over
  rows that already exist.

## Out of scope

- `[[` autocompletion in the editor. It is the natural next step and it is a different problem —
  input affordance, not the graph.
- Transitive or inferred edges. An edge exists because someone wrote it.
- Any ranking of pages by graph position inside retrieval. Changing what search returns is measured
  work against the `evals/` harness and belongs in its own change.
