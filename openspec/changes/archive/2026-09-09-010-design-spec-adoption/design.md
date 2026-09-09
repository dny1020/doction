# Design

## 1. Why the rename comes first, and separately

The document's rules can be copied literally only once the code speaks its vocabulary.
Renaming afterwards would mean translating every rule twice — into the old names to apply it,
then out of them again.

But the rename must be its own commit, because the two halves have different proofs. A rename
is correct when **nothing renders differently**; a colour change is correct when **every ratio
passes**. Combined, neither proof holds: a rendering difference could be the new colour or a
missed rename, and there is no way to tell them apart.

### It is a permutation, and that is what makes it dangerous

Three names exist in both vocabularies with different meanings.

| name | in the code today | in the document |
|---|---|---|
| `--border-strong` | the control boundary, 3.07:1, 20 call sites | a hover-only line, 2.63:1 |
| `--code-bg` | the **light** inline-code tint | the **dark** block slab |
| `--text-xs` … `--text-3xl` | 12 / 14 / 16 / 18 / 22 / 30 / 42 | shifted one step down |

Leaving `--border-strong` alone silently re-points twenty control borders at a value that fails
3:1. Leaving `--code-bg` alone turns every `` `foo` `` inside a paragraph into a black pill —
the exact regression the split in 009 was written to prevent. And the type scale overlaps
itself, so a sequential substitution cascades: rewriting `xs`→`sm` first and then `sm`→`base`
moves the original `xs` sites two steps.

The correct shapes are a permutation through intermediate names for the scale, and for the
lines: `--border` → `--border-subtle`, `--border-strong` → `--border-default`, and only *then*
a new third `--border-strong`.

### Names cannot prove it

Both vocabularies are valid identifiers, so no `grep` distinguishes a correct permutation from
a scrambled one. The proof is a **recorded dump of resolved values** — every font-size, padding,
margin, gap, border, colour and background on a fixed element list — captured before and
compared after. Byte-identical or the rename is wrong. The stylesheet is served raw with no
build step, so this is a direct comparison.

### The blast radius reaches outside the stylesheet

`frontend/src/prose.js` reads nine token names at runtime to build the Mermaid palette. A
CSS-only rename makes all nine return the empty string, Mermaid falls back to its own default,
and every diagram renders lavender — an anti-pattern the document names explicitly in §14. It
is invisible in a CSS diff and on every screen that has no diagram.

## 2. Decision: correct the document's values, and say so

The document is the source of truth for *intent*. It is not measured, and five of its values
would regress accessibility work this repository did on purpose. The requirement that governs
this is already in the spec: derive the nearest passing value on the same hue and write it back
with its measurement.

The focus ring is the clearest case. The document specifies alpha `0.13`, which composites to
**1.25:1**. Change 009 fixed that exact class of defect, raising the ring from 1.80:1 to
4.33:1, and recorded why in a comment. Shipping the document's value would undo a fix younger
than a day.

Two orange values also fall outside sRGB. A ratio computed from an out-of-gamut value describes
a colour the browser will never paint, so they are brought inside deliberately rather than left
to be mapped.

## 3. Decision: no `color-mix()`, and no `@supports`

The document uses `color-mix(in oklch, …)` for the callout ground and the input background.
`oklch()` shipped in Safari 15.4; `color-mix()` only in 16.2. In that window a custom property
holding `color-mix()` parses fine and then becomes invalid at substitution, which falls back to
the property's *initial* value — transparent — not to a previous declaration. Transparent
inputs and transparent callouts, silently, on a client fleet this deployment does not control.

Both are precomputed as flat tokens. That removes the gap and makes them measurable, which
`color-mix()` never would be.

An `@supports` fallback is rejected for a subtler reason: placed after the dark block it would
have equal specificity and win on source order, rendering dark mode in light values on exactly
the old browsers it was meant to help. Half a fallback is worse than none. A browser floor is
set and documented instead.

## 4. Decision: `.dark` is not adopted

The document writes its dark block as `.dark`. The application selects on
`[data-theme="dark"]` at the root element, and `theme.js`, the anti-flash script in
`index.html` and a `MutationObserver` in Preferences all depend on it. The values are mapped to
the existing selector; the selector is not touched. This is the first place where copying the
document literally is simply wrong.

## 5. Decision: the top bar is shown, then cleaned

