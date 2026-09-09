# Correcciones por medida

Derivadas con el verificador propio contra el peor de los cuatro suelos claros del documento
(`--background`, `--surface`, `--surface-muted`, `--surface-inset`). Se aplican en la fase 2 y
se escriben de vuelta en `DESIGN.md`.

| token | en el documento | medido | corregido | medido |
|---|---|---|---|---|
| anillo de foco | `oklch(0.365 0.055 151 / 0.13)` | 1.24:1 | `/ 0.60` | 3.03:1 |
| `--border-default` | `oklch(0.818 0.024 90)` | 1.64:1 | `oklch(0.600 0.024 90)` | 3.00:1 |
| `--ink-subtle` | `oklch(0.590 0.020 151)` | 3.80:1 | `oklch(0.501 0.020 151)` | 4.50:1 |
| `--danger` | `oklch(0.590 0.185 28)` | 4.20:1 | `oklch(0.525 0.185 28)` | 4.51:1 |
| `--orange-soft` | `oklch(0.932 0.046 57)` | fuera de gamut | `oklch(0.932 0.041 57)` | dentro |
| `--orange-hover` | `oklch(0.575 0.155 49)` | fuera de gamut | `oklch(0.575 0.154 49)` | dentro |

`--warning` (2.36:1) y `--success` (3.88:1) **no se añaden**. No los usa ninguna regla, ni del
documento ni del código, y el requisito vigente exige que un token sin llamadas no exista. Si
más adelante hacen falta, sus valores legibles son `oklch(0.494 0.080 148)` para el verde y uno
por derivar para el ámbar, que a croma 0.145 no alcanza 4.5:1 en ningún nivel dentro de gamut.

El tercer `--border-strong` del documento (2.59:1) es solo para el hover de un botón
secundario. Al ser el estado *más* marcado de un borde de control, no puede medir menos que
`--border-default`; se deriva por encima de 3:1 en la fase 3, cuando ese token entra.
