## 1. Decide the language before writing any CSS

- [x] 1.1 Write the palette: surfaces, ink levels, decorative line, control boundary, one accent,
      one warning — light and dark together, not light first and dark later. Record the measured
      contrast ratio of every pair that carries text or bounds a control.
- [x] 1.2 Decide the type roles and the families that fill them. Three roles exist — display, text,
      data — and three families is the reference's answer, not necessarily doction's. Justify each
      family against its vendored weight, and say which role an already-present family could fill.
- [x] 1.3 Subset every chosen face to the ranges the interface renders and vendor it under
      `app/static/vendor/fonts/`. Verify `npm run check` still reports every asset local.
- [x] 1.4 Check the accent against the danger hue for anyone who cannot separate them by colour:
      a destructive control must be identifiable by more than its colour.

### Notes on block 1

- **Inter stays; two families were added, not three.** The spec says a family is added only if a
  role requires it and no present family can fill it. Inter fills the text role, so replacing it
  with Inter Tight would have cost 133 KB to change nothing anyone can name. Instrument Serif and
  JetBrains Mono cost 90 KB between them, and only the latin subsets load unless a page needs
  latin-ext. Total fonts: 133 KB → 236 KB.
- **Only the faces that render are vendored**: the serif in regular, the mono in 400 and 500, no
  italics from either.
- **The control boundary needed no sweep.** Every control already used `--border-strong`; it was
  the token's *value* that was too light at about 1.6:1. Raising it to `#8A8D83` (3.21:1) fixed
  every input, button, select and trigger at once.
- **`--fg-3` was the real accessibility bug.** At `#8C887F` it measured 3.4:1 and it is used for
  `.muted` body text, not decoration. Now 6.37:1.
- **The dark theme is original work.** The source is light-only, so its palette was designed here
  against the same ratios, on a warm `#161614` rather than a blue-grey. The blue could not carry
  over — `#1B4FA0` on `#161614` misses 4.5:1 — so its lightness rises while the hue stays, which is
  what keeps it the same accent.
- **`--font-data` and `--font-code` are aliases of the mono**, separate so a rule says *why* it uses
  the face rather than which one, and so one can move without the other later.

## 2. Apply it

- [x] 2.1 Replace the token block, light and dark. Every value a token, no literals left in rules.
- [x] 2.2 Sweep the stylesheet for hardcoded colours and for rules that assume the orange accent.
- [x] 2.3 Move radii to the new family, keeping the pill, and verify nothing that relied on a tight
      radius now reads as a pill — the tag, the badge, the avatar, the code fence.
- [x] 2.4 Apply the data/prose rule: tags, slugs, heading paths, dates, counts, versions, delivery
      statuses, the retrieval constants and the system report's values move to the data face;
      confirm no descriptive sentence moved with them.
- [x] 2.5 Give controls the boundary token. Inputs, selects, bordered buttons, the workspace
      selector, the settings section selector.
- [x] 2.6 Restyle what ships its own colours: highlight.js on the new paper, KaTeX sitting level
      with the surrounding text, mermaid's light and dark themes.
- [x] 2.7 Remove the `--font-serif` token if no role uses it, or make it hold a serif if one does.
      It currently names a serif and holds Inter.

### Del bloque 2

- **Mermaid y highlight.js dejan de traer su paleta.** Mermaid pasa de `default`/`dark` a `base`
  con variables leídas de los tokens en tiempo de ejecución, así que el diagrama cambia con el tema
  sin un solo color escrito en `prose.js`. La sintaxis pasa de seis hex sueltos a seis tokens con
  variante clara y oscura, todos medidos contra el fondo del bloque de código: el más bajo queda en
  5.04:1.
- **El frontmatter se recorta antes de renderizar, no en el servidor.** La API sigue devolviendo el
  markdown tal cual está guardado, que es lo que el editor edita y lo que `read_page_raw` promete a
  un agente; lo que cambia es que la vista de lectura no lo pinta. Tres tests nuevos, incluido el
  que comprueba que un `---` a mitad de documento sigue siendo una regla horizontal.
