## Why

`/settings` is one route rendering one 720px column: profile, password, tokens, webhooks and
workspaces stacked in a single scroll (`frontend/src/pages/Settings.jsx`, 441 lines, plus
`WorkspaceSettings.jsx`, 225 more). Finding anything means scrolling past everything, there is
no way to link to a specific setting, and the page only grows — every future capability adds
another card to the same column. On a phone the whole thing is one long strip.

Two smaller problems come with it. Theme and language, the settings people change most often,
are not on the settings page at all — they live in the sidebar footer. And nothing anywhere in
the interface reveals which retrieval mode the server is running: `SEMANTIC_SEARCH`, `RERANK`
and `OCR_UPLOADS` are set in `/opt/doction/.env` on the Pi and the app is silent about them, so
the only way to tell whether semantic search is on is to notice the shape of the results.

## What Changes

- **`/settings` becomes a sectioned area with one route per section** (`/settings/:section`),
  each rendering only its own content. Sections are deep-linkable and the browser's back
  button moves between them.
- **Section navigation is responsive**: a persistent list beside the content on wide viewports,
  and a compact selector on narrow ones. This is a second navigation layer *inside* the content
  area — the app shell's sidebar is unaffected and its spec (`openspec/specs/app-shell`) is not
  modified.
- **Six sections**, each with a focused job:

  | Section | Contents | Backed by |
  |---|---|---|
  | My Account | display name, avatar colour, email, password | `/api/me`, `/api/settings/profile`, `/api/settings/password` |
  | Preferences | theme, language, sidebar default | client state, `/api/lang/{code}` |
  | Workspaces | list, rename, delete, members, export | `/api/workspaces` and children |
  | Access Tokens | create, list, revoke | `/api/tokens` |
  | Webhooks | create, list, delete | `/api/webhooks` |
  | System | version, database, retrieval mode, index state | **new** `GET /api/system` |

- **Theme and language move into Preferences** and stay in the sidebar footer as well. They are
  used too often to be only two levels deep, and removing them would be a regression dressed as
  tidying.
- **One new read-only endpoint, `GET /api/system`**, reporting version, database reachability,
  whether semantic search / reranking / OCR are enabled, the embedding model name, and how many
  pages are indexed versus pending. Read-only on purpose: these are deployment facts, not user
  preferences.
- **No visual redesign.** The existing design system, spacing, and `.settings-*` class
  vocabulary carry over. What changes is information architecture and routing, not appearance.

Three sections from the original request are deliberately **not** included:

- **AI / LLM Providers** — doction contains no LLM, by design and by documented principle
  (`app/embeddings.py`: *"doction hace retrieval; la generación la hace el agente conectado por
  MCP — aquí no vive ningún LLM"*). Provider and key configuration would reverse that
  architecture; that is a product decision, not a settings layout.
- **Notifications** — nothing in the system produces user-facing notifications. Webhooks are
  outbound machine integrations and already have their own section.
- **Storage** — there is no storage usage, quota or upload-management API. Workspace export,
  the one storage-shaped thing that exists, belongs with Workspaces.

**Search & RAG** is not a section of its own either: its settings are deployment-level
environment variables, so it appears as a read-only group inside System rather than a section
implying controls that cannot exist.

Empty sections are worse than absent ones — they promise features that do not exist. When any
of these capabilities is built, it gets a section then.

## Capabilities

### New Capabilities

- `settings`: the settings area's information architecture and navigation behaviour — how
  settings are grouped, addressed by URL, and navigated on wide and narrow viewports.
- `system-status`: read-only reporting of the running deployment's version, database state and
  retrieval configuration.

### Modified Capabilities

None. `app-shell` governs the application shell (sidebar, mobile header, touch targets); this
change adds navigation inside the content area and must satisfy that spec without altering it.

## Impact

- **Frontend**: `pages/Settings.jsx` splits into a section layout plus one component per
  section; `components/WorkspaceSettings.jsx` becomes the Workspaces section; `App.jsx` gains
  nested routes under `/settings`. Note that `Layout.jsx` supplies `{pages, pagesError,
  reloadPages}` through its `Outlet` context — a nested outlet resolves to the nearest
  provider, so the settings layout must pass that context through or sections that use it will
  break.
- **Backend**: one new read-only route in `app/main.py`; a small helper reporting index counts.
  No schema change, no new dependency.
- **Styles**: new `.settings-nav*` rules in `app/static/style.css`, reusing existing tokens.
- **i18n**: section names and System labels added to both catalogs in `app/i18n.py`.
- **Existing URLs**: `/settings` must keep working — it redirects to the first section rather
  than 404ing, since it is linked from the sidebar and may be bookmarked.
