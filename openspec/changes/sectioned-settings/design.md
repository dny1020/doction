## Context

See `proposal.md` — Why. Four properties of the current code shape the approach.

**The router is already a data router.** `main.jsx` uses `createBrowserRouter` with
`basename: '/app'`, and `App.jsx` exports a plain route tree. Nested routes are available
today; the editor's unsaved-changes `useBlocker` already depends on this router.

**The shell owns two breakpoints and a spec.** `Layout.jsx` reads
`(max-width: 820px)` via `matchMedia`; `style.css` also breaks at 1120px, where the
table-of-contents column is dropped. `openspec/specs/app-shell` fixes this behaviour in nine
requirements, including that the shell reflows across three bands and that touch targets meet
44px. Settings navigation is a *second* navigation layer inside the content area and must fit
between those bands without changing them.

**`Layout.jsx` passes state through its `Outlet`.** It renders
`<Outlet context={{ pages, pagesError, reloadPages }} />`, and `Reader`, `Editor`, `History`
and `Trash` consume it. `useOutletContext` resolves to the *nearest* provider, so introducing a
second `<Outlet>` inside settings silently cuts sections off from it. No settings component
uses that context today, which is exactly why the trap is easy to walk into later.

**There is already a dropdown idiom.** The workspace selector (`.ws-select`, `.ws-trigger`,
`.ws-menu` in `style.css`; behaviour in `Sidebar.jsx`) is a trigger button showing the current
value plus a menu of options, with click-outside dismissal. doction has no tabs and no
segmented controls, and the archived mobile-shell change rejected introducing one.

## Goals / Non-Goals

**Goals:**

- One section on screen at a time, each with its own URL.
- A navigation pattern that degrades in one step, reusing an idiom the codebase already has.
- Surface the deployment's retrieval configuration, which is currently invisible everywhere.
- Move code rather than rewrite it, so five working forms stay working.

**Non-Goals:**

- Any visual redesign. Same tokens, same spacing, same `.settings-*` vocabulary. If the
  sections look different from today beyond their arrangement, the change has overreached.
- New settings capabilities. No LLM providers, notifications or storage management — see
  `proposal.md`.
- Changing the application shell or its spec.
- Server-side persistence of preferences. Theme stays in `localStorage`, language stays a
  cookie; unifying them is a separate concern.
- Reorganising `WorkspaceSettings` internals. It becomes a section; its nested members list
  stays as it is.

## Decisions

### Nested routes, not local state

Sections become child routes of a `/settings` layout route:

```
/settings                → redirect to /settings/account
/settings/account        My Account
/settings/preferences    Preferences
/settings/workspaces     Workspaces
/settings/tokens         Access Tokens
/settings/webhooks       Webhooks
/settings/system         System
/settings/<unknown>      NotFound
```

Alternative rejected: keeping one route and tracking the section in component state. It is
less code and it fails the first requirement — no deep links, no back button, and a reload
always dumps you back on the first section. The routing table is also where the section list
becomes reviewable in one place instead of implied by render order.

`/settings` redirects rather than rendering a landing page: the sidebar links to it and it may
be bookmarked, and an index page listing six links the navigation already shows is furniture.

Unknown section names render the existing `NotFound` as a catch-all child route. The
alternative — an empty settings frame with nothing selected — is a dead end that looks like a
bug.

### The settings layout must re-provide the outlet context

The settings layout route renders `<Outlet context={useOutletContext()} />`, forwarding the
shell's `{pages, pagesError, reloadPages}` unchanged. Nothing needs it today; the Workspaces
section is the obvious first consumer, since deleting a workspace should refresh the page tree
rather than rely on a full reload. Forwarding costs one line and removes a failure that would
otherwise surface as an undefined destructure far from its cause.

### Section navigation collapses at 1120px, not 820px

The shell's sidebar is a persistent column down to 820px. A second persistent column inside the
content area between 820px and 1120px would leave the actual settings content narrower than the
navigation chrome around it — and `app-shell` requires that no width leave the content area
less usable than the band above it.

```
  ≥1120px    [ sidebar ][ section list ][ section content ]
  820-1120   [ sidebar ][ selector ▾                      ]
              (narrowed)  [ section content               ]
  <820px     [ ☰ header ][ selector ▾                     ]
                          [ section content               ]
```

1120px is reused deliberately: it is already the width at which the reader drops its
table-of-contents column, so the interface loses its secondary column at one width rather than
at two arbitrary ones. Settings has no table of contents, so the band is free.

