"""Configuración de logging: nivel y destino por variables de entorno.

Sin esto, uvicorn solo configura sus propios loggers (``uvicorn``, ``uvicorn.error``,
``uvicorn.access``) y deja el root logger sin handler, así que cualquier
``logger.info(...)`` de los módulos de ``app`` se pierde en silencio (el "handler de
último recurso" de Python solo imprime WARNING o superior). ``configure_logging()``
se llama una vez al importar ``app.main``, antes de que corra cualquier logger.
"""

from __future__ import annotations

import logging
import logging.handlers
import os
from pathlib import Path

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
LOG_DIR = Path(os.environ.get("LOG_DIR", "/logs"))
LOG_FILE = LOG_DIR / "doction.log"
LOG_MAX_BYTES = 10 * 1024 * 1024  # 10 MB por archivo
LOG_BACKUP_COUNT = 5  # hasta ~50 MB totales antes de descartar el más viejo

_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"


def configure_logging() -> None:
    """Root logger -> consola (stdout) + archivo rotado en LOG_DIR. Idempotente."""
    root = logging.getLogger()
    if root.handlers:
        return  # ya configurado (reload de uvicorn, import repetido en tests, etc.)

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
        logging.getLogger(__name__).warning(
            "no se pudo abrir el archivo de log %s: %s", LOG_FILE, exc
        )
