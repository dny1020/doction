"""Colores de identidad del avatar.

Son ocho porque tienen que distinguirse entre si, no porque sean marca: el
acento del producto es uno solo. Lo que si comparten con el resto del lenguaje
visual es el suelo — todos se miden contra el papel calido — y una unica tinta
encima (`--fg-on-identity`), que no gira con el tema porque el fondo tampoco.

La paleta anterior estaba pensada para otro lienzo y la letra no se leia: siete
de los ocho colores quedaban por debajo de 4.5:1 en claro y cuatro en oscuro.
Estos ocho conservan el matiz y bajan la luminosidad hasta pasar el umbral.
"""

AVATAR_COLORS = [
    "#B8523B",
    "#3B73B8",
    "#347F50",
    "#895AC2",
    "#926A2F",
    "#2D7B8C",
    "#C04669",
    "#5E7A37",
]

# El color elegido se guarda como texto en `users.avatar_color`, asi que quien
# ya habia escogido uno seguiria viendo el ilegible para siempre. El mapa lo
# traduce al leer: misma posicion, mismo matiz, contraste que si cumple.
_LEGACY = {
    "#c0604a": "#B8523B",
    "#4a7fc0": "#3B73B8",
    "#4aab6e": "#347F50",
    "#8b5fc0": "#895AC2",
    "#c0914a": "#926A2F",
    "#4aabc0": "#2D7B8C",
    "#c05473": "#C04669",
    "#7a9c4a": "#5E7A37",
}


def normalize_color(color: str | None) -> str | None:
    """Traduce un color heredado al actual; descarta cualquier otro valor."""
    if not color:
        return None
    current = _LEGACY.get(color.lower(), color)
    return current if current in AVATAR_COLORS else None
