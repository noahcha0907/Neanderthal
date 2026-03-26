"""
Unit tests for the corpus ingestion pipeline — PRD 1.1
"""
import pytest
from pathlib import Path

from src.controllers.ingest import (
    DocumentMetadata,
    ingest_document,
    ingest_directory,
)

# prose_file, store, metadata fixtures come from tests/conftest.py


# ── Happy path ─────────────────────────────────────────────────────────────

def test_ingest_document_succeeds(prose_file, store, metadata):
    result = ingest_document(prose_file, metadata, store)
    assert result.success is True
    assert result.chunks_added > 0
    assert result.error is None


def test_ingest_document_chunks_are_stored(prose_file, store, metadata):
    ingest_document(prose_file, metadata, store)
    assert len(store) > 0


def test_ingest_stores_correct_metadata(prose_file, store, metadata):
    ingest_document(prose_file, metadata, store)
    # Filter to chunks from this specific file only
    chunks = [c for c in store.all_chunks() if c.source_path == str(prose_file)]
    assert len(chunks) > 0
    assert all(c.title == "Test Work" for c in chunks)
    assert all(c.author == "Test Author" for c in chunks)
    assert all(c.doc_type == "literary" for c in chunks)
    assert all(c.year == 2024 for c in chunks)


# ── Idempotency ────────────────────────────────────────────────────────────

def test_ingest_document_is_idempotent(prose_file, store, metadata):
    r1 = ingest_document(prose_file, metadata, store)
    r2 = ingest_document(prose_file, metadata, store)
    assert r1.chunks_added > 0
    assert r2.chunks_added == 0
    assert r2.chunks_skipped == r1.chunks_added


def test_total_chunks_unchanged_after_duplicate_ingest(prose_file, store, metadata):
    ingest_document(prose_file, metadata, store)
    count_after_first = len(store)
    ingest_document(prose_file, metadata, store)
    assert len(store) == count_after_first


# ── Failure cases ──────────────────────────────────────────────────────────

def test_ingest_missing_file_fails(tmp_path, store, metadata):
    result = ingest_document(tmp_path / "ghost.txt", metadata, store)
    assert result.success is False
    assert "not found" in result.error.lower()


def test_ingest_unsupported_format_fails(tmp_path, store, metadata):
    f = tmp_path / "bad.docx"
    f.write_bytes(b"fake content")
    result = ingest_document(f, metadata, store)
    assert result.success is False
    assert "unsupported" in result.error.lower()


def test_ingest_unknown_doc_type_fails(prose_file, store):
    bad = DocumentMetadata("Title", "Author", "not_a_real_type")
    result = ingest_document(prose_file, bad, store)
    assert result.success is False
    assert "unknown doc_type" in result.error.lower()


def test_ingest_empty_file_fails(tmp_path, store, metadata):
    f = tmp_path / "empty.txt"
    f.write_text("", encoding="utf-8")
    result = ingest_document(f, metadata, store)
    assert result.success is False


# ── Directory ingestion ────────────────────────────────────────────────────

def test_ingest_directory_from_manifest(tmp_path, store, prose_file):
    manifest = [
        {"filename": "prose.txt", "title": "Doc", "author": "Auth",
         "doc_type": "literary", "year": 2020}
    ]
    results = ingest_directory(tmp_path, manifest, store)
    assert len(results) == 1
    assert results[0].success is True


def test_ingest_directory_handles_missing_file_gracefully(tmp_path, store):
    manifest = [
        {"filename": "missing.txt", "title": "T", "author": "A", "doc_type": "literary"}
    ]
    results = ingest_directory(tmp_path, manifest, store)
    assert results[0].success is False


def test_ingest_directory_multiple_docs(tmp_path, store):
    base_content = (
        "The weight of history presses down upon each generation in turn. "
        "We inherit not only the achievements of those who came before.\n\n"
        "What we call progress is often nothing more than the reordering of old "
        "mistakes into new configurations that feel, for a brief time, like solutions.\n\n"
        "A third idea enters, distinct and self-contained, refusing to be absorbed "
        "into the narrative logic of what preceded it. It asserts its own weight."
    )
    for i in range(3):
        f = tmp_path / f"doc{i}.txt"
        f.write_text(base_content + f"\n\nDocument number {i}.", encoding="utf-8")
    manifest = [
        {"filename": f"doc{i}.txt", "title": f"Doc {i}", "author": "A",
         "doc_type": "literary"}
        for i in range(3)
    ]
    results = ingest_directory(tmp_path, manifest, store)
    assert all(r.success for r in results)
    assert len(store) > 3
