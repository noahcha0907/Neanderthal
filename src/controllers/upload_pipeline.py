"""
User document upload pipeline — PRD 2.6

Validates and chunks a user-uploaded document into CorpusChunks ready for
private session storage.  Uploaded chunks are tagged doc_type="user_upload"
and held in session state until the user consents at session end (PRD 2.5).
They never touch the shared graph or chunk store here.

Pipeline:
  validate extension → validate size → extract text → chunk → build CorpusChunks

Public API:
  UploadError                          — raised on any validation failure
  process_upload(filename, content)    → list[CorpusChunk]
"""
import logging
from pathlib import Path

from src.config.settings import ACCEPTED_EXTENSIONS, MAX_UPLOAD_BYTES
from src.helpers.chunker import chunk_document
from src.helpers.parsers import parse_bytes
from src.models.corpus import CorpusChunk

logger = logging.getLogger(__name__)

# Chunk strategy for user uploads — paragraph splitting, same as literary/philosophy
_UPLOAD_DOC_TYPE = "user_upload"
_UPLOAD_CHUNK_STRATEGY = "paragraph"


class UploadError(ValueError):
    """
    Raised when an uploaded file fails validation.

    Callers (FastAPI endpoint, tests) can catch this to return a 400 response
    without exposing internal state.
    """


def process_upload(filename: str, content: bytes) -> list[CorpusChunk]:
    """
    Validate, parse, and chunk a user-uploaded document.

    filename: original filename from the upload (used for extension detection
              and as source_path in chunk metadata — never executed as a path).
    content:  raw bytes of the uploaded file.

    Returns a list of CorpusChunks tagged as user_upload.
    Raises UploadError for any validation failure.
    Raises UploadError (wrapping parse errors) if the file cannot be decoded.
    """
    _validate_extension(filename)
    _validate_size(filename, content)

    try:
        text = parse_bytes(filename, content)
    except ValueError as exc:
        raise UploadError(str(exc)) from exc

    if not text.strip():
        raise UploadError(f"No text could be extracted from {filename!r}")

    raw_chunks = chunk_document(text, _UPLOAD_DOC_TYPE)
    if not raw_chunks:
        raise UploadError(
            f"No usable chunks produced from {filename!r} — "
            "file may be too short or consist entirely of whitespace"
        )

    title = Path(filename).stem
    chunks = [
        CorpusChunk(
            chunk_id=CorpusChunk.make_id(filename, index),
            source_path=filename,
            title=title,
            author="user_upload",
            doc_type=_UPLOAD_DOC_TYPE,
            year=None,
            chunk_index=index,
            text=chunk_text,
            chunk_strategy=_UPLOAD_CHUNK_STRATEGY,
        )
        for index, chunk_text in enumerate(raw_chunks)
    ]

    logger.info(
        "Upload processed: %s — %d chunk(s) produced",
        filename,
        len(chunks),
    )
    return chunks


# ── Validation helpers ────────────────────────────────────────────────────────

def _validate_extension(filename: str) -> None:
    """Raise UploadError if the file extension is not in ACCEPTED_EXTENSIONS."""
    suffix = Path(filename).suffix.lower()
    if suffix not in ACCEPTED_EXTENSIONS:
        raise UploadError(
            f"Unsupported file type {suffix!r}. "
            f"Accepted formats: {', '.join(sorted(ACCEPTED_EXTENSIONS))}"
        )


def _validate_size(filename: str, content: bytes) -> None:
    """Raise UploadError if the file exceeds MAX_UPLOAD_BYTES."""
    if len(content) > MAX_UPLOAD_BYTES:
        mb = MAX_UPLOAD_BYTES / (1024 * 1024)
        raise UploadError(
            f"{filename!r} is {len(content):,} bytes — "
            f"uploads must be under {mb:.0f} MB"
        )
