# Tasks

Ordered by priority. Each tier is shippable on its own and leaves the app in a consistent state, so
the work can stop after any of them. Every block ends in something checkable by `grep` or by a
number, so "done" is not a matter of taste.

## 0. Settle the direction (no code)

- [x] 0.1 Confirm the accent split: ink green `#173B35` interactive; orange in two forms —
      `--accent #D97745` for decoration that carries nothing, `--accent-ink #A34D21` for marks that
      carry something. This reverses part of change 005 and is the one decision the rest depends on.
- [x] 0.2 Confirm the derived tokens, all measured against the **worst-case surface** rather than
      the page: `--foreground-muted #5F6864`, `--foreground-subtle #626763`, `--accent-ink
      #A34D21`, `--border-strong #858173`; dark `--foreground-dark-muted #938B7E`,
      `--foreground-dark-subtle #918B81`, `--border-dark-strong #766D61`.
- [x] 0.3 Amend `DESIGN.md` §2, §3 and §28 with 0.1 and 0.2 and their measured ratios. Nothing else
      in `DESIGN.md` changes.

## 1. Baseline

- [x] 1.1 Screenshot every app screen in both themes before touching anything. **102 captures**
      via Playwright against a seeded workspace: 15 authed screens (reader ×2, editor, new page,
      history, graph, inbox, trash, the six settings sections, 404) plus login and register, at
      1440/900/390 px, both themes. Indexed in the scratchpad under `shots/before/`.
- [x] 1.2 Record the starting numbers, measured at `b3df89f`: **2706** stylesheet lines, **0** hex
      literals outside the token blocks, **0** `rgba()` outside them, **5** `calc(var(--text-`
      heading rules, **3** `--r-pill` callers, **223 824 B** of vendored font across 8 files, of
      which **32 636 B** is Instrument Serif — the figure Fraunces is measured against in 4.2.

## 2. Tier 1 — palette, radius, elevation

The stylesheet has no literal colours, so this tier is almost entirely a token-block edit.

- [x] 2.1 Light surfaces to §2: `--bg #F5F1E8`, `--surface #F9F7F1`, `--surface-sunken` and
      `--surface-hover` derived from `--background-subtle #EFEADF`. Pure white leaves the palette.
- [x] 2.2 Dark surfaces to §3: `#171614`, `#1D1B18`, `#211F1B`, `#28251F`.
- [x] 2.3 Ink to §2/§3, with `--fg-3` at the derived `#696F6A` / `#857E74`.
- [x] 2.4 Lines: `--border #D8D2C5` / `#39352F` decorative; `--border-strong` at the derived
      values. Every control keeps the strong one.
- [x] 2.5 The accent split. `--accent` becomes ink green and keeps every interactive caller.
      Orange arrives as `--marker` (decorative, `#D97745`) and `--marker-ink` (functional,
      `#A34D21`); the active indicator, status dots and any icon that is the only carrier of its
      meaning take the functional one.
- [x] 2.6 Dark accent per §3: `--ink-green-dark #B9D0C7` interactive (11.12:1), `--accent-dark
      #E08A59` marker (6.85:1).
- [x] 2.7 Primary button to §10: ink green fill, `#F9F7F1` text, `--r-md`.
- [x] 2.8 Radius scale to §8: 6 / 7 / 10 / 12 / 14. `--r-pill` keeps its three circular callers and
      gains none.
- [x] 2.9 Shadows to §9's pair. Panels keep a line and no shadow.
- [x] 2.10 Code blocks to §18: `#E9E6DE` on `#D8D2C5`, `#11110F` on `#39352F`.
- [x] 2.11 Re-measure the syntax highlighting palette against the new code-block backgrounds; every
      token holds its ratio or moves.
- [x] 2.12 Field height to §19's 40–44px band, on pointer as well as touch.
- [x] 2.13 Contrast pass, parsed from the stylesheet itself rather than from a table: every ink,
      accent, danger, marker-ink and control boundary against all four surfaces, plus the tints and
      the six syntax colours against `--code-bg`. **0 failures** in both themes. Worst margins:
      light `--fg-2` 4.53:1, dark `--border-strong` 3.00:1.
