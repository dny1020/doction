# Tasks

## 1. Phase 1 — Verify the relational engine that already exists

The engine is built. This phase proves it, and fixes what the proof finds.

- [x] 1.1 Property test over `meta.wikilinks()`: both forms (`[[a]]`, `[[a|text]]`), a link inside
      a fenced block and inside inline code are ignored, a malformed `[[` is not a link, and the
      same target twice yields one edge, because the graph has edges, not mentions.
- [x] 1.2 Test that saving a page replaces its outgoing edges rather than accumulating them, and
      that deleting a page removes its edges but not the edges pointing at it.
- [x] 1.3 Test that renaming a page keeps every inbound edge resolved, and that a link to a
      non-existent slug stays unresolved and becomes resolved when that page is later created.
- [x] 1.4 Confirm the `page_links` indexes serve both directions. Asserted against
      `pg_indexes` rather than by reading a plan: the plan on a test-sized table picks a
      sequential scan whatever the indexes say, so it would have proved nothing.
- [x] 1.5 Do **not** create the table from the brief. Record in `design.md` why the existing shape
      is a superset, so the next reader does not re-propose it.

## 2. Phase 2 — Wikilinks become links, mentions gain provenance

- [x] 2.1 Add a markdown-it inline rule for `[[target]]` and `[[target|text]]` in
      `frontend/src/markdown.js`. It emits a `link_open`/`text`/`link_close` token triple, never a
      string of HTML.
- [x] 2.2 The href is built with `pagePath()` from `routes.js`, so the graph obeys the mount path
      and the workspace in the URL like every other link.
- [x] 2.3 Extend the DOMPurify allowlist only if the rule needs it. Add a test asserting a wikilink
      whose target contains quotes, angle brackets or a `javascript:` prefix cannot escape the
      anchor.
- [x] 2.4 A wikilink to a page that does not exist renders with a distinct class and is still
      clickable, landing on the create-page flow with the slug prefilled.
- [x] 2.5 The editor preview renders wikilinks identically to the reading view.
- [x] 2.6 `GET /api/pages/{slug}/view` returns, for each backlink, the sentence containing the
      mention. Truncate on a word boundary and mark the mention with the same sentinel scheme the
      search snippets use, so the client renders segments and never markup.
- [x] 2.7 Render that context under each mention in `Reader.jsx`, in the data face, and keep the
      existing tag-based related list beside it.

## 3. Phase 3 — The bird's-eye view

- [x] 3.1 `d3-force` entra como dependencia npm (3.0.0, en `package-lock.json`) y la empaqueta
      Vite, en vez de vendorizarse a mano en `app/static/vendor/`. Ese directorio es para lo que
      se carga en diferido por su tamaño — mermaid son 3,2 MB y KaTeX 600 KB —; d3-force son 18 KB
      y es una dependencia del cliente como markdown-it. Empaquetada no se pide nada en ejecución,
      que es lo que el air-gap exige, y la versión la fija el lockfile en vez de un fichero suelto.
      La ruta va en su propio trozo, así que quien no abre el grafo no lo descarga.
- [x] 3.2 `GET /api/workspaces/{ws}/graph` returns `{nodes, edges}`: nodes are live pages with
      slug, title, inbound and outbound counts; edges carry source, target and a `broken` flag.
      Workspace-scoped by membership like every other read.
- [x] 3.3 Route `/w/:ws/graph`, reachable from the sidebar, with the same skeleton and empty states
      as the rest of the application.
- [x] 3.4 Render as SVG the application draws itself. Every colour comes from a design token
      through CSS: nodes on `--surface` with `--border-strong`, edges in `--border`, the current
      page in `--accent`, a broken edge in `--danger`. No palette bridging in JavaScript.
- [x] 3.5 Node labels in the mono face, per the data-and-prose rule of the visual language.
- [x] 3.6 Interaction: drag a node, zoom, click to open the page. Respect
      `prefers-reduced-motion` by settling the simulation before first paint instead of animating
      into place. Recorrido visual hecho en Chrome, en claro y en oscuro. Encontró cinco defectos,
      todos corregidos: el grafo se dibujaba en la esquina porque `forceCenter(0,0)` es el origen
      del SVG y no su centro; el efecto que mide el lienzo se quedó sin dependencias y entraba en
      bucle de render; las páginas huérfanas salían despedidas fuera del lienzo sin nada que las
      retuviera; arrastrar un nodo abría su página, porque un arrastre termina en el mismo `click`
      que un toque; y el href de un wikilink no llevaba el basename `/app`, así que recargaba
      contra el backend y daba 404 — ese afectaba a todos los wikilinks, no solo a los rotos.
- [x] 3.7 Surface the insights the server already computes: orphan count, broken-link count, and
      the list of broken targets with the pages that point at them.
- [x] 3.8 Bound the work. Above a node threshold the view renders the highest-PageRank subgraph and
      says so, rather than laying out a thousand nodes in the browser.

## 4. Phase 4 — Navigation for agents

- [x] 4.1 Add `get_linked_knowledge(slug, depth=1)` to `app/mcp.py`. It returns each reachable page
      with its distance, the direction of each hop, and the path that reached it. El sentido es
      `outgoing`, `incoming` o `both`: dos páginas que se citan la una a la otra son un caso
      corriente, y contarlo solo como saliente lo borraba de los entrantes, que es justo lo que
      pregunta quien busca qué depende de esto. Lo encontró el test que compara `list_backlinks`
      con el recorrido a un salto.
- [x] 4.2 Cap `depth` and cap the returned node count. State both caps in the tool description, and
      say in the result when the neighbourhood was truncated.
- [x] 4.3 Declare the tool read-only in the same terms as the other read tools, per the live
      `mcp-tools` requirement that every tool states its effect.
- [x] 4.4 Keep `list_backlinks` and `related_pages` unchanged. Their descriptions gain one sentence
      each saying which relation they traverse, so the three tools are told apart at a glance.
- [x] 4.5 Test the traversal terminates on a cycle, on a self-link and on a broken edge.

## 5. Closing

- [x] 5.1 Both gates green: `uv run ruff check . && uv run ruff format --check . && uv run pyright
      app tests && uv run pytest`, and `npm run lint && npm run format:check && npm run build &&
      npm run check:assets` plus `npm run test`.
- [x] 5.2 Update `CLAUDE.md`: the new endpoint, the new route, the new vendored asset, the new tool.
- [x] 5.3 Sync the specs and archive the change.
