"""
Corpus Ingestion Pipeline — PRD 1.1

Orchestrates the full ingestion flow for a humanities document:
  parse → chunk → tag metadata → store (idempotent)

Public API:
  ingest_document(path, metadata, store)  → IngestionResult
  ingest_directory(directory, manifest, store) → list[IngestionResult]
"""
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from src.config.settings import (
    ACCEPTED_EXTENSIONS,
    CHUNK_STRATEGIES,
    DOCUMENT_TYPES,
    HUMANITIES_DIR,
    MANIFEST_FILENAME,
)
from src.helpers.chunker import chunk_document
from src.helpers.parsers import parse_document
from src.models.corpus import ChunkStore, CorpusChunk

logger = logging.getLogger(__name__)


@dataclass
class DocumentMetadata:
    """Caller-supplied metadata for a document being ingested."""
    title:    str
    author:   str
    doc_type: str
    year:     Optional[int] = None


@dataclass
class IngestionResult:
    """Outcome of ingesting one document."""
    path:           str
    success:        bool
    chunks_added:   int
    chunks_skipped: int   # Duplicates already present in the store
    error:          Optional[str] = None


def ingest_document(
    path: Path,
    metadata: DocumentMetadata,
    store: ChunkStore,
) -> IngestionResult:
    """
    Parse, chunk, and store a single document.

    Returns an IngestionResult describing the outcome.
    Never raises — all errors are captured in result.error.
    The store is not saved to disk here; call store.save() after a batch.
    """
    path = Path(path)

    if not path.exists():
        return IngestionResult(str(path), False, 0, 0, "File not found")

    if path.suffix.lower() not in ACCEPTED_EXTENSIONS:
        return IngestionResult(
            str(path), False, 0, 0, f"Unsupported format: {path.suffix}"
        )

    if metadata.doc_type not in DOCUMENT_TYPES:
        return IngestionResult(
            str(path), False, 0, 0, f"Unknown doc_type: '{metadata.doc_type}'"
        )

    try:
        raw_text = parse_document(path)
    except Exception as exc:
        logger.warning("Parse error for %s: %s", path, exc)
        return IngestionResult(str(path), False, 0, 0, f"Parse error: {exc}")

    if not raw_text.strip():
        logger.warning("No text extracted from %s", path)
        return IngestionResult(str(path), False, 0, 0, "No text extracted")

    chunks = chunk_document(raw_text, metadata.doc_type)
    if not chunks:
        return IngestionResult(
            str(path), False, 0, 0, "No chunks produced after filtering"
        )

    added = 0
    skipped = 0
    strategy = CHUNK_STRATEGIES.get(metadata.doc_type, "paragraph")

    for index, text in enumerate(chunks):
        chunk = CorpusChunk(
            chunk_id=CorpusChunk.make_id(str(path), index),
            source_path=str(path),
            title=metadata.title,
            author=metadata.author,
            doc_type=metadata.doc_type,
            year=metadata.year,
            chunk_index=index,
            text=text,
            chunk_strategy=strategy,
        )
        if store.add(chunk):
            added += 1
        else:
            skipped += 1

    logger.info(
        "Ingested '%s': %d chunks added, %d skipped (duplicates)",
        path.name, added, skipped,
    )
    return IngestionResult(str(path), True, added, skipped)


def ingest_directory(
    directory: Path,
    manifest: list[dict],
    store: ChunkStore,
) -> list[IngestionResult]:
    """
    Ingest all documents described in a manifest from a directory.

    Manifest format — list of dicts:
      [
        {
          "filename": "karamazov.pdf",
          "title": "The Brothers Karamazov",
          "author": "Fyodor Dostoevsky",
          "doc_type": "literary",
          "year": 1880
        },
        ...
      ]

    Saves the store to disk after all documents are processed.
    """
    directory = Path(directory)
    results: list[IngestionResult] = []

    for entry in manifest:
        filename = entry.get("filename", "")
        path = directory / filename
        metadata = DocumentMetadata(
            title=entry.get("title", filename),
            author=entry.get("author", "Unknown"),
            doc_type=entry.get("doc_type", "literary"),
            year=entry.get("year"),
        )
        result = ingest_document(path, metadata, store)
        results.append(result)

    store.commit()

    total_added   = sum(r.chunks_added for r in results)
    total_skipped = sum(r.chunks_skipped for r in results)
    failed        = sum(1 for r in results if not r.success)
    logger.info(
        "Directory ingest complete: %d docs, %d chunks added, "
        "%d skipped, %d failed",
        len(results), total_added, total_skipped, failed,
    )
    return results


def ingest_from_manifest_file(
    manifest_path: Optional[Path] = None,
    store: Optional[ChunkStore] = None,
) -> list[IngestionResult]:
    """
    Convenience entry point: read manifest.json from the humanities data
    directory and ingest all listed documents.

    Uses HUMANITIES_DIR and CHUNK_STORE_PATH from settings by default.
    Intended for CLI use: `python -m src.controllers.ingest`
    """
    manifest_path = manifest_path or (HUMANITIES_DIR / MANIFEST_FILENAME)
    store = store or ChunkStore()

    if not manifest_path.exists():
        logger.error("Manifest not found: %s", manifest_path)
        return []

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    return ingest_directory(HUMANITIES_DIR, manifest, store)


if __name__ == "__main__":
    import sys
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s — %(message)s",
        stream=sys.stdout,
    )
    results = ingest_from_manifest_file()
    for r in results:
        status = "OK" if r.success else "FAIL"
        print(f"[{status}] {Path(r.path).name} — "
              f"+{r.chunks_added} chunks, {r.chunks_skipped} skipped"
              + (f" | {r.error}" if r.error else ""))
