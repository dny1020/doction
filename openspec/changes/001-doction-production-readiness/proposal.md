## Why

doction works. What it lacks is the set of behaviours that separate an application someone
runs on their own laptop from one someone else runs on a Raspberry Pi they do not administer.
Nine of those behaviours are missing, and each of them fails in a way the current interface
cannot report.

**The markdown renderer closes XSS by refusing to render HTML at all.** `frontend/src/markdown.js`
runs `markdown-it` in `commonmark` mode with `html: false` and enables only `table` and
`strikethrough`. That is safe, but it is also why a task list renders as literal `- [ ]`, why
`$…$` renders as dollar signs, and why an `<abbr>` or a `<details>` block a person pasted from
somewhere else silently disappears. The safety and the missing GFM syntax are the same decision,
and undoing half of it without the other half is how stored XSS gets shipped.

**One rendering path already bypasses that decision.** The sidebar renders search snippets with
`dangerouslySetInnerHTML` (`frontend/src/components/Sidebar.jsx`), and those snippets come from
`ts_headline` in `app/db.py:1413`, which wraps matches in `<mark>` without escaping the page text
around them. Page content is the attacker-controlled half of that string. The semantic path is
the same shape: `embeddings._snippet()` returns raw page text and `search(mode="semantic")` puts
it in the same field. A page whose body contains `<img src=x onerror=…>` and a matching search
term is a stored XSS with the renderer's `html: false` fully intact.

**Loading and failure are one word.** Every route renders `<div className="placeholder">Loading</div>`
while it waits — the sidebar tree, the reader, the settings sections, trash, notes. On a Pi over
a VPN that word is on screen long enough to read. Nothing indicates the *shape* of what is
arriving, so a slow load and a hung load look identical.

**The active workspace is not in any URL.** Routes are `/p/:slug` and the workspace lives in the
server session; switching one calls `POST /api/workspaces/{slug}/switch` and then
`window.location.assign('/app/')`, a full reload. Page slugs are globally unique, but page
queries filter by `workspace_id`, so a link to a page in workspace B, opened while workspace A is
active, returns 404 rather than the page. Sharing a link with a colleague is a coin flip.

**The page tree is a flat list.** `db.list_pages_tree()` returns DFS order with a `depth` field
and the sidebar renders one `<li>` per row with `data-depth`. There is no disclosure control, so
nothing collapses, arrow keys do nothing, and a workspace with a hundred pages is a hundred-row
scroll. `Workspaces → Pages → Subpages` is the data model; the sidebar does not present it as one.

**Nothing reports whether the integrations are alive.** `GET /api/system` exists and reports
version, database reachability and retrieval flags, but the settings System section fetches it
once on mount and never again. `POST /api/mcp` — the surface every connected agent uses — is not
reported anywhere at all. A person whose agent stopped answering has no way to tell a dead MCP
endpoint from a dead agent.

**An edit lives only in React state.** `Editor.jsx` holds title and content in `useState`,
saves on explicit submit, and guards navigation with `useBlocker` plus `beforeunload`. Those
guards cover *leaving*. They do not cover the server going away: if `PUT /api/pages/{slug}`
fails, the error renders and the text is still on screen, but a reload, a crash or a closed
laptop takes it. There is no autosave and no local draft.

**Destructive actions can be fired twice.** The create forms guard with `busy`. The actions that
destroy things do not: deleting a page (`Reader.onDelete`), deleting a workspace and its whole
tree (`WorkspaceSettings`), removing a member, revoking a token, deleting a webhook, purging from
trash, and both submits in `PageActions`. Every one of them is an unguarded `async` handler on an
always-enabled button.

**The document title is the string `doction`.** It is hardcoded in `frontend/index.html` and never
written again. Ten open tabs are ten identical tabs, and a browser history entry says nothing
about which page it was.

Two things are already right and this change must not break them. Fonts, icons, highlight.js and
mermaid are all served locally — `app/static/vendor/`, `lucide-react` bundled, Inter self-hosted
with an explicit `@font-face` — so an air-gapped deployment has no external request to make. And
every `addEventListener`, `IntersectionObserver` and `setTimeout` in the current frontend has a
matching cleanup. Both are audited below rather than rebuilt.

## What Changes

- **Markdown gains GFM and a sanitizer, together.** Task lists, footnotes, definition-style
  inline HTML and math get enabled, and rendered HTML passes through an allowlist sanitizer
  before it reaches the DOM. Neither half ships without the other. The allowlist is the spec's
  subject, not the library's default.
- **Search snippets stop being HTML.** The API returns the matched text and the match offsets
  separately, or an escaped string; the sidebar stops calling `dangerouslySetInnerHTML` on
  anything derived from page content.
- **Skeletons replace the loading word** for the sidebar tree and the document body, and the
  reader gains a 500-shaped error state distinct from its existing 404.
- **Empty states get written** for a workspace with no pages, a page with no subpages, a document
  with too few headings for a table of contents, and a document with no body.
