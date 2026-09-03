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

- [ ] 2.1 Add a sanitizer dependency and define doction's allowlist in `frontend/src/markdown.js`
      — elements, attributes and URL schemes — as an explicit constant, not a library default.
- [ ] 2.2 Flip `html: false` to `html: true` and route all output through the sanitizer. Verify
      with tests for `<script>`, an `onerror` on an allowed element, `javascript:` and `data:`
      URLs, an `<iframe>`, and a surviving `<details>`/`<abbr>`/`<kbd>`.
- [ ] 2.3 Enable task lists and math; verify checkboxes render (read-only in the reading view) and
      that inline and display math render rather than showing delimiters.
- [ ] 2.4 Verify sanitization does not strip renderer output: a fenced block keeps its
      `language-*` class and still highlights, a `mermaid` block still becomes a diagram, and math
      markup survives.
- [ ] 2.5 Verify a fenced block whose contents are HTML displays as code and executes nothing.
- [ ] 2.6 Point the editor preview (`pages/Editor.jsx:224`) and `components/Markdown.jsx` at the
      same function so preview and reading view cannot diverge.

## 3. View states

- [ ] 3.1 Build tree and document skeletons matching row height, indentation and reading-column
      width, with an appearance delay so a fast response shows nothing. Verify no layout shift on
      arrival.
- [ ] 3.2 Replace the `t('loading')` placeholders in `Reader.jsx:84`, `Trash.jsx:48`,
      `Notes.jsx:40` and `settings/System.jsx:30` with the appropriate skeleton or an inline
      pending state.
- [ ] 3.3 Add a timeout that turns a still-pending skeleton into the failure state, and verify a
      hung request eventually reports rather than spinning forever.
- [ ] 3.4 Add the empty state for a page with a title and no body, offering edit.
- [ ] 3.5 Verify the three states are distinguishable in every fetching view, and that a failure
      in one region leaves the others working.

## 4. Routing: workspace in the URL

- [ ] 4.1 Change the route shape to carry the workspace and update every internal link:
      `Sidebar.jsx`, `Reader.jsx`, `Layout.jsx`, `CommandPalette.jsx`, `Notes.jsx`, `History.jsx`,
      `PageActions.jsx`.
- [ ] 4.2 Resolve the workspace from the route rather than from the session on every page fetch;
      verify opening a page in a non-active workspace shows the page and makes that workspace
      active.
- [ ] 4.3 Redirect old page-only addresses to the new shape; verify a bookmark still resolves.
- [ ] 4.4 Make workspace switching an in-application navigation — drop the
      `window.location.assign` at `Sidebar.jsx:80`. Verify back returns to the previous workspace
      and that the unsaved-changes guard fires when switching from a dirty editor.
- [ ] 4.5 Add the not-found state for an unknown or unreadable workspace segment, and verify it is
      indistinguishable from the workspace not existing.

## 5. The page tree

- [ ] 5.1 Render `list_pages_tree()`'s depth as real nesting with a disclosure control on rows
      that have children and none on rows that do not; verify labels align across both.
- [ ] 5.2 Persist collapse state for the session and always expand the path to the active page;
      verify a collapsed branch survives navigating elsewhere.
- [ ] 5.3 Implement keyboard operation on a roving tabindex: one Tab stop, up/down between visible
      rows, right to expand then descend, left to collapse then ascend, Enter to open. Verify each
      with the keyboard alone.
- [ ] 5.4 Expose the tree to assistive technology with level and expanded state per row; verify
      with a screen reader that both are announced.
- [ ] 5.5 Keep focus on an existing row when the tree reloads after create, move, rename or
      delete.
- [ ] 5.6 Add the coarse-pointer 44px targets for the disclosure, subpage and overflow controls in
      `app/static/style.css`, and verify under `@media (pointer: coarse)` that no two targets
      overlap and that touching a label never toggles disclosure.
- [ ] 5.7 Verify row height, per-level indentation and sidebar density are unchanged on a fine
      pointer.

## 6. Integration status

- [ ] 6.1 Add a backend read route for webhook delivery history over `webhook_deliveries`,
      grouping attempts under their event and exposing no signing secret. Verify with a test that
      no secret or signature header appears in the response.
- [ ] 6.2 Report per-hook health in the webhooks section: failing, pending and never-fired
      distinguished, with recent attempts on open.
