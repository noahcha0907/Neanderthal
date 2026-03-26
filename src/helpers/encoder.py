"""
Text encoder helper — PRD 1.2

Wraps sentence-transformers to produce 384-dimensional dense vectors from text.
The model is loaded once on first call and reused for the lifetime of the process.

Public API:
  encode(texts)  → np.ndarray  shape (len(texts), 384)
"""
import logging
from typing import Union

import numpy as np
from sentence_transformers import SentenceTransformer

from src.config.settings import EMBEDDING_MODEL

logger = logging.getLogger(__name__)

_model: Union[SentenceTransformer, None] = None


def _get_model() -> SentenceTransformer:
    """Load the embedding model on first access, then cache it."""
    global _model
    if _model is None:
        logger.info("Loading embedding model '%s'", EMBEDDING_MODEL)
        _model = SentenceTransformer(EMBEDDING_MODEL)
    return _model


def encode(texts: list[str]) -> np.ndarray:
    """
    Encode a list of strings into embedding vectors.

    Returns a float32 array of shape (len(texts), EMBEDDING_DIM).
    Normalises to unit length so cosine similarity reduces to dot product.
    """
    model = _get_model()
    vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return np.array(vectors, dtype=np.float32)
