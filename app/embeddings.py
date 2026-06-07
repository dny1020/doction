"""Local embedding model wrapper using sentence-transformers (no external API)."""

from __future__ import annotations

import logging

import numpy as np

logger = logging.getLogger(__name__)

MODEL_NAME = "all-MiniLM-L6-v2"


def load_model():
    """Load the embedding model. Returns None if unavailable (network/disk error)."""
    try:
        from sentence_transformers import SentenceTransformer
        return SentenceTransformer(MODEL_NAME)
    except Exception as exc:
        logger.warning(
            "Could not load embedding model %s: %s. Semantic search disabled.", MODEL_NAME, exc
        )
        return None


def embed(model, text: str) -> bytes:
    """Encode text to normalized float32 bytes. Uses first 3000 chars to bound latency."""
    vec = model.encode(text[:3000], convert_to_numpy=True, normalize_embeddings=True)
    return vec.astype(np.float32).tobytes()