- [ ] 6.3 Build the status indicator: poll `/health` or `/api/system` and the MCP endpoint's
      `initialize` at a fixed interval, report reachable / degraded / unreachable per surface,
      stay quiet when healthy, and stop while the document is hidden.
- [ ] 6.4 Verify recovery clears the indicator without a reload, and that a failing surface does
      not tighten the polling interval.

## 7. Drafts and connection loss

- [ ] 7.1 Write the editor's title and body to a per-workspace, per-page local draft on a debounce;
      verify two pages' drafts do not collide and that a blocked local store degrades quietly.
- [ ] 7.2 Offer restore on mount when a local draft is newer than the server's copy, with an
      explicit choice; clear the draft on a confirmed save.
- [ ] 7.3 Show a connection-lost notice while the server is unreachable, keep the editor usable,
      and clear it on reconnection. Verify by stopping the backend mid-edit, typing, reloading and
      recovering the text.
- [ ] 7.4 Distinguish an expired session from a connection failure, and preserve unsaved work
      across signing in again.
- [ ] 7.5 Verify the existing `useBlocker` and `beforeunload` guards still fire.

## 8. Debouncing and double submission

- [ ] 8.1 Debounce the editor preview render; verify typing does not stutter in a long document.
- [ ] 8.2 Discard superseded search responses so a slow earlier response cannot overwrite a later
      one; verify with a delayed response.
- [ ] 8.3 Add an in-flight guard and a disabled control to every destructive handler:
      `Reader.onDelete`, `WorkspaceSettings` delete/rename/member add/member remove,
      `Tokens.onRevoke`, `Webhooks.onDelete`, `Trash.onRestore`/`onPurge`, and
      `PageActions.submit`. Verify a double activation sends exactly one request in each case.
- [ ] 8.4 State in the delete confirmation for a page with subpages that the subpages are
      affected.
- [ ] 8.5 Verify a failed action re-enables its control, and that guarding one action leaves
      unrelated controls usable.

## 9. Subscription cleanup

- [ ] 9.1 Give every subscription added by this change a cleanup: status polling, the draft
      debounce, the tree's keyboard handler, any event stream. Verify mounting and unmounting a
      view repeatedly does not multiply its effects.
- [ ] 9.2 Abort or ignore in-flight requests for a view that has been navigated away from.
- [ ] 9.3 Re-verify the existing cleanups still hold after the refactors:
      `Layout.jsx`, `Sidebar.jsx`, `CommandPalette.jsx`, `KeyboardShortcuts.jsx`, `Editor.jsx`,
      `Toc.jsx`.

## 10. Self-hosting

- [ ] 10.1 Read the base path from the environment in `vite.config.js:10` and `main.jsx:15`, and
      stop hardcoding `/static/` in `frontend/index.html`; default to today's values and verify an
      unchanged deployment is unaffected.
- [ ] 10.2 Make the MCP endpoint path configurable for the status indicator's probe.
- [ ] 10.3 Fail the build when a required configuration value is missing, naming it.
- [ ] 10.4 Add a check that scans the built bundle, HTML and CSS for any external host and fails;
      wire it into `npm run check` so a future CDN dependency cannot ship.
- [ ] 10.5 Confirm the sanitizer and any math renderer added in section 2 ship no runtime fetch
      and no external font.

## 11. Document title

- [ ] 11.1 Set `document.title` from the route: page, workspace, application. Verify it updates on
      navigation without a reload and that each history entry carries its own title.
- [ ] 11.2 Give settings, trash, notes, the editor and the not-found state their own titles.
- [ ] 11.3 Verify a title containing HTML-significant characters appears literally, and that
      renaming a page updates the tab without a reload.

## 12. Verification

- [ ] 12.1 Walk every view at 1400px, 1000px and 700px: skeletons, empty states, 404, 500,
      keyboard tree, search shortcut, status indicator.
- [ ] 12.2 Verify with the backend stopped: connection notice, draft survival across a reload,
      recovery on restart.
- [ ] 12.3 Verify on a network with no external route that every view renders with its intended
      fonts, icons and diagrams.
- [ ] 12.4 Confirm the `app-shell`, `settings`, `system-status` and `search` specs still hold.
- [ ] 12.5 Run the frontend gate: `cd frontend && npm run check`.
- [ ] 12.6 Run the Python gate: `uv run ruff check . && uv run ruff format --check . && uv run
      pyright app tests && uv run pytest`.
- [ ] 12.7 Run `npm run build` so `app/static/app/` reflects the change, and click through the
      built bundle rather than only the dev server.
