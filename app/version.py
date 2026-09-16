"""Project version and licence, read from pyproject.toml.

pyproject.toml travels inside the Docker image, so both can be read at runtime rather
than duplicated anywhere else.
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
        logger.warning("could not read '%s' from %s", key, _PYPROJECT)
        return fallback


VERSION = _read("version", "0.0.0")

# The instance reports its licence because the AGPL obligation is its own, not the
# repository's. pyproject.toml is the only hand-written declaration, and
# scripts/check_license.py compares every other one against it.
LICENSE_ID = _read("license", "AGPL-3.0-only")
