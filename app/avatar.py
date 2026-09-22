"""Avatar identity colours.

Eight because they have to be told apart, not because they are brand: the product has
one accent. They share the rest of the visual language's ground — all measured against
the warm paper — and one ink on top (`--fg-on-identity`), which does not follow the
theme because the background does not either. Each passes 4.5:1 in both themes.
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

# The chosen colour is stored as text in `users.avatar_color`, so anyone who picked one
# from the old palette would keep the unreadable value forever. Translated on read:
# same position, same hue, contrast that passes.
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
    """Translate a legacy colour to its current value; discard anything else."""
    if not color:
        return None
    current = _LEGACY.get(color.lower(), color)
    return current if current in AVATAR_COLORS else None