- [x] 2.14 `grep -c '#[0-9A-Fa-f]\{3,6\}'` outside the token blocks is still 0.

## 3. Tier 2 — the type scale

- [x] 3.1 Scale to §6: 12 / 14 / 16 / 18 / 22 / 30 / 42. The 18px step is `Lead`, added to
      `DESIGN.md` §6 because the app has no legal size between body and subsection and a card title
      needs one — recorded there per the governance requirement, not diverged silently.
- [x] 3.2 The five `calc(var(--text-*) * 1.15)` heading rules are gone; `grep -c` reaches **0**.
      The one remaining literal size, `font-size: 16px` under `@media (pointer: coarse)`, now reads
      `var(--text-base)`: the iOS zoom threshold and the body step are the same 16px.
- [x] 3.3 Checked the dense surfaces against the baseline at all three widths: sidebar tree,
      tables, settings rows, the command palette. **Nothing wraps that did not wrap before.** The
      webhook form truncates its two inputs at 390 px, but it does so identically in the baseline —
      a pre-existing mobile layout issue, and layout is out of scope for this change.

## 4. Tier 3 — the display face

- [x] 4.1 Subset Fraunces to the latin and latin-ext ranges already vendored, static instances at
      the weights actually painted, no italic. The serif is painted at 400 only, so two files:
      **17 968 B + 17 288 B = 35 256 B**.
- [x] 4.2 Budget was 80 KB. **35 256 B**, against Instrument Serif's 32 636 B — a 2 620 B increase
      for the family the source of truth names. Swapped `--font-serif`, dropped both Instrument
      Serif faces. Vendored total moves 223 824 B → 226 444 B.
- [x] 4.3 No compensation needed. The five `calc()` multipliers existed for Instrument Serif's
      small x-height; Fraunces sits normally on the §6 steps, so 3.2's values stand unchanged.
- [x] 4.4 `npm run check` passes end to end — eslint, prettier, `tsc`-less vite build, and
      `check-local-assets.js` reporting "assets: todo local" with Fraunces vendored.

## 5. Tier 4 — paper texture

- [x] 5.1 One inline SVG fractal-noise data URI as `--paper-texture`, painted on `body` only.
      0.025 in light. Dark carries the same fibre at **0.012**: light grain reads about twice as
      strong on charcoal, and §3 warns the dark theme must never look brown or muddy.
- [x] 5.2 Verified by cascade rather than by rule: the editor textarea, preview, sidebar, cards,
      modals, palette and code blocks all paint their own background, so none inherits the fibre.
      One real gap found — `.prose td` is transparent, so texture read through table cells. The
      table now paints `--surface`, which is what §16 asks for.
- [x] 5.3 Verify it survives the dark theme without turning brown or muddy.
- [x] 5.4 Reviewed across all 102 captures in both themes. The fibre is not perceptible as a
      pattern on any screen and no text loses contrast over it, which is the bar §4 sets. Kept.

## 6. Verification

- [x] 6.1 Re-captured all 102 screens and compared against the baseline. One regression found and
      fixed: giving `.prose table` a `--surface` ground to block the texture turned every table
      into a raised panel, most visibly in the dark theme, which is the background decoration §20
      asks to avoid. The table now paints `--bg` — opaque enough to stop the fibre, the same tone
      as the canvas, so it is invisible. Tables read as thin separators again.
- [x] 6.2 Keyboard pass. The two focus treatments are intact and the split is still by kind: a
      ring on controls, an outline on links in prose. **One defect found and fixed**: the focus
      ring sat at 0.32 alpha and measured **1.80:1** against the paper, where an indicator needs
      3:1. It is pre-existing — the blue ring it replaced measured **1.70:1** and had been there
      since change 005 — but this change owns the token, so it is fixed here rather than logged.
      At 0.7 alpha it measures **4.33:1** light and **5.39:1** dark and still reads as a halo.
- [x] 6.3 `npm run check` passes, `check:assets` included ("assets: todo local"). Python gate:
      ruff clean, 50 files formatted, pyright 0 errors, **78 tests pass**.
- [x] 6.4 Sync the delta into `openspec/specs/visual-language/spec.md` and archive.
