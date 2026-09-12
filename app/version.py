"""Versión y licencia del proyecto, leídas de pyproject.toml.

Antes la versión vivía en dos sitios (pyproject.toml y SERVER_INFO en mcp.py) y ya
había driftado una vez. pyproject.toml viaja dentro de la imagen Docker (el COPY del
stage base), así que se puede leer en runtime con tomllib (stdlib) sin duplicarla.
"""

import logging
import tomllib
from pathlib import Path

logger = logging.getLogger(__name__)

_PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"


def _read(key: str, fallback: str) -> str:
    try:
        with _PYPROJECT.open("rb") as f:
            return tomllib.load(f)["project"][key]
    except (OSError, KeyError, tomllib.TOMLDecodeError):
        logger.warning("no se pudo leer '%s' desde %s", key, _PYPROJECT)
        return fallback


VERSION = _read("version", "0.0.0")

# La instancia informa bajo qué licencia corre porque la obligación de la AGPL es suya, no
# del repositorio. Sale del mismo sitio que la versión: pyproject.toml es la única
# declaración escrita a mano, y scripts/check_license.py compara el resto contra ella.
LICENSE_ID = _read("license", "AGPL-3.0-only")
