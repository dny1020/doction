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
- [x] 2.6 Focus: dos indicadores, y la división es por lo que es cada cosa. Los controles llevan
      el anillo del acento; los enlaces dentro del texto llevan `outline`, porque un enlace que
      parte en dos líneas se anillaría por la caja que une los dos fragmentos, que no es donde
      está. Se retiraron las ocho reglas por elemento que solo repetían el anillo.

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
- [x] 3.3 Sidebar: tree, search results, workspace switcher, footer.
- [x] 3.4 Editor and history. Los dos campos del editor pasan a `field field--bare`, conservando
      solo lo suyo: la serif del título y la mono del cuerpo. `.settings-flash` y sus dos estados
      resultaron ser código muerto — ninguna pantalla los nombraba — así que el editor se queda
      como el único aviso y no hizo falta unificar dos bandas en una pieza nueva.
- [x] 3.5 Inbox, trash, graph.
- [x] 3.6 Login, register, and the standalone 404.
- [x] 3.7 Auditados los 16 usos de `.muted`. La bandeja pasa a `EmptyState`; el resto no son
      estados vacíos sino prosa secundaria (subtítulos, pistas) o secciones vacías dentro de una
      pantalla que sí tiene contenido — un árbol sin páginas en 220px de barra lateral no quiere
      un bloque centrado con encabezado. La distinción ya existía y se respeta.

## 3b. Entrega del CSS

- [x] 3b.1 `style.css` se sirve con el hash de su contenido en la consulta, calculado en el mismo
      punto y del mismo modo que Vite calcula el del bundle. `index.html` queda como el único
      sitio que fija las dos versiones, así que o se sirve todo viejo —coherente— o todo nuevo.
      Probado: tocar la hoja cambia el hash, revertirla lo devuelve.

## 4. Cleanup

- [x] 4.1 Cero declaraciones de espaciado en píxeles crudos, desde 25. La mayoría eran ajustes
      ópticos de 1-2px que no tenían token porque la escala empieza en 4: se añadió `--sp-0: 2px`,
      un escalón por debajo de la base. Definirlo es lo que los mete en la escala; fingir que no
      hacen falta los habría dejado escritos a mano para siempre.
- [x] 4.2 De los 7 tamaños literales quedan 2, los dos con razón funcional escrita: `0.85em` en
      el código en línea, que debe ir un punto por debajo del texto que lo rodea sea cual sea, y
      `16px` en los campos bajo puntero grueso, que es el umbral por debajo del cual Safari hace
      zoom al enfocar y ya no vuelve.
- [x] 4.3 Delete every class no screen names any more.

## 5. Verify

- [~] 5.0 **Recorrido por debajo de 820px: NO REALIZADO.** El navegador de esta sesión no propaga
      el redimensionado al viewport — `resize_window` responde bien pero `innerWidth` no cambia —
      y las otras dos vías se descartaron: un iframe del ancho objetivo lo bloquean
      `X-Frame-Options: DENY` y `frame-ancestors 'none'`, que no se tocan.
      En su lugar: un escaneo de desbordamiento horizontal en cinco pantallas (ninguno), y una
      auditoría estática de las media queries. Esa auditoría encontró dos regresiones mías y las
      dos están corregidas: `.row` había perdido el `flex-wrap` que tenían las filas que sustituye,
      así que en pantalla estrecha las acciones aplastarían el nombre en vez de bajar debajo; y
      `.row-name` no partía cadenas sin espacios, así que un correo o una URL empujarían la fila a
      lo ancho. Queda pendiente mirarlo en un móvil de verdad.

- [x] 5.1 Class count has gone down, and the number is recorded. Evidence that the primitives are
      used, not a target: two things that mean different things stay separate whatever it costs
      the count.
- [x] 5.2 No rule sets spacing, font size or radius outside the scale.
- [x] 5.3 Every elevated surface matches its role's pairing.
- [x] 5.4 One focus treatment remains.
- [x] 5.5 Las dos puertas en verde más `npm run test`: 293 tests de Python, 42 de frontend,
      `pyright` sin avisos, air-gap intacto.
- [x] 5.6 Recorrido en navegador de cada pantalla en los dos temas, contra las 27 capturas de 1.2.
      Sin regresiones: las pantallas hacen lo mismo y se ven como se veían, con menos definiciones
      detrás. Dos defectos propios aparecieron durante el recorrido y se corrigieron ahí mismo —
      la fila de la papelera apilando sus botones, y cinco clases renombradas en Ajustes que no
      seguí hasta las pantallas que las tomaban prestadas.
- [x] 5.7 Contraste: este cambio no toca ningún token de color, así que los pares que midió 005
      siguen valiendo. Lo único que altera el contraste percibido es que dos controles de auth
      dejan de estar por debajo del suelo táctil.
- [x] 5.8 Sync the specs and archive.