Its DOM node already renders at every width and is hidden by one CSS declaration, so §4's 56px
bar costs nothing structurally. What it would *contain* is the problem: a toggle that can only
open an already-open sidebar, a title that would appear for the third time in the top 200px,
and an overflow menu holding three of the four buttons immediately below it.

The bar is shown, and CSS hides the inert toggle and the duplicated action row. Making it
genuinely useful — a section name in settings, a title on the graph route, a right-hand slot
that is not a duplicate — needs JSX and is deferred with the reason recorded.

## 6. What the sidebar scope means for all of this

`.sidebar` redefines nineteen names and `.sidebar .confirm-dialog` maps twenty-two back. Every
rename applies in all four scopes or the chrome leaks canvas values exactly where one was
missed — a failure that already happened once in this file, when the first draft of that block
omitted nine tokens and the active tree item measured 1.06:1.

One semantic conflict: the document puts both the sunken well and the hover ground on
`--surface-muted`. The sidebar maps them to two different values and paints itself with one of
them, so merging would delete its hover state. The value-preserving map is used instead
(`--surface-sunken` → `--surface-muted`, `--surface-hover` → `--surface-inset`), and the
divergence from the document's prose is recorded rather than discovered later.

## 7. Verification

The rename and the colour move are gated separately, as above. Beyond that: zero contrast
failures across six grounds — light canvas, dark canvas, both chrome grounds, the code ground
and the composed callout — zero out-of-gamut values, a Mermaid diagram rendering in the
application's palette, and the 102-screen capture in both themes at three widths.

---

# 8. Registro de desviaciones

`DESIGN.md` no está versionado en el repositorio, así que las desviaciones que el requisito de
gobernanza manda escribir de vuelta en él viven aquí. Este archivo es el registro: si algún día
el documento vuelve al repo, esta sección es lo que hay que trasladarle.

## 8.1 Correcciones por medida

Todas conservan el tono y el papel que el documento especifica; solo se mueve la luminosidad, o
el croma cuando el color salía del gamut sRGB. Las ratios son contra la **peor** de las
superficies en que cada token aparece, no contra la página.

| token | especificado | medido | implementado | medido |
|---|---|---|---|---|
| anillo de foco (claro) | `/ 0.13` | 1.24:1 | `/ 0.60` | 3.03:1 |
| anillo de foco (oscuro) | `/ 0.13` | 1.06:1 | `/ 0.53` | 3.00:1 |
| anillo de foco (chrome) | `/ 0.13` | — | `/ 0.55` | 3.00:1 |
| `--border-default` claro | `oklch(0.818 0.024 90)` | 1.64:1 | `oklch(0.600 0.024 90)` | 3.00:1 |
| `--border-default` oscuro | `oklch(0.345 0.025 150)` | 1.33:1 | `oklch(0.538 0.025 150)` | 3.01:1 |
| `--ink-subtle` claro | `oklch(0.590 0.020 151)` | 3.80:1 | `oklch(0.501 0.020 151)` | 4.50:1 |
| `--ink-subtle` oscuro | `oklch(0.550 0.018 110)` | 3.14:1 | `oklch(0.639 0.018 110)` | 4.51:1 |
| `--danger` claro | `oklch(0.590 0.185 28)` | 4.20:1 | `oklch(0.525 0.185 28)` | 4.51:1 |
| `--orange-soft` | croma 0.046 | fuera de gamut | croma 0.041 | dentro |
| `--orange-hover` | croma 0.155 | fuera de gamut | croma 0.154 | dentro |

El anillo de foco es el caso que más importa: la ronda anterior lo había subido de 1.80:1 a
4.33:1 y dejado escrito por qué, así que adoptar el valor del documento habría deshecho una
corrección de accesibilidad de menos de un día.

## 8.2 Lo que no se implementó, y por qué

- **`--warning` y `--success`.** Ninguna regla los usa, ni del documento ni del código, y un
  token sin llamadas no debe existir. Si hacen falta, el verde legible es
  `oklch(0.494 0.080 148)`; el ámbar a croma 0.145 no alcanza 4.5:1 en ningún nivel dentro de
  gamut, así que habrá que bajarle croma o reservarlo para superficies.
- **`color-mix()`.** Safari 15.4 a 16.1 lo rechaza y falla en silencio al valor inicial, que en
  un fondo es transparente: campos y avisos invisibles en un parque de clientes que este
  despliegue no controla. Sus dos usos van precalculados como tokens planos, que además así son
  medibles.
