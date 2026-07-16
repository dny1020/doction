"""OCR local de imágenes subidas (opt-in vía OCR_UPLOADS=1).

Llama al binario `tesseract` con subprocess — cero dependencias Python, filosofía
Unix — y guarda el texto en `upload_texts` para que capturas y diagramas subidos
aparezcan en la búsqueda. Idiomas vía OCR_LANGS (por defecto `eng+spa`, los
paquetes que instala el Dockerfile). Un OCR fallido nunca rompe la subida: el
worker registra el error y sigue.
"""

import logging
import os
import shutil
import subprocess
from pathlib import Path

from app import db

logger = logging.getLogger(__name__)

OCR_TIMEOUT_S = 120  # una captura normal tarda ~1-3 s incluso en el Pi; esto es el tope


def ocr_enabled() -> bool:
    """True si el OCR de uploads está activado por entorno."""
    return os.environ.get("OCR_UPLOADS", "").lower() in {"1", "true", "yes"}


def _langs() -> str:
    return os.environ.get("OCR_LANGS", "eng+spa")


def extract_text(path: Path) -> str | None:
    """Texto OCR de una imagen, o None si tesseract no está o falla."""
    if shutil.which("tesseract") is None:
        logger.warning("OCR_UPLOADS activo pero el binario `tesseract` no está instalado")
        return None
    try:
        proc = subprocess.run(
            ["tesseract", str(path), "stdout", "-l", _langs()],
            capture_output=True,
            text=True,
            timeout=OCR_TIMEOUT_S,
            check=False,
        )
    except subprocess.TimeoutExpired:
        logger.warning("ocr: timeout (%ss) procesando %s", OCR_TIMEOUT_S, path.name)
        return None
    except OSError:
        logger.exception("ocr: no se pudo ejecutar tesseract para %s", path.name)
        return None
    if proc.returncode != 0:
        logger.warning("ocr: tesseract falló para %s: %s", path.name, proc.stderr.strip()[:300])
        return None
    return proc.stdout


def index_upload(name: str, user_id: int, workspace_id: int, path: Path) -> bool:
    """OCR de un upload + indexado en `upload_texts`. True si quedó texto buscable."""
    text = (extract_text(path) or "").strip()
    if not text:
        return False
    db.store_upload_text(name, user_id, workspace_id, text)
    logger.info("ocr: indexado %s (%d caracteres)", name, len(text))
    return True
