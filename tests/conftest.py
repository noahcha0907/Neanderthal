"""
Shared pytest fixtures for all test tiers.

Database isolation strategy: each test that touches the DB gets a ChunkStore
whose transaction is rolled back at teardown. No test data ever commits to disk.
This means tests can run against the real local database without polluting it.
"""
import pytest
import psycopg2
from src.config.settings import DATABASE_URL
from src.models.corpus import ChunkStore


@pytest.fixture
def store():
    """
    A ChunkStore whose writes are rolled back after each test.
    Tests get a real DB connection but leave zero persistent state.
    """
    s = ChunkStore(DATABASE_URL)
    yield s
    s.rollback()
    s.close()


@pytest.fixture
def prose_file(tmp_path):
    """A realistic prose text file for ingestion tests."""
    content = (
        "The weight of history presses down upon each generation in turn. "
        "We inherit not only the achievements of those who came before, but also "
        "their failures — the long chain of cause and effect that stretches back "
        "through centuries of human striving and suffering.\n\n"
        "What we call progress is often nothing more than the reordering of old "
        "mistakes into new configurations that feel, for a brief time, like solutions. "
        "The mind finds comfort in novelty even when the underlying structure endures.\n\n"
        "A third idea enters, distinct and self-contained, refusing to be absorbed "
        "into the narrative logic of what preceded it. It asserts its own weight."
    )
    f = tmp_path / "prose.txt"
    f.write_text(content, encoding="utf-8")
    return f


@pytest.fixture
def metadata():
    """Standard DocumentMetadata for tests that need it."""
    from src.controllers.ingest import DocumentMetadata
    return DocumentMetadata(
        title="Test Work",
        author="Test Author",
        doc_type="literary",
        year=2024,
    )
