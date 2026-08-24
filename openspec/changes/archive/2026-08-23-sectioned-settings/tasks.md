## 1. System report endpoint

- [x] 1.1 Add `db.index_counts(workspace_id, model)` returning live page count and how many of
      those have chunks for that model; verify with a test that embeds one page of several and
      asserts both numbers.
- [x] 1.2 Add authenticated `GET /api/system` in `app/main.py` returning version, db state and
      the `semantic_search` / `rerank` / `ocr_uploads` flags; verify a test asserts 401 without
      auth and the flags match the environment.
- [x] 1.3 Include `embedding_model` and index counts only when semantic search is on, sourcing
      the name from `embeddings.current_model_name()`; verify a test asserts the keys are absent
      with the flag off and that no ONNX session is constructed.
- [x] 1.4 Verify the endpoint is read-only: a test asserts POST/PUT/PATCH/DELETE on `/api/system`
      return 405.

## 2. Settings routing

- [x] 2.1 Convert `/settings` into a layout route with children for `account`, `preferences`,
      `workspaces`, `tokens`, `webhooks` and `system` in `App.jsx`; verify each URL loads its own
      section directly.
- [x] 2.2 Redirect bare `/settings` to `/settings/account` with `replace`, and verify the
      sidebar link and a direct `/settings` load both land on the account section without
      leaving a dead entry in history.
- [x] 2.3 Add a catch-all child rendering `NotFound` for unknown section names; verify
      `/settings/nonsense` shows the 404 rather than an empty settings frame.
- [x] 2.4 Have the settings layout forward the shell context —
      `<Outlet context={useOutletContext()} />` — and verify a section reading `reloadPages`
      receives it rather than `undefined`.

## 3. Section navigation

- [x] 3.1 Build the settings layout: persistent section list beside the content above 1120px,
      compact selector at or below it. Verify at 1400px, 1000px and 700px that exactly one of
      the two is present at each width.
- [x] 3.2 Implement the compact selector on the `.ws-select` trigger-plus-menu idiom, including
      click-outside dismissal; verify choosing a section navigates, closes the menu and updates
      the trigger label.
- [x] 3.3 Mark the current section with `aria-current` and a non-colour indicator; verify with
      the keyboard that each item is focusable, focus is visible, and activation navigates.
- [x] 3.4 Add `.settings-nav*` rules to `app/static/style.css` using existing tokens, and verify
      against `@media (pointer: coarse)` that the selector trigger and list items meet the 44px
      minimum required by the `app-shell` spec.

## 4. Move the existing sections

- [x] 4.1 Move `ProfileSection` and `PasswordSection` out of `Settings.jsx` into the account
      section, code unchanged; verify saving a display name, avatar colour and password all still
      work and still toast.
- [x] 4.2 Move `TokensSection` and `WebhooksSection` into their own sections, code unchanged;
      verify create, list and revoke/delete on both, including that a new token is still shown
      once.
- [x] 4.3 Make `WorkspaceSettings.jsx` the Workspaces section, keeping rename, delete, members
      and export; verify each still works and that deleting a workspace refreshes the page tree.
- [x] 4.4 Delete the now-empty stacked container from `Settings.jsx` and verify no component
      renders two sections at once.

## 5. Preferences section

- [x] 5.1 Add theme and language controls to the preferences section, reusing `theme.js` and the
      existing language endpoint; verify changing either from settings takes effect immediately.
- [x] 5.2 Keep the shell's theme and language controls working, and verify a change made in one
      place is reflected in the other without a reload.

## 6. System section

- [x] 6.1 Render the report from `GET /api/system` as read-only rows grouped into retrieval and
      server; verify no value is an editable control.
- [x] 6.2 Handle the report failing to load with an inline message, and verify the rest of the
      settings area still works when the endpoint returns an error.

## 7. Copy and i18n

- [x] 7.1 Add section names and System labels to both the EN and ES catalogs in `app/i18n.py` in
      one edit; verify by switching language that no raw key is rendered in any section or in the
      navigation.

## 8. Verification

- [x] 8.1 Walk all six sections at 1400px, 1000px and 700px, confirming one section on screen at
      a time, working back button, and a working deep link into each.
- [x] 8.2 Confirm the `app-shell` spec still holds: sidebar chrome, mobile header and drawer
      behaviour are unchanged by the settings work.
- [x] 8.3 Run the frontend gate: `cd frontend && npm run check`.
- [x] 8.4 Run the Python gate: `uv run ruff check . && uv run ruff format --check . && uv run
      pyright app tests && uv run pytest`.
- [x] 8.5 Run `npm run build` so `app/static/app/` reflects the change, and click through the
      built bundle at `/app/settings` rather than only the dev server.

## Notes from implementation

- **3.1 was implemented differently than designed, for a reason found by testing.** The design
  put the 1120px threshold in two places: `matchMedia` in JS choosing which navigation to
  render, and the CSS media query supplying the two-column grid. Driving the real app exposed
  what that duplication costs — with the two out of step the section list renders *above* the
  content instead of beside it, because JS switched and CSS did not. Both navigations are now
  always in the DOM and the media query alone decides which is visible, so the widths cannot
  drift. The threshold is unchanged at 1120px and lives only in `style.css`.
- **5.2 caught a real defect.** `PreferencesSection` snapshotted `getTheme()` on mount, so
  toggling the theme from the sidebar footer left the settings label showing the previous
  value until reload. It now observes `data-theme` on `<html>` with a `MutationObserver`,
  which needs no change to `theme.js` or the shell and works whoever writes the attribute.
- **Wide-viewport verification used a temporary breakpoint.** The browser window would not
  resize past 879px CSS pixels on this machine, so the ≥1121px branch was verified by
  temporarily lowering the media query to 700px, confirming the two-column layout, sticky
  nav, active marking and section switching, then restoring 1121px. `style.css` is served
  directly rather than bundled, so this needed no rebuild. The 820px band and the compact
  selector were verified at the real 879px width.
- **8.2 verified by diff, not by mobile viewport.** `Layout.jsx` and `Sidebar.jsx` have no
  diff, and the only deletion in `style.css` is the `.avatar-menu-item {` line, extended into
  a longer selector list so the existing 44px `pointer: coarse` rule also covers the new
  controls. No shell rule was changed or removed.
