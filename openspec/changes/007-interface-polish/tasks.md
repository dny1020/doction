# Tasks

Each block ends with a number that can be checked by grep, so "done" is not a matter of taste.

## 1. Baseline

- [x] 1.1 Record today's numbers in `design.md`. Measured: 310 classes in 75 families, 13 list
      containers, 19 row treatments, 7 field definitions, 11 elevated surfaces across 5 radius +
      shadow pairings, 25 raw-pixel spacing declarations, 7 font sizes outside the scale, 4 focus
      declarations in 2 visual languages.
- [x] 1.2 Screenshot every screen in both themes before touching anything. 27 captures at
      879×915 against a seeded workspace, indexed in the scratchpad. Light: reader, editor, graph,
      inbox, trash, the six settings sections, sidebar search, command palette, quick capture, and
      both 404s. Dark: reader, editor, graph, inbox, trash, history, three settings sections,
      login, register.

## 2. The primitives

- [x] 2.1 Surface: three roles, one radius + shadow pairing each. Fix `.settings-select-menu` and
      `.conn-detail` to the raised pairing, and give panels a line instead of a shadow.
- [x] 2.2 List and Row: one container, one row, separators as a modifier on the list.
- [x] 2.3 Field: one input. The bare ones — editor textarea, title, palette — become a documented
      modifier rather than separate controls.
- [x] 2.4 Section label: one, replacing the four eyebrow and card-title variants.
- [x] 2.5 Meta: one, in the data face at the smallest scale size, replacing the nine per-screen
      spellings.
- [ ] 2.6 Focus: keep the accent ring, remove the outline-with-offset, and check every focusable
      element still shows it.

## 3. Re-express the screens

No screen changes what it renders. Each one stops naming its own classes and names the shared ones.

- [x] 3.1 Settings, all six sections — the largest family at 33 classes, and the one where a row
      already means the most different things. Verificado contra el baseline: las seis salen
      idénticas con menos definiciones detrás. `token-*` se retiró entera; lo que Webhooks le
      tomaba prestado se renombró a `secret-*` y `add-form`, porque el secreto de un webhook no
      es un token y el nombre mentía.
- [x] 3.2 Reader: subpages, relations, mentions, table of contents. El cuerpo del documento no se
      toca — es lo único que esta pantalla tiene que hacer bien. Cambia lo que lo rodea: las
      subpáginas se apoyan en `.card` con una excepción declarada para el relleno y el puntero,
      las menciones y las relacionadas pasan a `.rows`/`.row`, y los tres «eyebrow» de la
      aplicación (barra lateral, subpáginas, índice) eran la misma etiqueta escrita tres veces,
      dos de ellas a 10.5px, por debajo del suelo de la escala.
- [ ] 3.3 Sidebar: tree, search results, workspace switcher, footer.
- [ ] 3.4 Editor and history.
- [ ] 3.5 Inbox, trash, graph.
- [ ] 3.6 Login, register, and the standalone 404.
- [ ] 3.7 Every empty case renders `EmptyState`, including the ones that are a bare paragraph now.

## 3b. Entrega del CSS

- [x] 3b.1 `style.css` se sirve con el hash de su contenido en la consulta, calculado en el mismo
      punto y del mismo modo que Vite calcula el del bundle. `index.html` queda como el único
      sitio que fija las dos versiones, así que o se sirve todo viejo —coherente— o todo nuevo.
      Probado: tocar la hoja cambia el hash, revertirla lo devuelve.

## 4. Cleanup

- [ ] 4.1 Remove the 25 raw-pixel spacing declarations.
- [ ] 4.2 Remove the 7 literal font sizes; nothing below the smallest token.
- [ ] 4.3 Delete every class no screen names any more.

## 5. Verify

- [ ] 5.1 Class count has gone down, and the number is recorded. Evidence that the primitives are
      used, not a target: two things that mean different things stay separate whatever it costs
      the count.
- [ ] 5.2 No rule sets spacing, font size or radius outside the scale.
- [ ] 5.3 Every elevated surface matches its role's pairing.
- [ ] 5.4 One focus treatment remains.
- [ ] 5.5 Both gates green, plus `npm run test`.
- [ ] 5.6 Browser walkthrough of every screen in both themes, compared against the 1.2 screenshots.
      Any difference that is not the intended consistency is a regression.
- [ ] 5.7 Contrast holds: re-measure the pairs 005 fixed, and any new one this change introduces.
- [ ] 5.8 Sync the specs and archive.
