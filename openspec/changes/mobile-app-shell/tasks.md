All styling lands in `app/static/style.css` unless a task names another file. Every new rule
goes behind an existing `@media` query — the default desktop / fine-pointer path must not
change. See `design.md` — Decisions for the rationale behind each choice.

## 1. Sidebar scroll ownership

- [x] 1.1 Add `min-height: 0` to `.page-list` (l.517) and change `.sidebar` (l.163) from
      `overflow-y: auto` to `overflow: hidden`; verify that with a page tree taller than the
      viewport the brand, workspace selector, search field, Inbox link, New page button,
      theme control and avatar all stay visible while the tree scrolls to its end.
- [x] 1.2 Verify a tree *shorter* than the viewport renders no scrollbar and keeps the footer
      pinned to the bottom edge of the sidebar (`.page-list` is `flex: 1`, so it fills the
      column).
- [x] 1.3 Verify the workspace dropdown and the user menu still open fully inside the sidebar
      now that it clips overflow — check both themes at a short viewport height (~600px),
      since the user menu opens upward via `bottom: calc(100% + 6px)`.
- [x] 1.4 Convert the row overflow menu in `frontend/src/components/PageActions.jsx` from the
      `.avatar-menu` dropdown to the native `<dialog>` + `showModal()` pattern the component
      already uses for move and rename, so the top layer escapes `.page-list`'s clipping;
      verify the menu opens fully for a row at the bottom of a scrolled tree.
- [x] 1.5 Verify move and rename still work end to end from the new menu — move a page under a
      new parent, rename one, and confirm the existing toasts fire and the tree reloads.

## 2. Translation catalog

- [x] 2.1 Add EN and ES entries to `app/i18n.py` for the write/preview toggle (`preview`,
      `write`) and the mobile header's static labels for `/notes`, `/settings` and `/trash`;
      verify `GET /api/i18n` returns the new keys in both languages and that ES falls back to
      EN for any key left untranslated.

## 3. Mobile header

- [x] 3.1 Render an `.app-bar` element in `frontend/src/components/Layout.jsx` as the first
      child of `.content`, containing the existing `.sidebar-toggle` markup, a truncated page
      title, and an overflow control; verify it appears below 820px and is absent above it.
- [x] 3.2 Derive the title in `Layout.jsx` from the route — match the active slug against the
      `pages` tree the way `Sidebar.jsx` does, falling back to the static i18n label for
      non-page routes; verify the title matches the open page and updates on navigation
      without any new Outlet-context plumbing.
- [x] 3.3 Populate the overflow control with Edit, New subpage and History as plain links off
      the active slug, reusing the existing `.avatar-menu` dropdown pattern; verify Delete is
      **not** present and each link lands on the right route.
- [x] 3.4 Style `.app-bar` as `position: sticky; top: 0` inside `.content`, one row, ~44px,
      with a hairline bottom border and an opaque `--surface` background; verify it stays
      visible while scrolling a long page and that content scrolls beneath it without needing
      compensating top padding.
- [x] 3.5 Remove the `position: fixed` floating placement of `.sidebar-toggle--show` (l.231)
      within the 820px query now that the toggle lives in the bar; verify the toggle no longer
      overlaps breadcrumbs or headings at any scroll position, and that its desktop
      collapsed-state behaviour is unchanged.

## 4. Editor and reader on small viewports

- [x] 4.1 Under 820px, make `.editor-bar` (l.1215) sticky directly beneath the app bar and add
      `min-width: 0` to `.title-input` so the row does not wrap; verify Save and Cancel are
      reachable from the end of a long document without scrolling up, and that the row stays
      a single line at 360px wide.
- [x] 4.2 Under 820px, hide `.preview` by default and add a `.btn` in `.editor-bar` toggling
      between textarea and preview (labels from task 2.1) in `frontend/src/pages/Editor.jsx`;
      verify toggling swaps the panes, that the desktop split view is untouched above 820px,
      and that no segmented-control markup is introduced.
- [x] 4.3 Verify the `useBlocker` unsaved-changes guard still fires after the editor changes —
      edit a page, navigate away without saving, confirm the prompt appears.
- [x] 4.4 Verify `.page-actions` (l.826) in the reader is left in the page body and unchanged;
      Delete must remain there rather than moving into persistent chrome.

## 5. Touch ergonomics

- [x] 5.1 Extend the `::after` 44px overlay in the existing `@media (pointer: coarse)` block
      (l.1939) to cover `.btn`; verify on a touch device that a tap near a button's edge
      registers and that the button's rendered height stays 34px.
- [x] 5.2 Add `min-height: 44px` to `.page-list a` inside the same coarse-pointer block;
      verify tree rows are comfortably tappable and that the `data-depth` indentation is
      unaffected.
- [x] 5.3 Verify with a fine pointer that no control's height, padding or spacing differs from
      before this change — compare a desktop screenshot of the reader, editor and settings
      pages against the current build.
- [x] 5.4 Verify the widened `.btn` hit areas do not swallow neighbouring taps in
      `.page-actions` and `.editor-actions`, where buttons sit `--sp-2` (8px) apart.

## 6. Responsive bands and cleanup

- [x] 6.1 Set `--sidebar-w: 220px` inside `@media (max-width: 1120px)` (l.790); verify that at
      ~900px the sidebar is narrower and the content area wider, and that the drawer's
      `85vw / max-width: 320px` still wins below 820px.
- [x] 6.2 Delete the dead `.topbar` rule at l.1414; verify with a repo-wide search that the
      selector appears nowhere in `app/static/style.css` or `frontend/src/`.

## 7. Verification

- [x] 7.1 Run `cd frontend && npm run check` (eslint + prettier + build) and confirm it passes
      with no new warnings.
- [x] 7.2 Run `npm run build` and confirm `app/static/app/` is regenerated, since the bundle is
      gitignored and the app serves the built output.
- [x] 7.3 Manual pass on a real phone: read a long page, scroll a long tree, open and dismiss
      the drawer by tapping the overlay, navigate from the tree, edit and save. Confirm the
      drawer starts closed after a reload.
- [x] 7.4 Manual pass at a tablet width (~900px) and at desktop, in both light and dark themes,
      confirming the desktop layout is visually identical to the pre-change build.
