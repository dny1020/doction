## 1. Close the snippet XSS

- [x] 1.1 Change the search-hit contract so a snippet is not HTML: return the matched text plus
      match offsets, or an escaped string. Update `SearchHit`/`SearchResult` in `app/models.py`,
      the `ts_headline` query in `app/db.py:1413`, `embeddings._fts_results` / `search` /
      `rag_context`, and both routes that return it (`app/main.py`, `app/mcp.py`).
- [x] 1.2 Add a test that a page whose body contains `<img src=x onerror=alert(1)>` and a matching
      term returns a snippet with no live markup, in `keyword`, `semantic` and `hybrid` modes.
- [x] 1.3 Remove the `dangerouslySetInnerHTML` at `frontend/src/components/Sidebar.jsx:174` and
      render highlighting from offsets or escaped text; verify a match is still visibly marked.
- [x] 1.4 Audit every remaining `dangerouslySetInnerHTML` in `frontend/src` and confirm each one
      is either the sanitized markdown renderer or removed.

### Notes on section 1

- **`snippet` stayed a string; `parts` was added beside it.** The spec allows either match
  positions or an escaped string. Making `snippet` itself a list of segments would have changed
  the shape of `/api/search` and of the MCP `sgrep` tool for every existing agent and shell
  script. Instead `snippet` is now plain text, which is strictly safer than what it was and still
  a string, and `parts` carries the same text split into segments for the client that highlights.
  `embeddings._clean()` is gone: there is no longer any `<mark>` to strip.
- **The highlight markers are control characters, not `<mark>`.** `ts_headline` now wraps matches
  in `\x01`/`\x02`, and `translate()` removes those two characters from the input before
  highlighting, so a marked segment can only have come from the highlighter. A page whose body
  contains those characters cannot forge a highlight, which is asserted by a test.
- **The test asserts the server half only.** The snippet still contains whatever the page says,
  including text that looks like markup, because it is text and truncating it would misreport the
  page. What changed is that the server adds no markup and the client renders segments as text
  nodes. There is no frontend test runner in this project, so the client half is enforced by the
  audit in 1.4 rather than by a test.

## 2. Markdown sanitizer and the GFM syntax that was traded for it

- [x] 2.1 Add a sanitizer dependency and define doction's allowlist in `frontend/src/markdown.js`
      — elements, attributes and URL schemes — as an explicit constant, not a library default.
- [x] 2.2 Flip `html: false` to `html: true` and route all output through the sanitizer. Verify
      with tests for `<script>`, an `onerror` on an allowed element, `javascript:` and `data:`
      URLs, an `<iframe>`, and a surviving `<details>`/`<abbr>`/`<kbd>`.
- [x] 2.3 Enable task lists and math; verify checkboxes render (read-only in the reading view) and
      that inline and display math render rather than showing delimiters.
- [x] 2.4 Verify sanitization does not strip renderer output: a fenced block keeps its
      `language-*` class and still highlights, a `mermaid` block still becomes a diagram, and math
      markup survives.
- [x] 2.5 Verify a fenced block whose contents are HTML displays as code and executes nothing.
- [x] 2.6 Point the editor preview (`pages/Editor.jsx:224`) and `components/Markdown.jsx` at the
      same function so preview and reading view cannot diverge.

## 3. View states

- [x] 3.1 Build tree and document skeletons matching row height, indentation and reading-column
      width, with an appearance delay so a fast response shows nothing. Verify no layout shift on
      arrival.
- [x] 3.2 Replace the `t('loading')` placeholders in `Reader.jsx:84`, `Trash.jsx:48`,
      `Notes.jsx:40` and `settings/System.jsx:30` with the appropriate skeleton or an inline
      pending state.
- [x] 3.3 Add a timeout that turns a still-pending skeleton into the failure state, and verify a
      hung request eventually reports rather than spinning forever.
- [x] 3.4 Add the empty state for a page with a title and no body, offering edit.
- [x] 3.5 Verify the three states are distinguishable in every fetching view, and that a failure
      in one region leaves the others working.

## 4. Routing: workspace in the URL

- [x] 4.1 Change the route shape to carry the workspace and update every internal link:
      `Sidebar.jsx`, `Reader.jsx`, `Layout.jsx`, `CommandPalette.jsx`, `Notes.jsx`, `History.jsx`,
      `PageActions.jsx`.
- [x] 4.2 Resolve the workspace from the route rather than from the session on every page fetch;
      verify opening a page in a non-active workspace shows the page and makes that workspace
      active.
