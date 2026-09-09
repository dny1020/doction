# Sistema visual de doction

Este documento describe el diseño **tal como está implementado**, no como se
pretendía. Cada valor de aquí está en `app/static/style.css` y se puede verificar
leyéndolo. Cuando los dos discrepan, el defecto está en este documento antes que
en la hoja de estilos.

Concepto: cuaderno técnico moderno. Cálido, editorial, sobrio, sin apariencia de
plantilla generada.

---

## 1. Intención

doction debe sentirse como un sistema de conocimiento técnico de calidad, no como
un panel de control ni como una aplicación de notas genérica.

### Principios

1. El documento es el protagonista visual.
2. Pocas decisiones visuales, pero deliberadas.
3. El material se siente más de lo que se ve.
4. La jerarquía se construye con tipografía, ritmo, alineación y tono, no con
   tarjetas.
5. Lo técnico usa monoespaciada, densidad controlada y color restringido.
6. El diseño no añade ni quita funcionalidad, rutas, paneles ni información.

### Anti-patrones

No implementar degradados morados o azul eléctrico, fondos con ruido visible,
pergamino o estética retro, todo dentro de tarjetas, bordes de más de 8px,
píldoras salvo las genuinamente redondas, sombras grandes o repetidas,
glassmorphism, etiquetas «AI» o «MCP» como decoración, paneles o métricas
inventados, grafos neón, ni imitaciones de Notion, GitBook, Obsidian o Linear.

---

## 2. Color

Todo el color va en `oklch()`. Las ratios de contraste se miden siempre contra la
**peor** superficie en la que el token aparece, nunca contra la página: un valor
medido solo contra el lienzo pasa la revisión y falla luego en una fila con el
puntero encima.

### Tema claro

```css
:root {
  /* Superficies: papel técnico cálido */
  --background:     oklch(0.965 0.012 94);
  --surface:        oklch(0.982 0.008 92);
  --surface-raised: oklch(0.994 0.004 90);
  --surface-muted:  oklch(0.936 0.016 91);
  --surface-inset:  oklch(0.908 0.020 91);

  /* Tinta: verde oscuro, no azul */
  --ink:        oklch(0.245 0.030 151);  /* 15.00:1 */
  --ink-strong: oklch(0.185 0.026 150);
  --ink-muted:  oklch(0.445 0.025 151);  /*  7.01:1 */
  --ink-subtle: oklch(0.501 0.020 151);  /*  4.50:1 */

  /* Verde funcional: lo que se pulsa y lo que se lee */
  --green:       oklch(0.365 0.055 151);  /* 9.69:1 */
  --green-hover: oklch(0.315 0.052 151);
  --green-soft:  oklch(0.915 0.030 151);
  --green-ring:  oklch(0.365 0.055 151 / 0.60);  /* 3.03:1 */

  /* Naranja: señal, no color dominante */
  --orange:     oklch(0.635 0.155 52);   /* decoración */
  --orange-ink: oklch(0.515 0.133 52);   /* 4.50:1, marcas que informan */

  /* Líneas */
  --border-subtle:  oklch(0.875 0.018 90);
  --border-default: oklch(0.600 0.024 90);  /* 3.00:1, delimita controles */

  /* Estado */
  --danger:      oklch(0.525 0.185 28);  /* 4.51:1 */
  --danger-soft: oklch(0.911 0.046 28);
  --ok-soft:     oklch(0.981 0.030 148);

  /* Superficies compuestas, precalculadas */
  --callout-bg: oklch(0.960 0.022 63.2);
  --input-bg:   oklch(0.987 0.007 97.3);

  /* Código */
  --code-inline-bg: oklch(0.915 0.030 151);
  --code-bg:        oklch(0.205 0.024 151);
  --code-text:      oklch(0.930 0.018 96);
  --code-muted:     oklch(0.690 0.025 120);
  --code-green:     oklch(0.760 0.110 142);
  --code-orange:    oklch(0.780 0.130 61);
}
```

### Tema oscuro