- **Routes carry the workspace**: `/w/:workspace/:page` replaces `/p/:slug`, an unknown workspace
  segment 404s the same way an unknown page does, and switching workspaces becomes navigation
  rather than a reload. Old `/p/:slug` URLs redirect.
- **The sidebar becomes a real tree**: disclosure per row, collapse state persisted, full
  keyboard navigation (up, down, right to expand, left to collapse, Enter to open) on a roving
  tabindex.
- **A status indicator reports the API and MCP endpoints** continuously rather than once, and
  the webhooks section reports delivery outcomes per hook from `webhook_deliveries`.
- **Edits survive the server**: debounced local drafts, restored on return, cleared on a
  confirmed save, with the connection state shown while the server is unreachable.
- **Every destructive action gets an in-flight guard**, and the debounce that already exists in
  sidebar search is applied to the editor preview and the draft writer.
- **`document.title` follows the route**: `Page | Workspace — doction`.
- **The local-asset guarantee becomes a test**, so the next dependency that reaches for a CDN
  fails the build instead of failing in an air-gapped deployment.

Three items from the original scope are deliberately **not** included:

- **Reordering pages in the sidebar.** `list_pages_tree()` orders by `created_at, id` and there
  is no ordering column on `pages`. Reordering is a backend capability that does not exist; a
  drag handle over an ordering the server will not persist is a control that lies. The touch-target
  requirement here covers the row controls that *do* exist — disclosure, new subpage, overflow.
- **Inbound webhooks.** `app/webhooks.py` is outbound only: HMAC-SHA256 signing, a delivery queue
  in `webhook_deliveries`, a worker draining it with backoff. There is no route that accepts an
  external event, so there is nothing for an inbound-event view to show. What this change adds is
  visibility into the deliveries doction already makes. Accepting inbound events is a product
  decision about doction's write model, not a frontend readiness item.
- **A configurable API base URL.** FastAPI serves the SPA from its own origin (`/app` catch-all)
  and `api.js` uses relative paths with `credentials: 'same-origin'` — the session cookie only
  works that way. Making the origin configurable would mean CORS, cross-site cookies and a second
  deployment topology to support. What is genuinely coupled is the hardcoded `/app` base path in
  `vite.config.js` and the hardcoded `/static/...` URLs in `index.html`, and *that* is what the
  self-hosting spec addresses.

## Capabilities

### New Capabilities

- `markdown-rendering`: what doction's markdown renderer accepts, what it emits, and which HTML
  survives sanitization — including every path that puts page-derived content into the DOM.
- `view-states`: what a view shows while it is loading, when it has nothing to show, and when it
  has failed, for each of those three cases distinctly.
- `navigation`: how workspace, page and subpage are addressed, and how the page hierarchy is
  operated by keyboard.
- `integration-status`: what the interface reports about the reachability of the API and MCP
  endpoints and about outbound webhook delivery.
- `client-resilience`: how unsaved work survives a server that goes away, and how the client
  avoids doing the same work twice.
- `self-hosting`: what a deployment must be able to change without editing source, and what the
  running application is guaranteed never to fetch from the internet.

### Modified Capabilities

- `app-shell`: the 44px coarse-pointer floor already covers the controls the shell has today.
  Adding a disclosure control to every tree row adds a control it does not cover, so that
  requirement extends to it. Nothing else in `app-shell` changes.

Unmodified: `settings` and `system-status` govern the settings area's structure and the
`GET /api/system` report. This change reads that report more often and shows a summary of it
outside settings; it changes neither spec. `search` governs what search finds; the snippet
change here is about the *encoding* of a result, not its ranking, so `search` is untouched.

## Impact

- **Frontend, rendering**: `src/markdown.js` gains the GFM plugins and the sanitizer;
  `src/components/Markdown.jsx` and the editor preview both go through it. One new dependency
  is unavoidable here (a sanitizer), which is the only dependency this change adds.
- **Frontend, routing**: `App.jsx` route paths change shape and every `to={'/p/' + slug}` in
  `Sidebar.jsx`, `Reader.jsx`, `Layout.jsx`, `CommandPalette.jsx`, `Notes.jsx` and `History.jsx`
  changes with them. `Sidebar.switchWorkspace()` stops calling `window.location.assign`.
- **Frontend, sidebar**: the flat `pages.map()` becomes a recursive tree with disclosure state
  and a keyboard handler. This is the largest single piece of work in the change.
- **Frontend, editor**: a debounced draft writer over `localStorage`, restore-on-mount, and the
  connection-state banner.
- **Frontend, everywhere**: an in-flight guard on each destructive handler, and a `document.title`
  effect in the reader and editor.
- **Backend**: the search snippet's contract changes in `app/models.py`, `app/db.py:1413`,
  `app/embeddings.py` and the two routes that return it (`app/main.py`, `app/mcp.py`). A
  webhook-delivery read route joins `webhook_deliveries`. `GET /api/system` is unchanged.
- **Build**: `vite.config.js` reads the base path from the environment; `index.html` stops
  hardcoding `/static/`. A test asserts the built bundle contains no external host.
- **Not affected**: the database schema, the MCP tool surface, the auth model, and the git-commit
  page history.
