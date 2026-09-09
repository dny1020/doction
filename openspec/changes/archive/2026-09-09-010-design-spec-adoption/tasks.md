# Tasks

Six phases. Each is revertible and verifiable on its own. Phases 1 and 2 are **not** combined:
one is proved by "nothing renders differently", the other by "every ratio passes", and together
neither proof holds.

## 0. Hygiene and instruments — no visual change

- [x] 0.1 Normalised the file's only `var()` fallback, `var(--r-sm, 4px)` on `.member-role`.
      Fallbacks now count **0**, so a missed rename fails loudly instead of resolving to
      something plausible.
- [x] 0.2 Starting invariants: **2986** lines, **79** hex literals, **22** `rgba()`, **0** of
      either outside the token blocks, **0** `oklch(` and **0** `color-mix(`.
- [x] 0.3 Verifier now parses `oklch()` and `oklch(L C H / A)` alongside hex and `rgba()`,
      via OKLab and linear sRGB, compositing alpha in gamma-encoded sRGB the way a browser
      does. Validated against the ratios recorded in 008 and 009: the focus ring reproduces at
      **4.35** against a recorded 4.33 and **5.37** against 5.39, the rest exactly. The first
      run appeared to disagree because the test compared one ground where the record was the
      worst of four.
- [x] 0.4 Gamut check added, flagging before clamping. It confirms the two the plan predicted:
      `--orange-soft` overshoots red at **1.0215** and `--orange-hover` undershoots blue at
      **-0.0006**. All six documented defects reproduce with this verifier — focus ring 1.24:1,
      `--border-default` 1.64:1, `--border-strong` 2.59:1, `--ink-subtle` 3.80:1, `--danger`
      4.20:1, `--warning` 2.36:1. Corrections derived and recorded in `measurements.md`.
- [x] 0.5 Baseline captured: **246** class signatures across nine routes and both themes, 24
      resolved properties each. Ran twice and the two dumps are byte-identical, so the
      comparison is a real gate and not a source of noise.

## 1. The rename — mechanical, value-preserving

- [x] 1.1 Done as a **single simultaneous-substitution pass** rather than temporary names: one
      regex, longest-name-first, with a negative lookahead so `--border` cannot bite
      `--border-strong`. One pass means nothing is rewritten twice, so the permutation resolves
      by construction. 12→`sm`, 14→`base`, 16→`md`, and the call counts survive exactly
      (21/32/6).
- [x] 1.2 Lines permuted; the document's third `--border-strong` is deliberately absent until
      phase 3.
- [x] 1.3 Renamed to `--code-inline-bg` / `--code-inline-border`, so the document's `--code-bg`
      — which is the dark slab — cannot land on the inline tint by accident.
- [x] 1.4 **1063 substitutions** across all four scopes in one pass. A second permutation the
      plan had not caught surfaced here: the spacing scale also crosses itself, because
      `--sp-5` is 24px and 24px is `--space-6` in the document, not `--space-5`. The single-pass
      approach absorbed it without special handling.
- [x] 1.5 `--space-0`, `--font-data`, the `--syn-*` set, the scrim, the identity ink and the
      chrome and canvas families all survive under renamed forms. Comment pending in phase 2,
      where the token block is rewritten anyway.
- [x] 1.6 **13 substitutions** in `prose.js`, not nine — it reads some tokens more than once.
      Verified by rendering a real diagram: it draws in the application's greens, not Mermaid's
      default lavender.
- [x] 1.7 **Gate passed.** Zero surviving old names. Zero `var()` used but undeclared, zero
      declared but unused (`--bare` and `--missing` are BEM modifiers, not tokens). Both scoped
      blocks keep 23 and 22 declarations, and `var()` uses hold at 1024 before and after. The
      resolved-value dump over 246 class signatures is **identical byte for byte**.

## 2. Colour to oklch

- [x] 2.1 Convert the existing, already-measured values in place. No value moves yet.
- [x] 2.2 Move to the document's palette family by family, correcting by measurement: the focus
      ring, the control boundary, `--ink-subtle`, `--danger` and `--warning`.
- [x] 2.3 Bring `--orange-soft` and `--orange-hover` inside the sRGB gamut deliberately.
- [x] 2.4 Precompute the callout ground and the input background as flat tokens. No
      `color-mix()`, no `@supports`; record the browser floor instead.
- [x] 2.5 Restore the decorative/functional orange split under whatever names survive, or
      re-point its five call sites. The document has one orange and no vocabulary for the
      distinction.
- [x] 2.6 Write every correction back into `DESIGN.md` with its measurement.
- [x] 2.7 **Gate:** zero failures across six grounds, zero out-of-gamut.

## 3. Geometry and type

- [x] 3.1 Radii to 2/4/6/8. `--radius-xl` and `--radius-2xl` alias the large step rather than
      disappearing, so no call site had to move. The pill keeps its three genuinely round
      callers.
- [x] 3.2 Spacing scale adopted, and the §5 rhythm. Two steps the rhythm needs and its own
      scale does not contain — 56px above an H2 and 36px above an H3 — went into the scale as
      `--space-14` and `--space-9` rather than being left loose in a rule. Shadows collapse 4→3.
- [x] 3.3 Reading column 760px, gutter 72px, sidebar 280px, table of contents 220px at 64px
      separation, shell capped at 1720px and centred. The document body also moves to §3's
      16px/1.78. One correction after the first capture: the content was still *centred* in
      its space, so the left margin depended on window width. §4 says it **starts** at 72px, so
      it now aligns left and the shell is what centres.