- **Inter vendorizada.** §3 la nombra solo como respaldo de Manrope. Vendorizar dos caras de
  interfaz paga dos veces por un caso que no puede ocurrir, porque ambas vendrían del mismo
  origen. El respaldo real es `system-ui`.
- **El selector `.dark`.** La aplicación selecciona por `[data-theme="dark"]` y de ahí dependen
  el conmutador, el script antiparpadeo y Preferencias. Se mapean los valores; el selector no.

## 8.3 Lo que se añadió y el documento no nombra

- **`--orange-ink`** `oklch(0.515 0.133 52)`, 4.50:1. El naranja de identidad decora y puede no
  verse; una marca que informa tiene que medir, y a croma 0.155 no llega en ningún nivel.
- **`--space-0`, `--space-7`, `--space-9`, `--space-14`.** El ritmo de §5 pide 28, 36 y 56px y
  su propia escala no contiene ninguno; `--space-0` es el escalón óptico de 2px bajo texto de
  11 y 12px. Van en la escala en lugar de sueltos en una regla.
- **`--text-nav`**, 13px. §3 pone la navegación ahí y ningún paso de la escala cae en ese valor.
- **`--nav-*`**, la paleta del chrome, y **`--canvas-*`**, los alias que devuelven al lienzo lo
  que se declara dentro del sidebar pero se pinta fuera.

## 8.4 La paleta de sintaxis se reduce a tres señales

El documento nombra seis tokens de código y ninguno separa palabra clave de variable. El
resaltado queda en comentarios apagados, cadenas en verde y números en naranja; el resto se
queda en la tinta del código. Eso es lo que «restrained» significa con el vocabulario que hay.

## 8.5 La barra superior, y lo que aún no puede hacer

Se implementó a 56px mostrando el nodo que ya existía en el DOM y solo ocultaba el CSS. Dos
cosas hubo que limpiar con selectores:

- Su botón de menú solo sabe **abrir** una barra lateral que en escritorio ya está abierta. Se
  oculta mientras el sidebar esté desplegado. El botón `⋯` del lector lleva la misma clase, así
  que el selector tiene que ser de hijo directo o los oculta los dos.
- Su menú repite tres de los cuatro botones del lector. Esa fila se retira en escritorio,
  **salvo Delete**: destruir no se esconde en un desplegable de tres puntos.

Lo que necesita JSX y queda pendiente: en `/settings` muestra siempre la misma palabra; en la
vista de grafo y en la raíz del workspace sale **vacía**, porque el título se deriva de la URL y
ninguna de las dos nombra una página; parpadea en frío, porque se resuelve contra el árbol que
llega por red; y en el editor repite el título que el propio editor ya tiene en su campo.

## 8.6 El grafo se adaptó, no se copió

Los selectores de §12 suponen un DOM que no existe: el nodo es un `<g>` que envuelve un
`circle` y un `text`, y dos de sus clases no tienen contrapartida. Los estados propios de
doction que §12 no nombra se quedan: una página huérfana se apaga en vez de alarmar, y un
enlace roto se dibuja discontinuo en el tono de peligro.

El contorno naranja del nodo activo mide 2.87:1 contra su propio relleno, por debajo del 3:1 de
una marca que informa. Puede, porque no informa solo: el estado lo llevan el relleno y la tinta
del rótulo. Es naranja decorativo.

## 8.7 Lo que solo apareció en un navegador de verdad

Dos defectos que 102 capturas automatizadas no hicieron evidentes, ambos en tema oscuro.

- **El material de §7 pintaba una banda.** Con el mismo valor en ambos temas, el blanco al 18%
  sobre carbón dibuja una franja diagonal con borde duro donde el degradado llega a
  `transparent`. §7 pide un material que se sienta más de lo que se ve. Atenuado a una sexta
  parte en oscuro, conservando ángulo y paradas.
- **El callout oscuro salía marrón saturado**, porque ese valor se puso a ojo en vez de
  derivarlo. Componiendo la mezcla de §9 sobre la superficie de su tema da
  `oklch(0.248 0.030 72.5)`. El fondo de los campos tenía el mismo origen y se corrigió igual.

Es el argumento a favor de que la verificación de una ronda visual no puede ser solo un
comparador de imágenes: las dos eran evidentes en cuanto se miró la pantalla.