- [x] 4.3 Redirect old page-only addresses to the new shape; verify a bookmark still resolves.
- [x] 4.4 Make workspace switching an in-application navigation — drop the
      `window.location.assign` at `Sidebar.jsx:80`. Verify back returns to the previous workspace
      and that the unsaved-changes guard fires when switching from a dirty editor.
- [x] 4.5 Add the not-found state for an unknown or unreadable workspace segment, and verify it is
      indistinguishable from the workspace not existing.

## 5. The page tree

- [x] 5.1 Render `list_pages_tree()`'s depth as real nesting with a disclosure control on rows
      that have children and none on rows that do not; verify labels align across both.
- [x] 5.2 Persist collapse state for the session and always expand the path to the active page;
      verify a collapsed branch survives navigating elsewhere.
- [x] 5.3 Implement keyboard operation on a roving tabindex: one Tab stop, up/down between visible
      rows, right to expand then descend, left to collapse then ascend, Enter to open. Verify each
      with the keyboard alone.
- [x] 5.4 Expose the tree to assistive technology with level and expanded state per row; verify
      with a screen reader that both are announced.
- [x] 5.5 Keep focus on an existing row when the tree reloads after create, move, rename or
      delete.
- [x] 5.6 Add the coarse-pointer 44px targets for the disclosure, subpage and overflow controls in
      `app/static/style.css`, and verify under `@media (pointer: coarse)` that no two targets
      overlap and that touching a label never toggles disclosure.
- [x] 5.7 Verify row height, per-level indentation and sidebar density are unchanged on a fine
      pointer.

### Notes on sections 4 and 5

- **Pages live at `/w/<ws>/p/<slug>`, not `/w/<ws>/<slug>`.** The slug is chosen by whoever writes
  the page, so a page titled "new", "trash" or "notes" would shadow those routes without anyone
  noticing. One extra segment buys immunity from that.
- **The backend already accepted `?ws=`.** `attach_user` read a `ws` query parameter ahead of the
  workspace cookie, so carrying the workspace per request needed no new endpoint. What it did need
  was strictness: an explicit `ws` that does not resolve is now a 404 instead of a silent fallback
  to the user's first workspace, which is the whole point of putting it in the URL. The cookie
  still falls back, because it is memory rather than a request.
- **The frontend sends `ws` from one place.** `api.js` appends it to every request and the shell
  sets it from the route during render, before any child fetches. Threading it through a dozen
  call sites was the alternative, and forgetting one would read the wrong workspace silently.
- **The tree needed no API change.** `list_pages_tree()` already returns DFS order with a `depth`
  field, which is enough to rebuild the hierarchy in the client.
- **Collapse state is stored as what is collapsed, not what is expanded**, so the default state is
  the whole tree open — exactly what the sidebar showed before this change.
- **Two defects were found by driving the real app, not by the gates.** Switching workspaces
  redirected using the previous workspace's tree, landing on a page that does not exist in the new
  one; the shell now tracks which workspace its tree belongs to and the reader waits for a matching
  one. And collapsing a branch with the focus inside it sent focus back to the first row, so
  toggling now moves focus to the branch being toggled.
- **The workspace 404 keeps the shell.** It first rendered bare, which left no way out; it now
  renders in the content area with the sidebar of the user's own workspace still usable.
- **Reordering is still out of scope** and 5.x contains no task for it: `pages` has no ordering
  column. The touch-target work covers the controls that exist.

## 6. Integration status

- [x] 6.1 Add a backend read route for webhook delivery history over `webhook_deliveries`,
      grouping attempts under their event and exposing no signing secret. Verify with a test that
      no secret or signature header appears in the response.
- [x] 6.2 Report per-hook health in the webhooks section: failing, pending and never-fired
      distinguished, with recent attempts on open.
- [x] 6.3 Build the status indicator: poll `/health` or `/api/system` and the MCP endpoint's
      `initialize` at a fixed interval, report reachable / degraded / unreachable per surface,
      stay quiet when healthy, and stop while the document is hidden.
- [x] 6.4 Verify recovery clears the indicator without a reload, and that a failing surface does
      not tighten the polling interval.

## 7. Drafts and connection loss

- [x] 7.1 Write the editor's title and body to a per-workspace, per-page local draft on a debounce;
      verify two pages' drafts do not collide and that a blocked local store degrades quietly.
- [x] 7.2 Offer restore on mount when a local draft is newer than the server's copy, with an
      explicit choice; clear the draft on a confirmed save.
