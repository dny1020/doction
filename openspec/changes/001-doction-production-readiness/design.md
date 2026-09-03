# Design — production readiness audit

The requirement list this change came from was written against a generic minimalist markdown
application. This document maps each item onto what `doction` actually contains today, so the
implementation work is the difference and not the whole list. Line references are to the tree at
the time of writing.

## 1. Markdown rendering and frontend security

| Requirement | State | Where |
|---|---|---|
| XSS sanitized without breaking GFM | **Partial — safe, but by amputation** | `frontend/src/markdown.js` |
| Tables | Covered | `markdown.js:11` — `md.enable(['table', …])` |
| Strikethrough, autolinks, typographer | Covered | `markdown.js:6-11` |
| Fenced code + highlighting | Covered, self-hosted | `frontend/src/prose.js:50`, `app/static/vendor/highlight.min.js` |
| Mermaid | Covered, inserted as text, `securityLevel: 'strict'` | `prose.js:32-40` |
| Task lists | **Missing** | not enabled |
| Math | **Missing** | not enabled |
| 404 on a missing page | Covered | `frontend/src/pages/Reader.jsx:60-72` |
| 404 on an unknown route | Covered | `frontend/src/App.jsx:92`, `pages/NotFound.jsx` |
| 404 on an unknown settings section | Covered | `App.jsx:85` |
| 404 on a missing workspace | **Not expressible** — no workspace segment in any route |
| 500 / render crash | Covered | `pages/Reader.jsx:73-83`, `components/ErrorBoundary.jsx` |
| Network failure distinguished from empty | Covered for the tree | `components/Layout.jsx:28`, `Sidebar.jsx:192-198` |
| Empty state: no pages | Covered | `Reader.jsx:50-57` |
| Empty state: no subpages | Covered by omission | `Reader.jsx:154` — section hidden when empty |
| Empty state: no table of contents | Covered by omission | `components/Toc.jsx:21-26` — needs ≥2 headings |
| Empty state: empty document body | **Missing** — renders an empty `.prose` |
| Skeletons | **Missing** — every view renders the word "Loading" | `Reader.jsx:84`, `Trash.jsx:48`, `Notes.jsx:40`, `settings/System.jsx:30` |

**The sanitizer is the whole item.** `markdown-it` runs in `commonmark` mode with `html: false`,
which is why `Markdown.jsx:17` can call `dangerouslySetInnerHTML` safely. Enabling task lists and
math is a two-line change; enabling HTML without a sanitizer first is how this becomes a
vulnerability. The two are one task.

**The snippet path is already a hole.** `Sidebar.jsx:174` renders `r.snippet` with
`dangerouslySetInnerHTML`. That string is built by `ts_headline` in `app/db.py:1413`, which wraps
matches in `<mark>` and leaves the page text around them exactly as stored. The semantic and
hybrid modes reach the same field through `embeddings._snippet()` (`app/embeddings.py:268`) and
`search()` (`app/embeddings.py:389-411`), which do not escape either — `_clean()` only strips the
`<mark>` tags FTS added. A page containing an event-handler attribute plus a matching search term
is stored XSS with `html: false` fully in force. This is the one item in the change that is a
present defect rather than a missing feature.

## 2. Navigation hierarchy and minimalist UX

| Requirement | State | Where |
|---|---|---|
| Workspace in the URL | **Missing** — server session state | `Sidebar.jsx:75-87`, `app/main.py` `_api_workspace` |
| Page in the URL | Covered | `App.jsx:66` — `/p/:slug` |
| Subpage addressable directly | Covered — slugs are globally unique |
| Switching workspaces without a reload | **Missing** — `window.location.assign('/app/')` | `Sidebar.jsx:80` |
| Tree collapse / expand | **Missing** — flat list with `data-depth` | `Sidebar.jsx:200-205`, `app/db.py:826` |
| Keyboard tree navigation | **Missing** — rows are plain links, one Tab stop each |
| Global search shortcut | Covered | `components/CommandPalette.jsx:26-37` |
| Search shortcut works inside a text field | Covered | `CommandPalette.jsx:28`, and `KeyboardShortcuts.jsx:43-46` deliberately steps aside |
| Focus restored on close, closed palette inert | Covered | `CommandPalette.jsx:41-51`, `:80` |
| 44px coarse-pointer targets | Covered for existing controls | `openspec/specs/app-shell/spec.md`, `app/static/style.css` |
| 44px targets for new tree controls | **Delta of this change** | `app-shell` MODIFIED |
| Reordering subpages | **Out of scope** — no ordering column; `list_pages_tree` orders by `created_at, id` | `app/db.py:839` |

**Workspace-in-URL is the largest routing consequence.** Page slugs are globally unique because a
slug is also a directory name in the git repo, so `/p/:slug` does identify a page — but every page
query filters by `workspace_id`, so opening a page belonging to a workspace that is not the
session's active one returns 404. That is the concrete bug the URL change fixes, and it is why the
change is worth its blast radius: every `to={'/p/' + …}` in the frontend moves.

**The tree is the largest single piece of frontend work.** `list_pages_tree()` already returns DFS
order with `depth`, so the data is right; the sidebar flattens it into one `<li>` per row. A real
tree needs nesting, disclosure state, persistence of that state, revealing the active path, and a
roving-tabindex keyboard handler. None of that exists.

## 3. Interoperability — MCP, API and webhooks

