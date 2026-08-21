## Why

doction's SPA is responsive but not *app-like* on a phone: the chrome that should stay
put scrolls away. The sidebar's hide control, the workspace switcher, the search field and
the whole footer (Inbox, New page, theme, avatar) all scroll out of view together with the
page tree, because `.page-list` is missing `min-height: 0` and its overflow escapes to
`.sidebar`. The design already intends these to be fixed — `.sidebar-head` and
`.sidebar-foot` both carry `flex-shrink: 0` — so the shell is one property away from
behaving as designed.

The rest follows from the same gap: on mobile there is no persistent chrome at all, only a
32px button floating over the content, and a page's primary actions (Edit, New subpage,
Delete; Save in the editor) live in the scrolled header, so acting on a long document means
scrolling back to the top. doction is installable as a PWA since 0.22.0, which makes the
missing app shell more visible, not less.

## What Changes

- **Sidebar scrolls only its page tree.** `.page-list` gets `min-height: 0`; `.sidebar`
  stops being a scroll container. Head (brand, workspace, search) and foot (Inbox, New page,
  theme, avatar) become permanently visible on every viewport. This is the fix for the
  hide/show control disappearing.
- **A slim mobile header.** Below 820px the content area gains a sticky header carrying the
  sidebar toggle, the current page title and the page's overflow actions — replacing the
  button that currently floats over the breadcrumbs. Desktop is unaffected: it keeps the
  sidebar-mounted toggle and gains no new chrome.
- **Primary actions stay reachable.** On mobile the reader's `.page-actions` and the
  editor's Save/Cancel move into sticky bars instead of scrolling away with the header.
- **Touch targets meet 44px.** `.btn` joins the existing `pointer: coarse` block that
  already lifts `.sidebar-toggle`, `.theme-toggle`, `.search-clear` and the page-row `⋯`
  menu to 44px. It is currently 34px and is what every primary action uses.
- **Editor gets a write/preview toggle on mobile.** Under 820px the split pane stacks, so
  the preview is a screen below the textarea; an ordinary button in the editor bar switches
  between them instead. A button, not a segmented control — doction has no segmented
  controls today and this change does not introduce a mobile-specific idiom.
- **A tablet breakpoint.** Today 1120px drops the TOC and 820px switches to the drawer,
  leaving 820–1120px with a permanent 264px sidebar and no TOC. The sidebar narrows in that
  band rather than holding full width.
- **Dead CSS removed.** `.topbar` is styled in the mobile media query but the selector
  exists nowhere else in the stylesheet and nowhere in the JSX — a leftover from the retired
  Jinja/HTMX UI.

Not in scope, deliberately: no bottom tab bar, no native-style page transitions, no gesture
navigation, no new runtime dependency, and no change to the REST/MCP contract. The goal is a
shell that stays put, not a mobile app costume.

## Capabilities

### New Capabilities

- `app-shell`: the SPA's layout shell — which chrome stays fixed while content scrolls, how
  the shell reflows across desktop / tablet / mobile, how the sidebar behaves as a drawer,
  and the touch-ergonomics floor for interactive controls.

### Modified Capabilities

<!-- None. openspec/specs/ is empty; this change introduces the project's first capability. -->

## Impact

- **`app/static/style.css`** — the shared design system, and where most of this work lands:
  `.sidebar` / `.page-list` scroll ownership (l.163, l.517), the 820px and 1120px media
  queries (l.1390, l.790), the `pointer: coarse` block (l.1939), `.sidebar-toggle--show`
  (l.231), `.btn` (l.1030), the dead `.topbar` rule (l.1414).
- **`frontend/src/components/Layout.jsx`** — hosts the new mobile header; the floating
  `.sidebar-toggle--show` button moves into it.
- **`frontend/src/pages/Reader.jsx`, `frontend/src/pages/Editor.jsx`** — sticky action bars
  and the editor's write/preview toggle.
- **`frontend/src/components/Sidebar.jsx`** — unchanged in structure; it benefits from the
  scroll fix without markup changes.
- **`app/i18n.py`** — new EN/ES strings for the write/preview control and the mobile
  header's labels for non-page routes. The SPA does not hold a catalog of its own; it fetches
  this one from `GET /api/i18n`, so this adds entries to that response without changing its
  shape.
- No database, API contract or MCP surface is touched. No new npm dependency.
- Verification: `npm run check` (eslint + prettier + build) is the gate; the bundle must be
  rebuilt with `npm run build` for changes to appear, since `app/static/app/` is gitignored.