- [x] 7.3 Show a connection-lost notice while the server is unreachable, keep the editor usable,
      and clear it on reconnection. Verify by stopping the backend mid-edit, typing, reloading and
      recovering the text.
- [x] 7.4 Distinguish an expired session from a connection failure, and preserve unsaved work
      across signing in again.
- [x] 7.5 Verify the existing `useBlocker` and `beforeunload` guards still fire.

## 8. Debouncing and double submission

- [x] 8.1 Debounce the editor preview render; verify typing does not stutter in a long document.
- [x] 8.2 Discard superseded search responses so a slow earlier response cannot overwrite a later
      one; verify with a delayed response.
- [x] 8.3 Add an in-flight guard and a disabled control to every destructive handler:
      `Reader.onDelete`, `WorkspaceSettings` delete/rename/member add/member remove,
      `Tokens.onRevoke`, `Webhooks.onDelete`, `Trash.onRestore`/`onPurge`, and
      `PageActions.submit`. Verify a double activation sends exactly one request in each case.
- [x] 8.4 State in the delete confirmation for a page with subpages that the subpages are
      affected.
- [x] 8.5 Verify a failed action re-enables its control, and that guarding one action leaves
      unrelated controls usable.

### Notes on sections 6, 7, 8 and 10

- **Two knobs, not four.** `DOCTION_APP_PATH` (where the SPA is mounted, `/app` by default, `/`
  for the root) and `DOCTION_STATIC_PATH`, plus `DOCTION_MCP_PATH` for the status probe. The API
  prefix stayed fixed: the same FastAPI process serves it and no deployment moves it, so making it
  configurable would have been a knob with no user and a rewrite of a dozen call sites.
- **The SPA catch-all now registers last.** Mounted at the root its `/{full_path:path}` would
  otherwise shadow `/api`, `/health`, `/uploads` and `/static`, because Starlette resolves in
  registration order. Verified by serving at the root and checking all four still answer.
- **Autosave is local, not to the server.** Every server save is a git commit, so autosaving to
  the API would turn a page's history into one commit per typing pause. The draft is debounced
  into browser storage under a per-workspace, per-page key; the explicit save and its
  unsaved-changes guards are unchanged.
- **`api.js` now distinguishes a network failure from an HTTP error.** `fetch` only rejects when
  the request never went out or never came back, so that rejection becomes an error carrying
  `offline`. The editor needs the difference: one is retried when the server returns, the other
  has to be read.
- **`delivered_at` does not mean success.** The worker also sets it when it gives up, leaving
  `last_error` behind, so an abandoned delivery would have read as delivered. Status is derived
  from both columns and a test pins it.
- **The air-gap check has an allowlist, and each entry says why.** `www.w3.org` is the SVG XML
  namespace and `reactjs.org` is a URL inside React's error text — neither is ever fetched. It was
  proved to fail by adding a CDN reference to the stylesheet and watching the build reject it.
- **The status indicator started in the wrong place.** It was in the mobile app bar, which is
  `display: none` above 820px, so it was invisible on desktop — found by driving the app, not by
  the gates. It is now fixed to the shell, opposite the toasts.

## 9. Subscription cleanup

- [x] 9.1 Give every subscription added by this change a cleanup: status polling, the draft
      debounce, the tree's keyboard handler, any event stream. Verify mounting and unmounting a
      view repeatedly does not multiply its effects.
- [x] 9.2 Abort or ignore in-flight requests for a view that has been navigated away from.
- [x] 9.3 Re-verify the existing cleanups still hold after the refactors:
      `Layout.jsx`, `Sidebar.jsx`, `CommandPalette.jsx`, `KeyboardShortcuts.jsx`, `Editor.jsx`,
      `Toc.jsx`.

### Notes on section 9

- **Every subscription this change added has its cleanup**: the status poller (cancel flag,
  cleared timer, removed visibility listener, and a generation counter so returning to the tab
  cannot leave two polling chains running), and the editor's draft and preview debounces.
- **The pre-existing cleanups still balance** after the refactors: `addEventListener` and
  `removeEventListener` match one-for-one in all eight files that use them, and both observers
  disconnect.
- **One pre-existing exception, left alone**: `Toast.jsx` sets three timers per toast and clears
  none. Its provider wraps the router and only unmounts when the document does, so the timers die
  with the page. It predates this change and 9.2 is where in-flight work gets addressed.

## 10. Self-hosting

