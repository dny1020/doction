"""Versión única del proyecto, leída de pyproject.toml.

Antes la versión vivía en dos sitios (pyproject.toml y SERVER_INFO en mcp.py) y ya
había driftado una vez. pyproject.toml viaja dentro de la imagen Docker (el COPY del
stage base), así que se puede leer en runtime con tomllib (stdlib) sin duplicarla.
"""

from __future__ import annotations

import logging
import tomllib
from pathlib import Path

logger = logging.getLogger(__name__)

_PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"


def _read_version() -> str:
    try:
        with _PYPROJECT.open("rb") as f:
            return tomllib.load(f)["project"]["version"]
    except (OSError, KeyError, tomllib.TOMLDecodeError):
        logger.warning("no se pudo leer la versión desde %s", _PYPROJECT)
        return "0.0.0"


VERSION = _read_version()
