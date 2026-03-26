"""
Embedding storage and nearest-neighbour queries — PRD 1.2

EmbeddingStore manages the `embeddings` table in PostgreSQL, backed by a
pgvector HNSW index for sub-linear approximate nearest-neighbour search.

Public API:
  EmbeddingStore.embed_pending(encode_fn, batch_size) → int   (chunks embedded)
  EmbeddingStore.nearest_neighbors(query_text, k)     → list[tuple[CorpusChunk, float]]
  EmbeddingStore.count()                              → int
"""
import logging
from dataclasses import dataclass
from typing import Callable, Optional

import numpy as np
import psycopg2
import psycopg2.extras
from pgvector.psycopg2 import register_vector
from psycopg2.extensions import connection as PgConnection

from src.config.settings import DATABASE_URL, EMBEDDING_BATCH_SIZE
from src.models.corpus import CorpusChunk

logger = logging.getLogger(__name__)


@dataclass
class ScoredChunk:
    """A corpus chunk paired with its cosine similarity to a query."""
    chunk:      CorpusChunk
    similarity: float


class EmbeddingStore:
    """
    PostgreSQL-backed store for chunk embedding vectors.

    Uses pgvector's <=> cosine distance operator with an HNSW index for fast
    approximate nearest-neighbour retrieval at 6,000+ chunk scale.

    Connection is opened on construction. Use as a context manager or call
    close() explicitly when done.
    """

    def __init__(self, conn_or_url=DATABASE_URL):
        """
        Accepts either a connection URL string or an existing psycopg2 connection.

        Passing an existing connection lets callers share a transaction — useful
        in tests where both ChunkStore and EmbeddingStore must roll back together.
        """
        if isinstance(conn_or_url, str):
            self._conn: PgConnection = psycopg2.connect(conn_or_url)
            self._conn.autocommit = False
            self._owns_conn = True
        else:
            # Shared connection — caller manages lifecycle and commit/rollback
            self._conn = conn_or_url
            self._owns_conn = False
        # Register pgvector type so psycopg2 can send/receive vector values
        register_vector(self._conn)

    # ── Public API ──────────────────────────────────────────────────────────

    def embed_pending(
        self,
        encode_fn: Callable[[list[str]], np.ndarray] = None,
        batch_size: int = EMBEDDING_BATCH_SIZE,
    ) -> int:
        """
        Find every chunk that has no embedding yet, encode it, and store the vector.

        encode_fn must accept a list[str] and return an ndarray of shape
        (len(texts), EMBEDDING_DIM). Defaults to the production encoder.
        Returns the number of new embeddings inserted.
        """
        if encode_fn is None:
            from src.helpers.encoder import encode as encode_fn  # deferred import avoids loading the model unless needed

        pending = self._fetch_pending_chunks()
        if not pending:
            logger.info("No pending chunks to embed")
            return 0

        logger.info("Embedding %d chunks in batches of %d", len(pending), batch_size)
        total_inserted = 0

        for batch_start in range(0, len(pending), batch_size):
            batch = pending[batch_start : batch_start + batch_size]
            texts = [chunk.text for chunk in batch]
            vectors = encode_fn(texts)

            with self._conn.cursor() as cur:
                psycopg2.extras.execute_values(
                    cur,
                    """
                    INSERT INTO embeddings (chunk_id, vector)
                    VALUES %s
                    ON CONFLICT (chunk_id) DO NOTHING
                    """,
                    [(chunk.chunk_id, vector.tolist()) for chunk, vector in zip(batch, vectors)],
                )
                total_inserted += cur.rowcount

            logger.info(
                "  Batch %d–%d: %d inserted",
                batch_start + 1, batch_start + len(batch), cur.rowcount,
            )

        # Caller is responsible for committing — call commit() after embed_pending()
        # to flush to disk. This matches ChunkStore.add() and keeps test isolation intact
        # (test fixtures roll back the connection at teardown).
        logger.info("Embedding complete: %d new vectors staged", total_inserted)
        return total_inserted

    def nearest_neighbors(
        self,
        query_text: str,
        k: int = 10,
        encode_fn: Callable[[list[str]], np.ndarray] = None,
        exact: bool = False,
    ) -> list[ScoredChunk]:
        """
        Return the k chunks whose embeddings are closest to query_text.

        Similarity is cosine similarity (1 − cosine distance).
        Results are ordered by descending similarity.

        exact=False (default): uses the HNSW index — fast, approximate, requires
        embeddings to be committed before querying (standard production use).

        exact=True: forces a sequential scan — slower but works on uncommitted
        embeddings within the same transaction (useful in tests).
        """
        if encode_fn is None:
            from src.helpers.encoder import encode as encode_fn

        query_vector = encode_fn([query_text])[0]

        with self._conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            if exact:
                # Disable index scans so Postgres falls back to a sequential scan,
                # which respects the current transaction's uncommitted rows.
                cur.execute("SET LOCAL enable_indexscan = off")
                cur.execute("SET LOCAL enable_bitmapscan = off")

            cur.execute(
                """
                SELECT c.chunk_id, c.source_path, c.title, c.author,
                       c.doc_type, c.year, c.chunk_index, c.text, c.chunk_strategy,
                       1 - (e.vector <=> %s::vector) AS similarity
                FROM   embeddings e
                JOIN   chunks     c ON c.chunk_id = e.chunk_id
                ORDER  BY e.vector <=> %s::vector
                LIMIT  %s
                """,
                (query_vector.tolist(), query_vector.tolist(), k),
            )
            rows = cur.fetchall()

        return [
            ScoredChunk(
                chunk=CorpusChunk(
                    chunk_id=row["chunk_id"],
                    source_path=row["source_path"],
                    title=row["title"],
                    author=row["author"],
                    doc_type=row["doc_type"],
                    year=row["year"],
                    chunk_index=row["chunk_index"],
                    text=row["text"],
                    chunk_strategy=row["chunk_strategy"],
                ),
                similarity=float(row["similarity"]),
            )
            for row in rows
        ]

    def all_embeddings(self) -> list[tuple[str, np.ndarray]]:
        """
        Return every (chunk_id, vector) pair in the store.

        Used by build_graph to compute the full pairwise similarity matrix
        in one numpy batch pass rather than querying per-chunk.
        """
        with self._conn.cursor() as cur:
            cur.execute("SELECT chunk_id, vector FROM embeddings ORDER BY chunk_id")
            return [(row[0], np.array(row[1], dtype=np.float32)) for row in cur.fetchall()]

    def count(self) -> int:
        """Return the number of embeddings stored."""
        with self._conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM embeddings")
            return cur.fetchone()[0]

    def commit(self) -> None:
        """Commit the current transaction to disk."""
        self._conn.commit()

    def rollback(self) -> None:
        """Roll back the current transaction."""
        self._conn.rollback()

    def close(self) -> None:
        """Close the database connection (only if this store owns it)."""
        if self._owns_conn:
            self._conn.close()

    # ── Private helpers ─────────────────────────────────────────────────────

    def _fetch_pending_chunks(self) -> list[CorpusChunk]:
        """Return all chunks that do not yet have a corresponding embedding row."""
        with self._conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """
                SELECT c.chunk_id, c.source_path, c.title, c.author,
                       c.doc_type, c.year, c.chunk_index, c.text, c.chunk_strategy
                FROM   chunks c
                LEFT   JOIN embeddings e ON e.chunk_id = c.chunk_id
                WHERE  e.chunk_id IS NULL
                ORDER  BY c.title, c.chunk_index
                """
            )
            return [CorpusChunk(**dict(row)) for row in cur.fetchall()]

    # ── Context manager support ─────────────────────────────────────────────

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self._conn.rollback()
        else:
            self._conn.commit()
        self.close()

    def __len__(self) -> int:
        return self.count()
