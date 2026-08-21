## Context

See `proposal.md` — Why, and `specs/app-shell/spec.md` for the behaviour contract.

Constraints that shape the approach:

- Styling is one shared, hand-written stylesheet (`app/static/style.css`, ~2040 lines) built
  on CSS custom properties. There are no CSS modules, no utility framework and no
  styled-components. New rules join the existing sections and reuse the existing tokens.
- The SPA is plain JSX. Adding a dependency is out of scope, so anything that looks like a
  drawer library, a headless UI kit or a gesture handler is unavailable by construction.
- Three responsive controls already exist and are correct: `@media (max-width: 1120px)`
  drops the TOC column, `@media (max-width: 820px)` turns the sidebar into a drawer, and a
  `@media (pointer: coarse)` block expands small icon-button hit areas to 44px with an
  `::after` pseudo-element. This change extends those; it does not introduce a new
  responsive strategy.
- `app/static/app/` is gitignored. Nothing shows up in the running app until
  `npm run build` regenerates the bundle.

## Goals / Non-Goals

**Goals:**

- Fix the persistence failure at its root rather than papering over it with sticky
  positioning.
- Keep the desktop rendering byte-for-byte identical wherever the change is not specifically
  about desktop.
- Put every new rule behind an existing breakpoint or pointer query, so the default
  (desktop, fine pointer) stylesheet path is untouched.

**Non-Goals:**

- No JavaScript-driven layout. Nothing here should need a resize listener, a
  `ResizeObserver`, or scroll position state.
- No new shared component abstraction. The mobile header is one element in `Layout.jsx`, not
  a `<Header>` subsystem.
- No change to the REST or MCP contract. `app/i18n.py` gains catalog entries, which changes
  the *content* of `GET /api/i18n`, not its shape.

## Decisions

### 1. Fix sidebar scroll ownership, don't add stickiness

`.page-list` already declares `flex: 1; overflow-y: auto` — it is *meant* to be the scroll
container. It fails because a flex item's `min-height` defaults to `auto`, which resolves to
content height, so the item never shrinks and its overflow escapes to `.sidebar`, which
carries `overflow-y: auto` and scrolls the whole column.

The fix is `min-height: 0` on `.page-list` and changing `.sidebar` from `overflow-y: auto` to
`overflow: hidden`. Head and foot are already `flex-shrink: 0`; they become permanently
visible with no new rules.

*Alternative rejected:* `position: sticky` on `.sidebar-head` and `.sidebar-foot`. It works,
but it needs opaque backgrounds and z-index management to stop tree rows showing through, and
it leaves `.sidebar` scrolling — so the sticky footer would hover over the last tree item
instead of sitting below it. It treats the symptom; the flex fix restores the intended design.

### 2. The mobile header is sticky inside the content column, not fixed to the viewport

A new `.app-bar` element rendered by `Layout.jsx` directly inside `.content`, with
`position: sticky; top: 0`, shown only under 820px.

Sticky rather than fixed because a sticky element participates in layout: the content below
it needs no compensating top padding, and it cannot collide with the drawer's stacking
context. `position: fixed` (which the current floating toggle uses) requires manually
offsetting `.content-body`, and that offset has to be maintained against
`env(safe-area-inset-top)` for the installed PWA.

Composition, one row, ~44px tall:

```
┌──────────────────────────────────────────────┐
│ [☰]   Page title (truncated)            [⋯]  │  44px, hairline bottom border
└──────────────────────────────────────────────┘
```

- `[☰]` reuses the existing `.sidebar-toggle` markup and styling, relocated out of its
  current `position: fixed` floating placement. `.sidebar-toggle--show` loses its `fixed`
  positioning under 820px and its rule is deleted from the mobile query.
- The title is a truncated single line at `--text-sm`. No brand mark, no search field, no
  tabs — per the spec, and because both already live in the drawer.
- `[⋯]` reuses the existing `.avatar-menu` dropdown pattern, the same one `PageActions` and
  the user menu already use. Not a new visual idiom.

### 3. The header derives its title and actions from the route, not from page state

`Layout.jsx` already receives `pages` and can read the active slug from the URL with the same
one-line match `Sidebar.jsx` uses (`location.pathname.match(/^\/p\/([^/]+)/)`). The title
comes from the matching tree entry; non-page routes (`/notes`, `/settings`, `/trash`) use a
static i18n label.

This avoids adding a `setAppBar(...)` callback to the Outlet context and the state plumbing
that comes with it. The header stays a dumb function of the URL.

The consequence is a deliberate scope limit on the overflow menu: it carries only the actions
`Layout` can express as plain links off the slug — **Edit**, **New subpage**, **History**.
**Delete** stays in the page body. That is the right split anyway: delete is destructive and
rare, it needs the confirm dialog and a tree reload, and hoisting it into always-visible
chrome makes it easier to hit by accident on a phone.

*Alternative rejected:* an Outlet-context callback letting each route publish its own title
and action set. More flexible, but it is state plumbing across five route components to
solve a problem the URL already answers.

### 4. The editor's save controls become sticky in place