Alternative rejected: collapsing at 820px to match the sidebar. It is the number that first
comes to mind and it produces the worst layout in the band where it matters most.

### The compact selector reuses the workspace-selector idiom

A trigger button showing the current section, opening a menu of all sections — the same
structure as `.ws-select`. Reasons: it is already styled, already handles click-outside and
keyboard dismissal in `Sidebar.jsx`, already meets the 44px touch minimum under
`@media (pointer: coarse)`, and it keeps every section one interaction away regardless of how
many there are.

Alternatives rejected:

- **Horizontal scrolling tabs.** Pushes later sections off-screen, so reaching them is a scroll
  plus a tap, and it reads as a segmented control — an idiom this codebase deliberately does not
  have.
- **A native `<select>`.** Cannot carry the design system, and the existence of `.ws-select`
  shows the project already made this call once.
- **Reusing the shell's drawer.** Would put settings navigation behind the same control as page
  navigation, so the section list would compete with the page tree for one surface.

### `GET /api/system` reports, and only reports

```json
{
  "version": "0.23.0",
  "db": "ok",
  "semantic_search": true,
  "rerank": false,
  "ocr_uploads": false,
  "embedding_model": "all-MiniLM-L6-v2-int8",
  "indexed_pages": 27,
  "pending_pages": 0
}
```

The last three keys are present only when semantic search is on — reporting `0` indexed pages
for a deployment that has the feature disabled is indistinguishable from a broken index.

The model name comes from `embeddings.current_model_name()`, which reads the encoders' class
attributes and deliberately does not construct the ONNX session, so the report is cheap with
the feature off. Index counts need one new query counting live pages in the workspace against
distinct `page_chunks.page_id` for the current model; `db.pages_to_embed()` exists but returns
page content and is the wrong tool.

Authenticated like every other `/api` route. Separate from `/health`, which is unauthenticated,
consumed by the container healthcheck, and must stay a liveness probe rather than grow into an
inventory.

No write path, now or later: these values come from the process environment, and a settings
form that appears to change them would be lying unless the app could rewrite `/opt/doction/.env`
and restart itself.

### Split by moving, not rewriting

`Settings.jsx` already contains four self-contained components (`ProfileSection`,
`PasswordSection`, `TokensSection`, `WebhooksSection`) that own their own fetch, state and
submit handlers. Each moves to its own file essentially unchanged; `ProfileSection` and
`PasswordSection` land in the same account section file. `WorkspaceSettings.jsx` is already a
separate component and only needs its section wrapper.

The value here is what it rules out: rewriting five working forms while also changing routing
and layout makes any resulting bug ambiguous between the two. Behavioural changes to the forms
themselves are out of scope.

## Risks / Trade-offs

- **Three columns get tight between 1120px and roughly 1400px** → the section list is a text
  list, not a panel; it takes the width of its longest label. If it still crowds, the fix is to
  raise the collapse threshold, not to shrink the content.
- **`/settings` bookmarks and the sidebar link** → covered by the redirect, and worth an
  explicit test rather than an assumption, since it is the one URL that certainly exists in the
  wild.
- **Splitting a 441-line file can drift behaviour** → move code verbatim; the existing
  `test_spa_api.py` coverage of the settings endpoints is the check that the forms still post
  what they posted before.
- **Two catalogs in `i18n.py` must stay in sync** → a missing key renders as the key itself, so
  a section could ship with a raw identifier as its name. Add EN and ES together, in one edit.
- **A second dropdown appears on small viewports** (workspace selector in the drawer, section
  selector in the content) → they live on different surfaces and are never visible
  simultaneously, since opening the drawer covers the content.
- **The System section can mislead if it drifts from reality** → every value is read from the
  running process at request time; nothing is cached or stored.

## Migration Plan

No data migration. The change is additive apart from the `/settings` route, which gains
children and a redirect.

1. Ship the backend endpoint first; it is independent and testable on its own.
2. Split the frontend and add the routes.
3. `npm run build` — `app/static/app/` is gitignored and the Docker `web` stage rebuilds it, so
   a frontend change that is not rebuilt simply does not appear.
4. Rollback is reverting the image; no persisted state changes shape.

## Open Questions

- **Should Preferences eventually persist theme server-side?** Today theme is `localStorage`
  and language is a cookie, so the two behave differently across devices. Deferrable: it
  changes neither the section layout nor this change's task breakdown, only what the
  preferences section writes to.