El selector es `[data-theme="dark"]` sobre `<html>`, **no** `.dark`: de él
dependen el conmutador de tema, el script antiparpadeo de `index.html` y
Preferencias.

```css
[data-theme="dark"] {
  --background:     oklch(0.170 0.006 150);
  --surface:        oklch(0.205 0.007 150);
  --surface-raised: oklch(0.238 0.008 150);
  --surface-muted:  oklch(0.238 0.008 150);
  --surface-inset:  oklch(0.265 0.008 150);

  --ink:        oklch(0.925 0.016 93);   /* 12.24:1 */
  --ink-strong: oklch(0.975 0.007 93);
  --ink-muted:  oklch(0.720 0.018 100);  /*  6.16:1 */
  --ink-subtle: oklch(0.639 0.018 110);  /*  4.54:1 */

  --green:      oklch(0.745 0.090 145);  /* 6.97:1 */
  --green-ring: oklch(0.745 0.090 145 / 0.53);  /* 3.00:1 */
  --orange:     oklch(0.735 0.135 57);   /* 6.27:1 */

  --border-default: oklch(0.538 0.025 150);  /* 3.03:1 */
  --code-bg:        oklch(0.115 0.014 150);
}
```

**El croma del oscuro es deliberadamente bajo.** Con 0.018–0.023 el carbón se
lee verde y, sumado al chrome, la aplicación entera queda teñida. El verde se
reserva para donde dice algo: acento, elemento activo y código.

### El naranja se parte por consecuencia

Sobre papel el naranja de identidad mide 2.48:1, por debajo del 3:1 que necesita
una marca que informa. Por eso hay dos:

- `--orange` **decora** y puede no verse: un filete, un glifo junto a una palabra
  que ya está escrita. Si nadie pierde nada por no verlo, es este.
- `--orange-ink` **informa** y por eso mide 4.50:1.

La pregunta que decide cuál usar es qué pierde quien no vea la marca.

Sobre carbón el naranja sí llega, así que en tema oscuro un solo valor cubre los
dos papeles. La regla no cambia entre temas; cambia cuántos tonos hacen falta
para cumplirla.

---

## 3. Tipografía

Tres familias, autohospedadas en `app/static/vendor/fonts/`. doction se sirve en
LAN, en VPN y a veces sin salida a internet, así que una petición a un CDN
fallaría justo donde más se usa.

```css
--font-ui:      'Manrope', 'Inter', system-ui, -apple-system, sans-serif;
--font-display: 'Instrument Serif', Georgia, 'Times New Roman', serif;
--font-mono:    'JetBrains Mono', ui-monospace, "SF Mono", SFMono-Regular, Menlo, monospace;
--font-data:    var(--font-mono);
```

- **Manrope** — navegación, cuerpo, formularios, botones, tablas y controles.
  Vendorizada en 400, 500 y 600.
- **Instrument Serif** — solo el título de página y el H1 del documento. Un peso.
- **JetBrains Mono** — código, rutas, atajos, marcas de tiempo y metadatos. Nunca
  una frase. Esta última regla es la que hace que la aplicación se lea como
  documentación y no como una aplicación con contenido dentro.

`Inter` figura en la cadena pero **no se vendoriza**: sería pagar dos veces por un
caso que no puede ocurrir, porque ambas caras vendrían del mismo origen. El
respaldo real es `system-ui`.

### Escala

```css
--text-xs:   0.6875rem;  /* 11px — metadatos */
--text-sm:   0.75rem;    /* 12px */
--text-base: 0.875rem;   /* 14px — interfaz */
--text-nav:  0.8125rem;  /* 13px — navegación */
--text-md:   1rem;       /* 16px — cuerpo del documento */
--text-lg:   1.125rem;   /* 18px */
--text-xl:   1.375rem;   /* 22px */
--text-2xl:  1.75rem;    /* 28px */
--text-3xl:  2.25rem;    /* 36px */
--text-4xl:  3.25rem;    /* 52px */
```