Under 820px, `.editor-bar` — which already holds the title input, Cancel and Save in one flex
row — becomes `position: sticky` directly beneath the app bar. The title input gets
`min-width: 0` so the row does not wrap.

No markup moves. The unsaved-changes `useBlocker` guard is untouched.

*Alternative rejected:* hoisting Save into the app bar via the HTML `form="..."` attribute, so
a submit button outside the `<form>` still submits it. It is standards-based and would save
~48px of vertical chrome, but it couples `Layout` to the editor's form id and puts a
save-in-progress state in a component that knows nothing about the edit. Clever over boring.

*Alternative rejected:* a fixed bottom action bar. Thumb-reachable, but it is a mobile-app
pattern with no desktop counterpart, and it fights the iOS keyboard when the textarea is
focused.

### 5. Editor preview toggles with an ordinary button, not a segmented control

The proposal said "segmented control". Revised after review: under 820px the preview pane is
hidden by default and a plain `.btn` in `.editor-bar` toggles between the textarea and the
preview, labelled *Preview* / *Write*.

A segmented control is a mobile-specific idiom doction does not currently use anywhere. A
`.btn` is the interface's existing vocabulary and needs no new CSS beyond `display: none`
toggling.

### 6. Touch sizing uses two techniques, chosen by control shape

Both live in the existing `@media (pointer: coarse)` block, so no fine-pointer rule changes.

| Control shape | Technique | Why |
|---|---|---|
| Small square icon buttons | `::after` 44px overlay (existing) | keeps the 32px visual; already applied to `.sidebar-toggle`, `.theme-toggle`, `.search-clear`, `.page-row-actions-btn` |
| `.btn` (34px, inline, variable width) | `::after` overlay, extended to `.btn` | preserves the 34px look; expanding padding would reflow every button row |
| Full-width rows (`.page-list a`, `.avatar-menu-item`, `.ws-option`) | `min-height: 44px` | they are already full-width blocks, so growing them adds no horizontal reflow and an `::after` overlay would collide with the neighbouring row |

`.avatar-menu-item` and `.ws-option` already have the `min-height: 44px` rule; only
`.page-list a` is added.

### 7. Tablet band narrows the sidebar via the custom property

`@media (max-width: 1120px)` sets `--sidebar-w: 220px`. The `.sidebar` rule already reads
`width: var(--sidebar-w)`, so one declaration covers it and the drawer's `85vw / max-width:
320px` under 820px continues to override.

### 8. Remove the dead `.topbar` rule

`app/static/style.css:1414` styles `.topbar`, a selector that appears nowhere else in the
stylesheet and nowhere in `frontend/src/`. It is a leftover from the retired Jinja/HTMX UI.

## Risks / Trade-offs

- **Stacked chrome in the mobile editor.** App bar (~44px) plus sticky editor bar (~52px)
  is ~96px of fixed chrome on a phone, against a `.editor-textarea` of `min-height: 40vh`.
  → Accepted as the cost of not hoisting Save into the app bar (decision 4). If it proves too
  heavy in use, the app bar can hide its title on `/edit` routes, recovering the row without
  changing the structure.
- **`overflow: hidden` on `.sidebar` clips any child that overflows deliberately.** The
  workspace dropdown and the avatar menu open *inside* the sidebar and are positioned
  relative to it. → Both already open within the sidebar's bounds (the avatar menu opens
  upward via `bottom: calc(100% + 6px)`); this must be verified in both themes and at a
  short viewport height, and is called out as a task.
- **`::after` hit expansion on `.btn` can overlap neighbouring buttons.** `.page-actions` and
  `.editor-actions` put buttons in a row with `--sp-2` (8px) gaps; two 44px overlays on 34px
  buttons will overlap by a few pixels. → The overlay is centred, so each button still owns
  its own centre; the overlap region resolves to whichever is later in the DOM. Acceptable,
  but the gap in `.page-actions` should be checked on a real device.
- **Sticky elements and iOS Safari's dynamic toolbar.** `position: sticky` inside a scrolling
  ancestor is well-supported, but the project has already had one round of iOS Safari fixes
  (commit `b96ddac`). → The header sticks inside `.content`, not the viewport, which is the
  more robust of the two; verify against the `100dvh` usage already in `.layout`.
- **Nothing here is covered by an automated test.** The gate (`npm run check`) is eslint +
  prettier + `tsc`/build; it cannot catch a layout regression. → Verification is manual and
  enumerated in tasks: a real phone, a tablet width, and a desktop before/after comparison.

## Migration Plan

Pure frontend styling plus catalog entries; no data migration and no deploy coupling.

1. Land the CSS and JSX changes; run `npm run check`.
2. `npm run build` to regenerate `app/static/app/` (gitignored — the Docker `web` stage does
   this in CI).
3. Ship in the normal image: push to `main`, CI publishes to GHCR, manual `docker compose
   pull && up -d` on the Pi.

Rollback is redeploying the previous image tag. No schema, no API, no persisted state is
touched — `localStorage.sidebar` keeps its existing `open`/`collapsed` values and meaning.
