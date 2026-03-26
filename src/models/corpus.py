"""
Data models for the corpus ingestion pipeline (PRD 1.1).

CorpusChunk  — one semantically meaningful unit of text from a source document.
ChunkStore   — PostgreSQL-backed, concurrent-safe storage for all ingested chunks.
               Replaces the earlier JSON implementation for production correctness.
"""
import hashlib
from dataclasses import dataclass
from typing import Optional

import psycopg2
import psycopg2.extras
from psycopg2.extensions import connection as PgConnection

from src.config.settings import DATABASE_URL


@dataclass
class CorpusChunk:
    """
    A single semantically meaningful unit of text from a source document.

    chunk_id is a SHA-256 hash of (source_path + chunk_index), making it
    stable and reproducible — re-ingesting the same file at the same path
    produces identical IDs, enabling idempotent storage.
    """
    chunk_id:       str
    source_path:    str
    title:          str
    author:         str
    doc_type:       str
    year:           Optional[int]
    chunk_index:    int
    text:           str
    chunk_strategy: str

    @staticmethod
    def make_id(source_path: str, chunk_index: int) -> str:
        """
        Produce a stable, reproducible chunk ID.
        Same source_path + chunk_index always yields the same hash.
        """
        raw = f"{source_path}::{chunk_index}"
        return hashlib.sha256(raw.encode()).hexdigest()


class ChunkStore:
    """
    PostgreSQL-backed store for corpus chunks.

    Idempotency: INSERT ... ON CONFLICT DO NOTHING ensures that re-ingesting
    the same file never creates duplicate rows. Each call to add() is
    atomic at the database level — safe for concurrent writers.

    Connection is opened on construction and closed explicitly via close()
    or by using the store as a context manager.
    """

    def __init__(self, db_url: str = DATABASE_URL):
        self._conn: PgConnection = psycopg2.connect(str(db_url))
        self._conn.autocommit = False

    # ── Public API ──────────────────────────────────────────────────────────

    def add(self, chunk: CorpusChunk) -> bool:
        """
        Insert a chunk. Returns True if inserted, False if already present.
        Does not commit — call commit() after a batch for efficiency.
        """
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO chunks
                    (chunk_id, source_path, title, author, doc_type,
                     year, chunk_index, text, chunk_strategy)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (chunk_id) DO NOTHING
                """,
                (
                    chunk.chunk_id,
                    chunk.source_path,
                    chunk.title,
                    chunk.author,
                    chunk.doc_type,
                    chunk.year,
                    chunk.chunk_index,
                    chunk.text,
                    chunk.chunk_strategy,
                ),
            )
            return cur.rowcount == 1

    def commit(self) -> None:
        """Commit the current transaction to disk."""
        self._conn.commit()

    def rollback(self) -> None:
        """Roll back the current transaction."""
        self._conn.rollback()

    def all_chunks(self) -> list[CorpusChunk]:
        """Return every chunk in the store."""
        with self._conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("""
                SELECT chunk_id, source_path, title, author, doc_type,
                       year, chunk_index, text, chunk_strategy
                FROM chunks
                ORDER BY title, chunk_index
            """)
            return [CorpusChunk(**dict(row)) for row in cur.fetchall()]

    def count(self) -> int:
        """Return total number of chunks stored."""
        with self._conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM chunks")
            return cur.fetchone()[0]

    def contains(self, chunk_id: str) -> bool:
        """Return True if a chunk with this ID already exists."""
        with self._conn.cursor() as cur:
            cur.execute("SELECT 1 FROM chunks WHERE chunk_id = %s", (chunk_id,))
            return cur.fetchone() is not None

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()

    # ── Context manager support ─────────────────────────────────────────────

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.rollback()
        else:
            self.commit()
        self.close()

    def __len__(self) -> int:
        return self.count()

    def __contains__(self, chunk_id: str) -> bool:
        return self.contains(chunk_id)


def get_connection() -> PgConnection:
    """
    Return a raw psycopg2 connection for operations that need direct
    database access (e.g. the embedding layer in PRD 1.2).
    """
    return psycopg2.connect(str(DATABASE_URL))
