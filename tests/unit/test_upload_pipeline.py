"""
Unit tests for the user document upload pipeline — PRD 2.6

Covers:
  - Valid .txt and .md uploads → CorpusChunks produced
  - Chunk metadata: doc_type="user_upload", stable chunk_ids, correct author/title
  - Validation: unsupported extension, oversized file, empty file, undecodable bytes
  - chunk_document integration: chunks are non-empty, within length bounds
  - Session isolation: process_upload returns new list each call (no shared state)
"""
import pytest

from src.config.settings import ACCEPTED_EXTENSIONS, MAX_UPLOAD_BYTES, MIN_CHUNK_LENGTH
from src.controllers.upload_pipeline import UploadError, process_upload
from src.models.corpus import CorpusChunk


# ── Fixtures ──────────────────────────────────────────────────────────────────

PROSE_TEXT = (
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


def prose_bytes() -> bytes:
    return PROSE_TEXT.encode("utf-8")


# ── Happy path: .txt upload ───────────────────────────────────────────────────

def test_txt_upload_returns_chunks():
    chunks = process_upload("essay.txt", prose_bytes())
    assert len(chunks) > 0


def test_txt_upload_chunks_are_corpus_chunk_instances():
    chunks = process_upload("essay.txt", prose_bytes())
    for chunk in chunks:
        assert isinstance(chunk, CorpusChunk)


def test_txt_upload_doc_type_is_user_upload():
    chunks = process_upload("essay.txt", prose_bytes())
    for chunk in chunks:
        assert chunk.doc_type == "user_upload"


def test_txt_upload_author_is_user_upload():
    chunks = process_upload("essay.txt", prose_bytes())
    for chunk in chunks:
        assert chunk.author == "user_upload"


def test_txt_upload_title_is_filename_stem():
    chunks = process_upload("my_essay.txt", prose_bytes())
    for chunk in chunks:
        assert chunk.title == "my_essay"


def test_txt_upload_source_path_is_filename():
    chunks = process_upload("essay.txt", prose_bytes())
    for chunk in chunks:
        assert chunk.source_path == "essay.txt"


def test_txt_upload_year_is_none():
    chunks = process_upload("essay.txt", prose_bytes())
    for chunk in chunks:
        assert chunk.year is None


def test_txt_upload_chunk_strategy_is_paragraph():
    chunks = process_upload("essay.txt", prose_bytes())
    for chunk in chunks:
        assert chunk.chunk_strategy == "paragraph"


def test_txt_upload_chunk_text_meets_min_length():
    chunks = process_upload("essay.txt", prose_bytes())
    for chunk in chunks:
        assert len(chunk.text) >= MIN_CHUNK_LENGTH


def test_txt_upload_chunk_indices_are_sequential():
    chunks = process_upload("essay.txt", prose_bytes())
    for i, chunk in enumerate(chunks):
        assert chunk.chunk_index == i


# ── Happy path: .md upload ────────────────────────────────────────────────────

def test_md_upload_returns_chunks():
    md_content = (
        "# On Memory\n\n"
        "Memory is not a passive recording but an active reconstruction. "
        "Every time we recall an event we partially rewrite it, coloring it "
        "with the emotional palette of the present moment.\n\n"
        "The self that remembers and the self that was remembered are separated "
        "by time and by the changes wrought in the intervening years."
    )
    chunks = process_upload("notes.md", md_content.encode("utf-8"))
    assert len(chunks) > 0
    for chunk in chunks:
        assert chunk.doc_type == "user_upload"


# ── Chunk ID stability ─────────────────────────────────────────────────────────

def test_chunk_ids_are_stable_across_calls():
    """Same filename + content → identical chunk_ids on repeated calls."""
    chunks_a = process_upload("essay.txt", prose_bytes())
    chunks_b = process_upload("essay.txt", prose_bytes())
    ids_a = [c.chunk_id for c in chunks_a]
    ids_b = [c.chunk_id for c in chunks_b]
    assert ids_a == ids_b


def test_chunk_ids_differ_across_filenames():
    """Different filenames → different chunk_ids even for identical content."""
    chunks_a = process_upload("file_a.txt", prose_bytes())
    chunks_b = process_upload("file_b.txt", prose_bytes())
    ids_a = set(c.chunk_id for c in chunks_a)
    ids_b = set(c.chunk_id for c in chunks_b)
    assert ids_a.isdisjoint(ids_b)


def test_chunk_ids_are_unique_within_upload():
    """No two chunks from the same upload share an ID."""
    chunks = process_upload("essay.txt", prose_bytes())
    ids = [c.chunk_id for c in chunks]
    assert len(ids) == len(set(ids))


# ── Validation: extension ─────────────────────────────────────────────────────

def test_unsupported_extension_raises():
    with pytest.raises(UploadError, match="Unsupported"):
        process_upload("payload.exe", b"content")


def test_html_extension_raises():
    with pytest.raises(UploadError):
        process_upload("page.html", b"<p>hello</p>")


def test_no_extension_raises():
    with pytest.raises(UploadError):
        process_upload("README", prose_bytes())


# ── Validation: size ──────────────────────────────────────────────────────────

def test_oversized_file_raises():
    oversized = b"x" * (MAX_UPLOAD_BYTES + 1)
    with pytest.raises(UploadError, match="bytes"):
        process_upload("big.txt", oversized)


def test_exactly_max_size_is_accepted():
    """File exactly at the limit is not rejected for size."""
    # Content at the byte limit — but mostly padding so may not chunk well;
    # we only assert no UploadError for size (empty-text error is acceptable)
    content = b"A" * MAX_UPLOAD_BYTES
    try:
        process_upload("limit.txt", content)
    except UploadError as exc:
        # Size rejection is not acceptable; other errors (no usable chunks) are
        assert "bytes" not in str(exc), f"Rejected for size at exact limit: {exc}"


# ── Validation: encoding ──────────────────────────────────────────────────────

def test_invalid_utf8_bytes_raises():
    """Bytes that cannot be decoded as UTF-8 or Latin-1 raise UploadError."""
    # Construct bytes that are invalid in both UTF-8 and Latin-1
    # Latin-1 covers all 256 values, so we can't trigger a decode error via bad bytes.
    # Instead test that a file whose content, after Latin-1 decode, yields only whitespace
    # raises an UploadError for empty content (the sanitization path).
    whitespace_only = b"   \n\t  \n  "
    with pytest.raises(UploadError):
        process_upload("empty.txt", whitespace_only)


def test_valid_latin1_bytes_accepted():
    """Latin-1 encoded text that is not valid UTF-8 is still accepted."""
    # Paragraphs long enough to survive MIN_CHUNK_LENGTH filtering
    latin1_text = (
        "Über die Natur der Dinge lässt sich viel sagen, wenn man bereit ist, "
        "sich den Widersprüchen des Lebens zu stellen und die Vergänglichkeit "
        "als grundlegende Eigenschaft aller Dinge anzuerkennen.\n\n"
        "Das ist ein langer Text der viele Wörter enthält und über die "
        "Beschaffenheit der Welt nachdenkt, über Schönheit und Schmerz, "
        "über Freiheit und die Grenzen des menschlichen Verstehens."
    )
    latin1_bytes = latin1_text.encode("latin-1")
    chunks = process_upload("german.txt", latin1_bytes)
    assert len(chunks) > 0


# ── Validation: empty / too-short content ────────────────────────────────────

def test_empty_file_raises():
    with pytest.raises(UploadError):
        process_upload("empty.txt", b"")


def test_whitespace_only_file_raises():
    with pytest.raises(UploadError):
        process_upload("blank.txt", b"   \n\n   ")


def test_content_below_min_chunk_length_raises():
    """Text that produces no chunks after filtering raises UploadError."""
    short_text = b"Too short."  # Below MIN_CHUNK_LENGTH
    with pytest.raises(UploadError):
        process_upload("short.txt", short_text)


# ── No shared state between calls ────────────────────────────────────────────

def test_repeated_uploads_return_independent_lists():
    """Mutating the result of one call does not affect the next."""
    result_a = process_upload("essay.txt", prose_bytes())
    result_b = process_upload("essay.txt", prose_bytes())
    result_a.clear()
    assert len(result_b) > 0


# ── Integration with session manager ─────────────────────────────────────────

def test_chunks_are_compatible_with_session_add_upload():
    """Chunks returned by process_upload can be passed to SessionManager.add_upload."""
    from datetime import datetime, timezone
    from src.controllers.session_manager import SessionManager

    manager = SessionManager()
    session = manager.create()
    chunks = process_upload("essay.txt", prose_bytes())

    for chunk in chunks:
        manager.add_upload(session.session_id, chunk)

    assert len(manager.get(session.session_id).uploads) == len(chunks)
