"""
Chunking strategies for the corpus ingestion pipeline (PRD 1.1).

Three strategies:
  paragraph — splits on blank lines. Used for literary, philosophy, history.
  stanza    — splits on blank lines. Used for poems and song lyrics.
              Mechanically identical to paragraph but semantically distinct:
              stanzas are shorter, more self-contained units.
  section   — splits on heading-like lines. Used for textbooks.
              Falls back to paragraph splitting if no headings are detected.

Public API:
  chunk_document(text, doc_type) → list[str]
"""
import re
from src.config.settings import MIN_CHUNK_LENGTH, MAX_CHUNK_LENGTH, CHUNK_STRATEGIES


def chunk_document(text: str, doc_type: str) -> list[str]:
    """
    Split document text into semantically meaningful chunks.

    Dispatches to the correct strategy based on doc_type, then filters
    chunks that are too short or truncates those that are too long.
    Returns an empty list for empty or whitespace-only input.
    """
    if not text or not text.strip():
        return []

    strategy = CHUNK_STRATEGIES.get(doc_type, "paragraph")

    if strategy in ("paragraph", "stanza"):
        raw = _split_on_blank_lines(text)
    elif strategy == "section":
        raw = _split_on_sections(text)
    else:
        raw = _split_on_blank_lines(text)

    return _filter_chunks(raw)


def _split_on_blank_lines(text: str) -> list[str]:
    """Split text into blocks separated by one or more blank lines."""
    blocks = re.split(r"\n{2,}", text.strip())
    return [b.strip() for b in blocks if b.strip()]


def _split_on_sections(text: str) -> list[str]:
    """
    Split textbook text at section headings.

    Headings are detected as lines matching any of:
      - "Chapter N", "Section N.N", "Part N", "Unit N" (case-insensitive)
      - Lines in ALL CAPS between 5 and 80 characters

    Each heading begins a new chunk that includes the heading plus all
    following text until the next heading. Falls back to paragraph splitting
    if the heuristic detects no headings.
    """
    heading_re = re.compile(
        r"^(?:"
        r"(?:chapter|section|part|unit)\s+[\dIVXivx][\w.]*"  # Chapter 3, Section 2.1
        r"|[A-Z][A-Z\s\d,:\-]{4,79}"                         # ALL CAPS heading
        r")$",
        re.MULTILINE,
    )

    lines = text.split("\n")
    chunks: list[str] = []
    current: list[str] = []

    for line in lines:
        if heading_re.match(line.strip()) and current:
            chunks.append("\n".join(current).strip())
            current = [line]
        else:
            current.append(line)

    if current:
        chunks.append("\n".join(current).strip())

    # Fall back if the heuristic found no headings
    if len(chunks) <= 1:
        return _split_on_blank_lines(text)

    return [c for c in chunks if c.strip()]


def _filter_chunks(chunks: list[str]) -> list[str]:
    """
    Remove chunks below MIN_CHUNK_LENGTH.
    Truncate chunks above MAX_CHUNK_LENGTH at the nearest sentence boundary.
    """
    result: list[str] = []
    for chunk in chunks:
        if len(chunk) < MIN_CHUNK_LENGTH:
            continue
        if len(chunk) > MAX_CHUNK_LENGTH:
            result.append(_truncate_at_sentence(chunk, MAX_CHUNK_LENGTH))
        else:
            result.append(chunk)
    return result


def _truncate_at_sentence(text: str, max_length: int) -> str:
    """
    Truncate text to at most max_length characters, ending at the nearest
    sentence boundary (". " or ".\n"). If no boundary is found in the latter
    half of the allowed range, truncates at the hard limit.
    """
    if len(text) <= max_length:
        return text

    window = text[:max_length]
    last_period = max(window.rfind(". "), window.rfind(".\n"))

    # Only snap to the sentence boundary if it's in the latter half of the window
    if last_period > max_length // 2:
        return window[: last_period + 1].strip()

    return window.strip()
