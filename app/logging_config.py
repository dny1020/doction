"""Logging level and destination, from environment variables.

Needed because uvicorn configures only its own `uvicorn.*` loggers and leaves the root
without a handler, so every `logger.info(...)` from `app` would be dropped silently.
Called once when `app.main` is imported, before any logger runs.
"""

import logging
import logging.handlers
import os
from pathlib import Path

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
LOG_DIR = Path(os.environ.get("LOG_DIR", "/logs"))
LOG_FILE = LOG_DIR / "doction.log"
LOG_MAX_BYTES = 10 * 1024 * 1024
LOG_BACKUP_COUNT = 5  # ~50 MB in total before the oldest is dropped

_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"


def configure_logging() -> None:
    """Root logger to stdout plus a rotated file in LOG_DIR. Idempotent."""
    root = logging.getLogger()
    if root.handlers:
        return  # already configured: uvicorn reload, repeated import in tests

    root.setLevel(LOG_LEVEL)
    formatter = logging.Formatter(_FORMAT)

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root.addHandler(console)

    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            LOG_FILE, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
    except OSError as exc:
        logging.getLogger(__name__).warning("could not open the log file %s: %s", LOG_FILE, exc)