| Requirement | State | Where |
|---|---|---|
| Deployment self-report exists | Covered | `app/main.py:563` `GET /api/system`, `tests/test_system_report.py` |
| Anonymous liveness/readiness | Covered | `app/main.py:1069` `GET /health` |
| Report shown in the interface | Covered, in settings only, fetched once on mount | `frontend/src/pages/settings/System.jsx:14-19` |
| Continuous status indicator outside settings | **Missing** |
| MCP endpoint reachability reported | **Missing** — `POST /api/mcp` appears nowhere in the interface | `app/mcp.py` |
| Outbound webhooks with signing and retry | Covered | `app/webhooks.py`, `webhook_deliveries` |
| Webhook last status per hook | Partial — one field, no history | `frontend/src/pages/settings/Webhooks.jsx:84-93` |
| Webhook delivery history | **Missing** — `webhook_deliveries` has no read route |
| Inbound webhooks | **Out of scope** — no route accepts an external event |
| Draft preserved when the server falls over | **Missing** | `frontend/src/pages/Editor.jsx` |
| Unsaved-changes guards | Covered | `Editor.jsx:74-91` — `useBlocker` plus `beforeunload` |
| Failed save reports and retains content | Covered | `Editor.jsx:126-128` |

**`initialize` and `tools/list` are open on the MCP endpoint** while `tools/call` requires Bearer
auth, so a status probe can check reachability without a token. That makes the MCP half of the
indicator cheap.

## 4. Self-hosting readiness

| Requirement | State | Where |
|---|---|---|
| No external CDN for fonts | **Covered** — Inter vendored, two `@font-face` ranges | `app/static/style.css:1-27`, `app/static/vendor/fonts/` |
| No external CDN for icons | **Covered** — `lucide-react` bundled | `frontend/package.json` |
| No external CDN for scripts | **Covered** — highlight.js and mermaid vendored, lazily loaded from `/static/vendor/` | `frontend/src/prose.js:9-19` |
| No external CDN for favicons and app icons | **Covered** | `app/static/favicon.svg`, `icon-192.png`, `icon-512.png`, `apple-touch-icon.png`, `manifest.webmanifest` |
| The guarantee is enforced | **Missing** — nothing fails if the next dependency reaches out |
| API base URL is configuration | **Not applicable as stated** — same-origin by design | `frontend/src/api.js`, `credentials: 'same-origin'` |
| Base path is configuration | **Missing** — hardcoded in three places | `vite.config.js:10` `base: '/app/'`, `main.jsx:15` `basename: '/app'`, `index.html` `/static/…` |
| Dynamic `document.title` | **Missing** — the literal string `doction`, never rewritten | `frontend/index.html:6` |

**The air-gap requirement is already satisfied and should be locked rather than built.** Someone
took the trouble to vendor Inter with explicit unicode ranges and a comment explaining that a
request to `fonts.gstatic.com` would fail precisely where doction is used. The work here is a
check that keeps it true.

**A configurable API origin is the wrong reading of the requirement for this architecture.**
FastAPI serves the SPA from its own origin through the `/app` catch-all and the session is an
httponly same-origin cookie. A separately-hosted frontend would mean CORS and cross-site cookies —
a second deployment topology, not a readiness fix. The genuine coupling is the hardcoded base
path, and that is what the spec asks for.

## 5. Performance and resilience

| Requirement | State | Where |
|---|---|---|
| Debounced search | Covered — 200 ms | `Sidebar.jsx:50-62` |
| Superseded search responses discarded | **Partial** — the timer is cleared, an in-flight request is not |
| Debounced autosave | **Missing** — there is no autosave |
| Debounced preview render | **Missing** — re-renders markdown on every keystroke | `Editor.jsx:224` |
| Double-submit guard on creates | Covered | `Editor.jsx:110-111`, `settings/Tokens.jsx:15`, `settings/Webhooks.jsx:15`, `settings/Account.jsx:26`, `WorkspaceSettings.jsx:15` |
| Double-submit guard on destructive actions | **Missing everywhere** | see below |
| Listener cleanup | **Covered throughout** | see below |

**Every destructive handler is unguarded.** Each is an `async` function on an always-enabled
button with no in-flight state: `Reader.onDelete` (`Reader.jsx:86`), `WorkspaceSettings` delete,
rename, member add and member remove (`WorkspaceSettings.jsx:79`, `:90`, `:169`, `:181`),
`Tokens.onRevoke` (`settings/Tokens.jsx:40`), `Webhooks.onDelete` (`settings/Webhooks.jsx:41`),
`Trash.onRestore` and `Trash.onPurge` (`pages/Trash.jsx:25`, `:36`), and `PageActions.submit` for
both move and rename (`components/PageActions.jsx:40`). The pattern to copy already exists three
files away; it was simply never applied to the delete path. Deleting a workspace deletes every page
under it, so this is the highest-consequence gap in the change.

**Cleanup needs auditing, not writing.** Every `addEventListener` in the current frontend has a
matching `removeEventListener` in its effect's return: `Layout.jsx:66`, `Sidebar.jsx:72`,
`CommandPalette.jsx:36`, `KeyboardShortcuts.jsx:64`, `Editor.jsx:91`, `Editor.jsx:105`. The
`IntersectionObserver` in `Toc.jsx:68` is disconnected and its class removed. `Sidebar.jsx:62`
clears its debounce timer. The requirement holds today; what this change adds is new subscriptions
— status polling, the draft writer, a possible event stream — which must arrive with their cleanup
rather than have it retrofitted.

## What is not touched

- The database schema, the MCP tool surface (21 tools), the auth model, and git-backed page
  history.
- `openspec/specs/search` — the snippet change is about encoding a result, not ranking one.
- `openspec/specs/settings` and `openspec/specs/system-status` — this change reads the system
  report more often and summarises it outside settings; neither spec's requirements change.
- `openspec/specs/app-shell`, apart from the one requirement extended to cover the tree's new
  disclosure controls.
