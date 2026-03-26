"""
Unit tests for the embedding storage layer — PRD 1.2

Uses a deterministic fake encoder so tests never load sentence-transformers.
All DB writes (chunks + embeddings) are rolled back by the shared connection
in conftest.py — the embed_store fixture shares store._conn so both operate
in the same transaction.
"""
import numpy as np
import pytest

from src.models.embeddings import EmbeddingStore, ScoredChunk
from src.controllers.ingest import ingest_document


# ── Helpers ────────────────────────────────────────────────────────────────

EMBEDDING_DIM = 384


def fake_encode(texts: list[str]) -> np.ndarray:
    """
    Deterministic fake encoder.
    Produces normalised random unit vectors seeded at 42.
    Output shape is (len(texts), EMBEDDING_DIM).
    """
    rng = np.random.default_rng(seed=42)
    vecs = rng.random((len(texts), EMBEDDING_DIM)).astype(np.float32)
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    return vecs / norms


@pytest.fixture
def embed_store(store):
    """
    An EmbeddingStore that shares the ChunkStore's psycopg2 connection.

    Same connection = same transaction. The store fixture's rollback at teardown
    undoes all chunk inserts AND embedding inserts together, leaving the
    production DB completely untouched.
    """
    return EmbeddingStore(store._conn)


# ── embed_pending ──────────────────────────────────────────────────────────

def test_embed_pending_inserts_vectors(prose_file, store, embed_store, metadata):
    """After ingesting a document, embed_pending should store one vector per chunk."""
    ingest_document(prose_file, metadata, store)
    inserted = embed_store.embed_pending(encode_fn=fake_encode)
    assert inserted > 0


def test_embed_pending_is_idempotent(prose_file, store, embed_store, metadata):
    """Calling embed_pending twice returns 0 on the second call."""
    ingest_document(prose_file, metadata, store)
    first  = embed_store.embed_pending(encode_fn=fake_encode)
    second = embed_store.embed_pending(encode_fn=fake_encode)
    assert first > 0
    assert second == 0


def test_embed_pending_skips_already_embedded(prose_file, store, embed_store, metadata):
    """Chunks already in embeddings table are not re-processed."""
    ingest_document(prose_file, metadata, store)
    embed_store.embed_pending(encode_fn=fake_encode)
    count_after_first = len(embed_store)
    embed_store.embed_pending(encode_fn=fake_encode)
    assert len(embed_store) == count_after_first


def test_encode_fn_called_with_correct_texts(prose_file, store, embed_store, metadata):
    """embed_pending passes chunk text strings (non-empty) to the encode function."""
    ingest_document(prose_file, metadata, store)

    received: list[str] = []

    def capturing_encode(texts):
        received.extend(texts)
        return fake_encode(texts)

    embed_store.embed_pending(encode_fn=capturing_encode)

    assert len(received) > 0
    assert all(isinstance(t, str) for t in received)
    assert all(len(t) > 0 for t in received)


# ── nearest_neighbors ──────────────────────────────────────────────────────

def test_nearest_neighbors_returns_k_results(prose_file, store, embed_store, metadata):
    """nearest_neighbors returns exactly k results when enough embeddings exist."""
    ingest_document(prose_file, metadata, store)
    embed_store.embed_pending(encode_fn=fake_encode)

    results = embed_store.nearest_neighbors("suffering and history", k=2, encode_fn=fake_encode, exact=True)
    assert len(results) == 2


def test_nearest_neighbors_returns_scored_chunks(prose_file, store, embed_store, metadata):
    """Results are ScoredChunk instances with valid similarity scores and non-empty text."""
    ingest_document(prose_file, metadata, store)
    embed_store.embed_pending(encode_fn=fake_encode)

    results = embed_store.nearest_neighbors("weight of history", k=1, encode_fn=fake_encode, exact=True)
    assert len(results) == 1
    sc = results[0]
    assert isinstance(sc, ScoredChunk)
    assert 0.0 <= sc.similarity <= 1.01   # cosine similarity is in [0, 1] for unit vecs
    assert sc.chunk.text != ""


def test_nearest_neighbors_k_larger_than_corpus(prose_file, store, embed_store, metadata):
    """k larger than stored embeddings does not raise — returns however many exist."""
    ingest_document(prose_file, metadata, store)
    embed_store.embed_pending(encode_fn=fake_encode)

    # HNSW caps returned rows at ef_search (default 40); verify no exception
    # and at least one result is returned.
    results = embed_store.nearest_neighbors("query", k=99999, encode_fn=fake_encode, exact=True)
    assert len(results) >= 1


# ── count / __len__ ────────────────────────────────────────────────────────

def test_count_increases_after_embed(prose_file, store, embed_store, metadata):
    ingest_document(prose_file, metadata, store)
    before = len(embed_store)
    embed_store.embed_pending(encode_fn=fake_encode)
    after  = len(embed_store)
    assert after > before
