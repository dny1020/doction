## 1. Decide the language before writing any CSS

- [ ] 1.1 Write the palette: surfaces, ink levels, decorative line, control boundary, one accent,
      one warning — light and dark together, not light first and dark later. Record the measured
      contrast ratio of every pair that carries text or bounds a control.
- [ ] 1.2 Decide the type roles and the families that fill them. Three roles exist — display, text,
      data — and three families is the reference's answer, not necessarily doction's. Justify each
      family against its vendored weight, and say which role an already-present family could fill.
- [ ] 1.3 Subset every chosen face to the ranges the interface renders and vendor it under
      `app/static/vendor/fonts/`. Verify `npm run check` still reports every asset local.
- [ ] 1.4 Check the accent against the danger hue for anyone who cannot separate them by colour:
      a destructive control must be identifiable by more than its colour.

## 2. Apply it

- [ ] 2.1 Replace the token block, light and dark. Every value a token, no literals left in rules.
- [ ] 2.2 Sweep the stylesheet for hardcoded colours and for rules that assume the orange accent.
- [ ] 2.3 Move radii to the new family, keeping the pill, and verify nothing that relied on a tight
      radius now reads as a pill — the tag, the badge, the avatar, the code fence.
- [ ] 2.4 Apply the data/prose rule: tags, slugs, heading paths, dates, counts, versions, delivery
      statuses, the retrieval constants and the system report's values move to the data face;
      confirm no descriptive sentence moved with them.
- [ ] 2.5 Give controls the boundary token. Inputs, selects, bordered buttons, the workspace
      selector, the settings section selector.
- [ ] 2.6 Restyle what ships its own colours: highlight.js on the new paper, KaTeX sitting level
      with the surrounding text, mermaid's light and dark themes.
- [ ] 2.7 Remove the `--font-serif` token if no role uses it, or make it hold a serif if one does.
      It currently names a serif and holds Inter.

## 3. What must not move

- [ ] 3.1 No `.jsx` file changes. If a component needs editing to restyle it, stop: either the
      change is drifting into layout, or the component is hardcoding a colour and that is the fix.
- [ ] 3.2 No motion changes. `rise`, the durations, the easing, the transitions on menus, palette
      and toasts, the skeleton pulse and the `prefers-reduced-motion` override are all untouched.
      Verify by diff, not by eye.
- [ ] 3.3 No behaviour changes: nothing appears, disappears, moves or reorders.
- [ ] 3.4 Verify the 44px floor still holds on coarse pointers after the radius and padding change,
      including the tree's disclosure gutter.

## 4. Verification

- [ ] 4.1 Measure every contrast pair the spec requires, in both themes, and record the numbers.
- [ ] 4.2 Walk the app in both themes: reader, editor with a page carrying tables, code, mermaid
      and math, the tree, search results, all six settings sections, trash, inbox, the 404 and the
      error state, and the connection indicator in its failing state.
- [ ] 4.3 Confirm no flash on load with the dark theme stored.
- [ ] 4.4 Confirm every asset is local: `cd frontend && npm run check`.
- [ ] 4.5 Run the frontend gate and the tests: `npm run check && npm run test`.
- [ ] 4.6 Run the Python gate — `app/static/style.css` ships in the image and the asset check reads
      it: `uv run ruff check . && uv run ruff format --check . && uv run pyright app tests && uv run
      pytest`.
- [ ] 4.7 Confirm the change is one stylesheet and some fonts. Any other file in the diff needs a
      reason.