- **`--fg-2` baja de 12.67:1 a 8.17:1** en claro y de 10.74:1 a 7.55:1 en oscuro. A la intensidad
  anterior no se distinguía del principal, y dos tintas que se ven igual son una tinta.
- **Los radios de tarjetas y modales ya habían subido con el valor de sus tokens**; solo los tres
  campos de entrada seguían en `--r-sm` y pasan a `--r-md`.

**Tarea 3.1 reinterpretada, y conviene decirlo.** Decía «ningún `.jsx`», pensada para que un
restyle no se convirtiera en un cambio de componentes. Tres módulos del cliente cambiaron y ninguno
por estilo: `LanguageToggle.jsx` por la colisión de clase, `markdown.js` por el frontmatter y
`prose.js` porque es el único sitio donde se configura Mermaid. Los dos primeros son defectos que
salieron en el recorrido y que decidiste arreglar aquí; el tercero es la única forma de que un
diagrama use la paleta. Ninguno mueve layout ni comportamiento.

### Del recorrido visual

Hecho en ambos temas sobre una pagina que ejercita todo: frontmatter, tablas con alineacion,
codigo, KaTeX en linea y en bloque, listas de tareas, mermaid y `<details>`.

- **La regla de datos frente a prosa funciona y se ve.** En Ajustes / Sistema la columna de valores
  se escanea sin leer las etiquetas. Es el efecto que motivo el change.
- **Un defecto encontrado y arreglado en el recorrido**: `.prose` pedia `--font-serif` desde
  siempre, y como el token contenia Inter nadie lo noto. Hacerlo honesto puso Instrument Serif en
  parrafos de 15px. El cuerpo vuelve a la cara de texto; la serif se queda en los encabezados.
- **Mermaid sigue con su lavanda** y desentona: es la tarea 2.6 y pertenece al bloque 2.
- **`--fg-2` a 12.67:1 puede ser demasiado oscuro** para texto secundario: apenas se distingue del
  principal. Es decision de diseno, no de accesibilidad, y merece mirarse en el bloque 2.

Dos hallazgos ajenos a este change, anotados para no perderlos:

- **El frontmatter se pinta como un encabezado.** Para markdown-it, `type: runbook` seguido de
  `---` es sintaxis de encabezado setext, asi que la vista de lectura lo muestra como un titulo. El
  troceador si lo quita antes de embeber; el renderizador no. Es anterior a este change y la serif
  solo lo hace mas evidente.
- **`LanguageToggle` reutiliza la clase `.theme-toggle`**, asi que un selector por esa clase acierta
  el control equivocado. Cosmetico hasta que alguien escribe un test.

## 3. What must not move

- [ ] 3.1 **Reinterpretada, ver nota.** No `.jsx` file changes. If a component needs editing to restyle it, stop: either the
      change is drifting into layout, or the component is hardcoding a colour and that is the fix.
- [x] 3.2 No motion changes. `rise`, the durations, the easing, the transitions on menus, palette
      and toasts, the skeleton pulse and the `prefers-reduced-motion` override are all untouched.
      Verify by diff, not by eye.
- [x] 3.3 No behaviour changes: nothing appears, disappears, moves or reorders.
- [x] 3.4 Verify the 44px floor still holds on coarse pointers after the radius and padding change,
      including the tree's disclosure gutter.

## 4. Verification

- [x] 4.1 Measure every contrast pair the spec requires, in both themes, and record the numbers.
- [x] 4.2 Walk the app in both themes: reader, editor with a page carrying tables, code, mermaid
      and math, the tree, search results, all six settings sections, trash, inbox, the 404 and the
      error state, and the connection indicator in its failing state.
- [x] 4.3 Confirm no flash on load with the dark theme stored.
- [x] 4.4 Confirm every asset is local: `cd frontend && npm run check`.
- [x] 4.5 Run the frontend gate and the tests: `npm run check && npm run test`.
- [x] 4.6 Run the Python gate — `app/static/style.css` ships in the image and the asset check reads
      it: `uv run ruff check . && uv run ruff format --check . && uv run pyright app tests && uv run
      pytest`.
- [x] 4.7 Confirm the change is one stylesheet and some fonts. Any other file in the diff needs a
      reason.