| Elemento | Familia | Tamaño | Interlínea |
|---|---|---|---|
| Título de página | display | 52px | 1.03 |
| H1 del documento | display | 36px | 1.15 |
| H2 | interfaz, 600 | 22px | 1.3 |
| H3 | interfaz, 600 | 16px | 1.45 |
| Cuerpo del documento | interfaz | 16px | 1.78 |
| Interfaz | interfaz | 14px | 1.45 |
| Navegación | interfaz | 13px | 1.3 |
| Metadatos | datos | 11px | 1.45 |

Los H2 y H3 van en la cara de interfaz, no en la serif: a 22 y 16px la serif
tiene el ojo demasiado pequeño para pesar como un encabezado.

Peso 400 para texto, 500 para controles y navegación, 600 solo para encabezados
de interfaz. Evitar 700.

---

## 4. Retícula

```css
--sidebar-width:      280px;
--toc-width:          220px;
--topbar-height:       56px;
--document-max-width: 760px;
--document-gutter:     72px;
--shell-max-width:   1720px;
```

```text
Viewport
├── Sidebar fijo: 280px, pegado al borde
└── Área principal
    ├── Barra superior: 56px
    └── Zona de documento (máx. 1720px)
        ├── Margen izquierdo: 72px
        ├── Columna de lectura: máx. 760px
        ├── Separación: 96px
        └── Índice: 220px
```

Reglas de composición:

- El sidebar **se ancla al borde de la ventana**. El tope de 1720px limita el
  contenido, no el shell: puesto sobre el conjunto, el panel quedaba flotando con
  el fondo asomando a su izquierda.
- El contenido **arranca** a 72px del lateral. Centrarlo haría que el margen
  dependiera del ancho de la ventana.
- El índice respira a 96px del documento. Es texto pequeño y gris junto a texto de
  lectura, y el aire es lo único que los separa.
- Nada de una tarjeta blanca gigante alrededor del documento.

---

## 5. Espaciado

Base de 4px, más un escalón óptico por debajo.

```css
--space-0:  2px;   --space-1:  4px;   --space-2:  8px;   --space-3: 12px;
--space-4: 16px;   --space-5: 20px;   --space-6: 24px;   --space-7: 28px;
--space-8: 32px;   --space-9: 36px;   --space-12: 48px;  --space-14: 56px;
--space-16: 64px;  --space-20: 80px;  --space-24: 96px;
```

`--space-0` existe porque hay diecisiete sitios con separaciones de 2px bajo texto
de 11 y 12px, y subirlos a 4 engorda cada insignia y cada marca en línea.

Ritmo del documento: 56px sobre un H2, 36px sobre un H3, 24px bajo un párrafo,
28px alrededor de un bloque de código o una nota.

---

## 6. Radio, bordes y sombras

```css
--radius-xs: 2px;   --radius-sm: 4px;   --radius-md: 6px;   --radius-lg: 8px;
--radius-pill: 999px;

--shadow-1: 0 1px 2px  oklch(0.20 0.02 150 / 0.05);
--shadow-2: 0 4px 14px oklch(0.20 0.02 150 / 0.07);
--shadow-3: 0 12px 32px oklch(0.20 0.02 150 / 0.10);
```

Radio estándar de interfaz 4px; código 6px; modales 8px. La píldora sobrevive
solo en lo genuinamente redondo: avatares y puntos de tema.

Las sombras son para lo que flota —menús, ventanas emergentes, modales—. Una
superficie que se apoya en la página lleva línea, no sombra.

---

## 7. Material

El material es tonal, no textural. **Nada de ruido, grano visible, texturas ni
imágenes de papel.**

```css
--material: linear-gradient(
  112deg,
  var(--material-sheen) 0%,
  transparent 32%,
  var(--material-warm) 100%
);
```

La fuerza cambia entre temas: sobre carbón, el mismo valor que sobre papel pinta
una banda diagonal con borde duro cruzando el documento en vez de sentirse.

| | claro | oscuro |
|---|---|---|
| `--material-sheen` | 0.18 | 0.030 |
| `--material-warm` | 0.05 | 0.018 |

---

## 8. Chrome

