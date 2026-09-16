"""Local OCR of uploaded images, opt-in via OCR_UPLOADS=1.

Shells out to the `tesseract` binary and stores the text in `upload_texts` so
screenshots and diagrams turn up in search. Languages come from OCR_LANGS. A failed
OCR never breaks the upload.
"""

import logging
import os
import shutil
import subprocess
from pathlib import Path

from app import db

logger = logging.getLogger(__name__)

OCR_TIMEOUT_S = 120  # a normal screenshot takes 1-3s even on the Pi; this is the ceiling


def ocr_enabled() -> bool:
    return os.environ.get("OCR_UPLOADS", "").lower() in {"1", "true", "yes"}


def _langs() -> str:
    return os.environ.get("OCR_LANGS", "eng+spa")


def extract_text(path: Path) -> str | None:
    """OCR text from an image, or None if tesseract is missing or fails."""
    if shutil.which("tesseract") is None:
        logger.warning("OCR_UPLOADS is on but the `tesseract` binary is not installed")
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
        logger.warning("ocr: timed out (%ss) on %s", OCR_TIMEOUT_S, path.name)
        return None
    except OSError:
        logger.exception("ocr: could not run tesseract for %s", path.name)
        return None
    if proc.returncode != 0:
        logger.warning("ocr: tesseract failed for %s: %s", path.name, proc.stderr.strip()[:300])
        return None
    return proc.stdout


def index_upload(name: str, user_id: int, workspace_id: int, path: Path) -> bool:
    """OCR an upload and index it; True when searchable text was stored."""
    text = (extract_text(path) or "").strip()
    if not text:
        return False
    db.store_upload_text(name, user_id, workspace_id, text)
    logger.info("ocr: indexed %s (%d characters)", name, len(text))
    return True
