"""
Embedding Pipeline Controller — PRD 1.2

Orchestrates the full embedding flow:
  fetch unembedded chunks → encode → store vectors

Public API:
  run_embedding_pipeline(store)  → int   (number of new embeddings)

CLI: python -m src.controllers.embed
"""
import logging
import sys

from src.helpers.encoder import encode
from src.models.embeddings import EmbeddingStore

logger = logging.getLogger(__name__)


def run_embedding_pipeline(store: EmbeddingStore = None) -> int:
    """
    Encode all chunks that do not yet have an embedding and persist the vectors.

    Returns the number of new embeddings inserted.
    Safe to call repeatedly — already-embedded chunks are skipped.
    """
    store = store or EmbeddingStore()
    pending_before = len(store._fetch_pending_chunks())

    if pending_before == 0:
        logger.info("All chunks already embedded — nothing to do")
        return 0

    logger.info("Starting embedding pipeline: %d chunks to embed", pending_before)
    inserted = store.embed_pending(encode_fn=encode)
    store.commit()
    logger.info("Pipeline complete: %d embeddings added", inserted)
    return inserted


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s — %(message)s",
        stream=sys.stdout,
    )
    total = run_embedding_pipeline()
    print(f"\nDone — {total} new embeddings stored.")