- [x] 10.1 Read the base path from the environment in `vite.config.js:10` and `main.jsx:15`, and
      stop hardcoding `/static/` in `frontend/index.html`; default to today's values and verify an
      unchanged deployment is unaffected.
- [x] 10.2 Make the MCP endpoint path configurable for the status indicator's probe.
- [x] 10.3 Fail the build when a required configuration value is missing, naming it.
- [x] 10.4 Add a check that scans the built bundle, HTML and CSS for any external host and fails;
      wire it into `npm run check` so a future CDN dependency cannot ship.
- [x] 10.5 Confirm the sanitizer and any math renderer added in section 2 ship no runtime fetch
      and no external font.

## 11. Document title

- [x] 11.1 Set `document.title` from the route: page, workspace, application. Verify it updates on
      navigation without a reload and that each history entry carries its own title.
- [x] 11.2 Give settings, trash, notes, the editor and the not-found state their own titles.
- [x] 11.3 Verify a title containing HTML-significant characters appears literally, and that
      renaming a page updates the tab without a reload.

### Notes on sections 2, 3, 8 and 11

- **Three dependencies, and each one earns it.** `dompurify` (the sanitizer, needed on every
  render so it is bundled), `markdown-it-task-lists`, and `vitest`+`jsdom` for the tests. KaTeX is
  **not** a dependency: it is vendored under `app/static/vendor/katex/` and loaded lazily by
  `prose.js`, exactly like mermaid and highlight.js, so the 600 KB only lands on pages that
  contain formulas. Only its woff2 faces were kept and the woff/ttf `src` entries were stripped
  from its stylesheet, so no page requests a font that is not there.
- **The sanitizer broke table alignment, and that is the interesting find.** markdown-it writes
  column alignment as an inline `style`, which is precisely what the allowlist must strip. The
  renderer now translates it to a class and the alignment lives in CSS, where it belonged. Caught
  by a test, not by looking at a page.
- **`<input>` is on the allowlist only for `- [x]`.** A DOMPurify hook removes any input that is
  not a disabled checkbox, so a page cannot render a text field inside a document.
- **Math is marked, not rendered, at sanitize time.** The markdown plugin emits the formula source
  as escaped text inside a marked node; KaTeX converts it client-side afterwards with
  `trust: false`, which blocks `\href` and `\includegraphics`. So KaTeX's own output never has to
  survive the sanitizer, and the page's input never reaches the DOM as markup.
- **The editor preview was silently skipping every enhancement.** Its `ref` was missing, so
  `enhanceProse` ran against null: no highlighting, no diagrams, no formulas — the same markdown
  looked different in the editor and in the reader. Found by driving the app; the gates were green
  the whole time.
- **Skeletons appear only after 250 ms.** Below that a skeleton is a flash that reads as a fault.
  Verified by delaying `fetch` in the running app and watching the document skeleton hold.
- **Empty states are for what is missing, not for what is optional.** A workspace with no pages, a
  page with no body, and a search with no matches each get one with the action that fills it. A
  page with no subpages still renders nothing, because it is not empty — it simply has none.

## 12. Verification

- [ ] 12.1 Walk every view at 1400px, 1000px and 700px: skeletons, empty states, 404, 500,
      keyboard tree, search shortcut, status indicator. **Only done at ~1500px**: the browser on
      this machine would not honour a window resize, so the 1000px and 700px bands are unverified.
      Everything else in this section was checked against the running app.
- [x] 12.2 Verify with the backend stopped: connection notice, draft survival across a reload,
      recovery on restart.
- [x] 12.3 Verify on a network with no external route that every view renders with its intended
      fonts, icons and diagrams.
- [x] 12.4 Confirm the `app-shell`, `settings`, `system-status` and `search` specs still hold.
      Checked by diff against `main`: the mobile header still contains only the sidebar toggle,
      the title and one overflow control (the connection indicator sits outside it); the settings
      routes changed only in indentation; `GET /api/system` has no diff; and nothing in the
      retrieval ranking was touched. The one requirement this change does modify, `app-shell`'s
      44px floor, carries its delta and its reason.
- [x] 12.5 Run the frontend gate: `cd frontend && npm run check`.
- [x] 12.6 Run the Python gate: `uv run ruff check . && uv run ruff format --check . && uv run
      pyright app tests && uv run pytest`.
- [x] 12.7 Run `npm run build` so `app/static/app/` reflects the change, and click through the
      built bundle rather than only the dev server.