La navegación **no es papel**: es una región de tinta verde oscura, en los dos
temas, y el documento es la superficie clara a su lado. Ese contraste es lo que da
jerarquía: el chrome recede, el documento manda.

```css
--nav-bg:        oklch(0.145 0.028 151);  /* extremo superior del degradado */
--nav-bg-end:    oklch(0.115 0.022 151);  /* extremo inferior */
--nav-hover:     oklch(0.185 0.030 151);
--nav-active-bg: oklch(0.310 0.040 151 / 0.72);
--nav-edge:      oklch(0.330 0.030 151);  /* el canto, medido contra el LIENZO */

--nav-ink:            oklch(0.928 0.014 93);   /* 11.37:1 */
--nav-ink-strong:     oklch(0.975 0.007 93);   /* 13.08:1 */
--nav-ink-muted:      oklch(0.720 0.018 100);  /*  5.68:1 */
--nav-ink-subtle:     oklch(0.659 0.018 110);  /*  4.52:1 */
--nav-border-default: oklch(0.556 0.025 150);  /*  3.01:1 */
--nav-green:          oklch(0.745 0.090 145);  /*  6.42:1 */
--nav-orange:         oklch(0.635 0.155 52);   /*  3.88:1 */
```

El chrome **es más oscuro que el documento también en tema oscuro**. Si queda más
claro, el panel avanza en vez de recederse y la aplicación se lee como una sola
masa.

Sus cuatro suelos reales son los dos extremos del degradado más el fondo del
elemento activo compuesto sobre cada uno. Todo lo que va encima se mide contra el
peor de los cuatro.

El elemento activo lleva superficie verde tenue y un filete izquierdo de 2px en
naranja, **no** un relleno: el naranja señala el borde y el peso y la tinta hacen
el resto, así que el color nunca viaja solo.

### Cómo está implementado

El chrome redefine los **nombres** de token dentro de su ámbito en lugar de
reescribir las reglas que contiene. `var()` se resuelve en el elemento que hace
match con las propiedades que ese elemento hereda, así que todo lo que vive dentro
se re-tematiza solo.

Dos consecuencias que se aprendieron midiendo:

- **Todo nombre que el chrome redefina hay que redefinirlo también en la reentrada
  al lienzo.** Un nombre olvidado no falla ruidosamente: resuelve al valor del
  lienzo, que es el equivocado justo donde se olvidó.
- **Lo que se declara dentro pero se pinta fuera tiene que volver al lienzo.** El
  diálogo de mover y renombrar vive en el árbol pero `showModal()` lo pinta
  centrado sobre el documento; sin devolverlo, salía oscuro mientras el diálogo
  idéntico del resto de la aplicación salía claro.

### El suelo no puede aclararse

El disco del avatar toma su color de un `style` inline, no de un token, y es un
límite de control que necesita 3:1. Sobre el suelo actual mide 3.68:1. Aclarar el
chrome lo baja por debajo del umbral sin que nada en el sidebar lo delate.

---

## 9. Documento

- Encabezado con aire arriba y una línea que lo cierra abajo.
- Migas de pan en la cara de datos, mayúsculas, 11px. Su separador lleva el
  naranja decorativo: es `aria-hidden`, así que no debe contraste a nadie.
- Franja de metadatos con los dos campos que existen, fecha de actualización y
  último editor. No hay propietario ni tiempo de lectura.
- Enlaces en verde. Un wikilink a una página que aún no existe se pinta apagado:
  allí es algo por escribir, no un error.
- Separadores: una línea fina y mucho espacio vertical.
- Ninguna sección del markdown va dentro de un contenedor.

### Notas

Filete izquierdo de 2px en naranja sobre un fondo cálido tenue, sin cursiva:
párrafos enteros en cursiva se leen peor.

### Código

El **bloque** es una losa oscura, un inset de terminal dentro de un libro. Su
color de texto se declara en el bloque, no en el resaltador: el resaltado solo se
aplica a las vallas que declaran lenguaje, y una valla pelada heredaría la tinta
del documento sobre la losa.

