"""
Justification trace storage — PRD 1.7

TraceStore persists and retrieves justification traces from the `justifications`
table in PostgreSQL.  Uses the same shared-connection pattern as EmbeddingStore
so callers can share a transaction with ChunkStore or roll back in tests.

Public API:
  TraceStore.save(trace)        → None   (stages the INSERT; caller commits)
  TraceStore.get(artwork_id)    → str | None
  TraceStore.commit()           → None
  TraceStore.rollback()         → None
  TraceStore.close()            → None
"""
import logging

import psycopg2
from psycopg2.extensions import connection as PgConnection

from src.config.settings import DATABASE_URL
from src.models.trace import JustificationTrace

logger = logging.getLogger(__name__)


class TraceStore:
    """
    PostgreSQL-backed store for justification traces.

    Accepts either a connection URL string or an existing psycopg2 connection.
    Passing an existing connection lets callers share a transaction — useful in
    tests where all writes must roll back together at teardown.
    """

    def __init__(self, conn_or_url=DATABASE_URL):
        if isinstance(conn_or_url, str):
            self._conn: PgConnection = psycopg2.connect(conn_or_url)
            self._conn.autocommit = False
            self._owns_conn = True
        else:
            self._conn = conn_or_url
            self._owns_conn = False

    # ── Public API ────────────────────────────────────────────────────────────

    def save(self, trace: JustificationTrace) -> None:
        """
        Upsert the justification trace for trace.artwork_id.

        Does not commit — call commit() after saving to flush to disk.
        Re-saving an existing artwork_id overwrites the previous trace.
        """
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO justifications (artwork_id, trace_text)
                VALUES (%s, %s)
                ON CONFLICT (artwork_id) DO UPDATE
                    SET trace_text = EXCLUDED.trace_text,
                        created_at = NOW()
                """,
                (trace.artwork_id, trace.to_text()),
            )
        logger.debug("Trace staged for artwork_id=%s", trace.artwork_id)

    def get(self, artwork_id: str) -> str | None:
        """
        Return the plain-text trace for artwork_id, or None if not found.
        """
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT trace_text FROM justifications WHERE artwork_id = %s",
                (artwork_id,),
            )
            row = cur.fetchone()
        return row[0] if row else None

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

    # ── Context manager support ───────────────────────────────────────────────

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self._conn.rollback()
        else:
            self._conn.commit()
        self.close()