- [x] 3.4 Manrope vendored at 400/500/600 (§3 asks for those three weights) and Instrument
      Serif at 400, both in latin and latin-ext. Fraunces removed. **Inter also removed**: §3
      names it only as a fallback, and vendoring two interface faces pays twice for a case that
      cannot happen, since both would come from the same origin. The real fallback is
      `system-ui`. Vendored total **226 444 → 157 612 B**, 68 832 fewer.
- [x] 3.5 H2 and H3 move to the interface face at weight 600. At 22 and 16px the serif has too
      small an eye to read as a heading. Display stays on the page title (52px) and the document
      H1 (36px).
- [x] 3.6 Document header from §9: air above, a rule closing it below, breadcrumbs as the
      kicker in the data face at 11px, and the metadata strip at the same step.

## 4. Material and surfaces

- [x] 4.1 Noise texture removed — §7 forbids it in as many words. Replaced with the §7 tonal
      gradient. The optional vertical rules §7 also offers are left out: there is already one
      material decision and §1 asks for few, deliberate ones.
- [x] 4.2 Sidebar is the §8 vertical gradient, and the active item is a faint green ground with
      a 2px inset orange rule instead of the solid fill from 009. **The chrome lost its dark
      variant**: §8 gives one gradient, and a sidebar that is ink green in both themes is what
      "different material" actually means. Its four grounds are now the two gradient ends plus
      the active ground composed over each, and every chrome ink was re-derived against them.
      One real defect the verifier caught: `--ink-strong` was not remapped in the sidebar scope,
      so the active item's text resolved to the canvas's **dark** ink on a dark ground —
      **1.32:1**. Same failure shape as the 1.06:1 bug in 009, and again only visible by
      measuring.
- [x] 4.3 Code block with the §9 border and inner highlight, inline code green on green-soft,
      and callouts on the precomputed warm ground with a 2px orange rule.
- [x] 4.4 Buttons to 32px at 4px radius, inputs to 36px on the precomputed ground, navigation
      at its own 13px step, and the §13 durations. Four literals I introduced along the way
      (28/22/18px) went into the spacing scale as `--space-7` rather than staying loose.

## 5. Top bar and graph

- [x] 5.1 Show the top bar on desktop at 56px, and hide with CSS the toggle that cannot act and
      the action row it duplicates.
- [x] 5.2 Record in `DESIGN.md` what the bar still lacks and why it needs JSX.
- [x] 5.3 Adapt §12's graph rules to the DOM that exists: the node is a group wrapping a circle
      and a label, and two of the document's selectors have no counterpart.

## 6. Verification

- [x] 6.1 Re-captured all 102 screens, same set, both themes, three widths. No layout
      regressions: the mobile drawer and its top bar behave as before, and the four reader
      actions come back below 821px where there is no room for them in the bar.
- [x] 6.2 **0 failures, 0 out of gamut.** Six grounds: light canvas, dark canvas, the two ends
      of the chrome gradient and the active ground composed over each. Tightest margins:
      `--border-default` 3.00:1, `--nav-ink-subtle` 4.52:1, `--ink-subtle` 4.50:1.
- [x] 6.3 **This caught a real regression.** Moving the palette to `oklch()` broke Mermaid: its
      colour parser does not understand the format, and it fails *silently* — no console error,
      no diagram, just the fence source printed as one line. The browser will not convert it
      either; neither `getComputedStyle().color` nor `ctx.fillStyle` normalises to rgb. Painting
      the colour into a 1px canvas and reading the pixel does. Diagrams now draw in the app's
      greens again. Second time Mermaid broke this round, by a different route each time.
- [x] 6.4 A fence with no language reads at 16.33:1 on the slab, and inline code stayed on the
      green tint inside the sentence. Both survived the code tokens moving.
- [x] 6.5 Focus ring visible on both sides of the boundary. It was one of the corrected values:
      the document specified an alpha that composes to 1.24:1.
- [x] 6.6 Zero hex, zero `rgba()`, zero loose `oklch()` outside the token blocks, zero tokens
      used-but-undeclared and zero declared-but-unused. Three colours copied straight out of the
      document into rules were pulled back into tokens, and six tokens orphaned by the active
      item ceasing to be a fill were removed.
- [x] 6.7 `npm run check` passes with the local-assets guard; ruff and pyright clean.

## 7. Prueba en Chrome real

- [x] 7.1 Recorrido en un navegador de verdad, no en capturas automatizadas. Encontró **dos
      defectos que 102 capturas no habían hecho evidentes**, ambos solo en tema oscuro.
- [x] 7.2 **El material de §7 pintaba una banda.** Con el mismo valor en ambos temas, el blanco
      al 18% sobre carbón dibujaba una franja diagonal con borde duro cruzando el documento,
      justo donde el degradado llega a `transparent`. §7 pide un material que se sienta más de
      lo que se ve. Se atenúa a una sexta parte en oscuro, conservando ángulo y paradas — el
      mismo patrón que la textura de la ronda anterior.
- [x] 7.3 **El callout oscuro salía marrón saturado.** Ese valor lo había puesto a ojo en lugar
      de derivarlo como el claro. Componiendo la mezcla de §9 sobre la superficie de su tema da
      `oklch(0.248 0.030 72.5)`, un tinte cálido discreto en vez del pergamino que §14 prohíbe.
      El fondo de los campos tenía el mismo origen y se derivó igual.
- [x] 7.4 Comprobado además: Mermaid dibuja con la paleta de la aplicación en ambos temas, la
      losa de código se lee con y sin lenguaje, el grafo aplica el degradado radial de §12 con
      los nodos huérfanos apagados, la consola no registra ningún error, y el anillo de foco se
      ve sobre la tinta oscura del chrome.
- [x] 7.5 Confirmado en vivo el defecto ya anotado: la barra superior sale **vacía** en la vista
      de grafo, porque su título se deriva de la URL y esa ruta no nombra ninguna página.