El **código en línea** no comparte esa superficie. Es tipografía dentro de una
frase, va en verde sobre verde tenue; sobre la losa cada `` `foo` `` de un párrafo
sería una pastilla negra.

El resaltado se reduce a tres señales sobre la tinta del código: comentarios
apagados, cadenas en verde, números en naranja. El resto se queda en `--code-text`.

---

## 10. Índice

Ancho 220px, posición pegajosa, a 96px del documento. Tipografía de interfaz a
12px y el rótulo en datos a 11px. Sin tarjeta ni fondo flotante.

El estado activo tiene **un solo portador**: el filete naranja. El texto sube a
tinta principal, que ya es contraste suficiente sin depender del color. Decirlo
con el color y con el filete a la vez sube el volumen del índice entero.

---

## 11. Controles

```css
.button-primary  { height: 32px; background: var(--green); border-radius: var(--radius-sm); }
.button-secondary{ height: 32px; background: transparent; border: 1px solid var(--border-default); }
.input           { min-height: 36px; background: var(--input-bg); border: 1px solid var(--border-default); }
.input:focus     { border-color: var(--green); box-shadow: 0 0 0 3px var(--green-ring); }
```

El anillo de foco mide 3.03:1 en claro y 3.00:1 en oscuro. Un indicador de foco
necesita 3:1, y este ha tenido que subirse dos veces por quedarse corto: cualquier
propuesta de bajarlo va contra una corrección deliberada.

### Barra de desplazamiento

Propia, no la del sistema. Definida una vez y heredada por los tres sitios que
desplazan —árbol, menú de workspaces e índice—, así que dentro del chrome se
re-tematiza sola. 8px de ancho, pulgar redondeado a su propio ancho y más fino que
la pista gracias a un borde transparente.

### Un control, una acción

Con el sidebar plegado solo debe verse **un** botón para desplegarlo, el de la
barra superior. El botón flotante que existía para eso se retiró cuando la barra
pasó a verse a todos los anchos.

---

## 12. Grafo

Nodos sin brillo ni efectos. El nodo en reposo es una superficie con contorno
verde; el activo se rellena de verde y lleva una señal naranja mínima en el
contorno. Las relaciones son líneas cartográficas, no constelaciones. El fondo usa
profundidad tonal suave, sin cuadrículas.

Dos estados propios de doction que el lenguaje general no nombra: una página
**huérfana** se apaga en vez de alarmar, porque no es un error sino algo que nadie
ha conectado todavía; un enlace **roto** se dibuja discontinuo en el tono de
peligro, porque aquí sí es un hallazgo.

---

## 13. Movimiento

```css
--ease-standard: cubic-bezier(0.2, 0, 0, 1);
--duration-fast: 120ms;   /* color, fondo, borde */
--duration-base: 180ms;   /* sombra, opacidad */
--duration-slow: 240ms;   /* el cajón móvil */
```

Solo color, fondo, borde, sombra y opacidad. Nada de rebotes, entradas dramáticas,
animaciones continuas ni parallax.

---

## 14. Cómo se verifica

Estas reglas se comprueban, no se confían.

- **Contraste medido desde la propia hoja de estilos**, no desde una tabla escrita
  a mano: se parsean los bloques de token y se calcula cada par contra los seis
  suelos —lienzo claro, lienzo oscuro, los dos extremos del chrome, la losa de
  código y el fondo compuesto de las notas—. Cero fallos es la condición de
  entrega.
- **Gamut**: un color fuera de sRGB lo remapea el navegador a algo que el autor no
  eligió, así que una ratio calculada sobre el valor original describe un color que
  nadie ve.
- **Ningún literal de color fuera de los bloques de token**, y ningún token sin
  llamadas.
- **En un navegador de verdad, no solo en capturas.** Dos defectos de la última
  ronda —una banda diagonal en el material y una nota marrón saturada— eran
  evidentes en pantalla y no lo fueron en 102 capturas automatizadas.
- **Reconstruir antes de medir.** La hoja se enlaza con un hash de contenido que
  solo cambia al construir; sin `make build-web` la medición describe la hoja
  anterior.
