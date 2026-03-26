"""
Unit tests for chunking strategies — PRD 1.1
"""
import pytest
from src.helpers.chunker import chunk_document, _filter_chunks, _truncate_at_sentence

# ── Fixtures ───────────────────────────────────────────────────────────────

PROSE = (
    "The weight of history presses down upon each generation in turn. "
    "We inherit the failures and the achievements alike, bound together "
    "by the long chain of cause and effect that stretches back through time.\n\n"
    "What we call progress is often nothing more than the reordering of old "
    "mistakes into new configurations that feel, briefly, like solutions. "
    "The mind finds comfort in novelty, even when the underlying structure remains.\n\n"
    "A third idea enters now, distinct from what came before. It stands alone, "
    "asserting its own logic, refusing to be absorbed into the narrative of the prior paragraphs."
)

POEM = (
    "Shall I compare thee to a summer's day?\n"
    "Thou art more lovely and more temperate.\n"
    "Rough winds do shake the darling buds of May,\n"
    "And summer's lease hath all too short a date.\n\n"
    "Sometime too hot the eye of heaven shines,\n"
    "And often is his gold complexion dimm'd;\n"
    "And every fair from fair sometime declines,\n"
    "By chance, or nature's changing course, untrimm'd.\n\n"
    "But thy eternal summer shall not fade,\n"
    "Nor lose possession of that fair thou ow'st."
)

TEXTBOOK = (
    "Chapter 1 The Foundations of Democracy\n"
    "The origins of democratic thought stretch back to ancient Athens, where "
    "citizens gathered to debate the laws that governed their city. This tradition "
    "of civic participation shaped Western political philosophy for millennia.\n\n"
    "Chapter 2 The American Revolution\n"
    "The American Revolution was not merely a political upheaval but a profound "
    "shift in how people understood their relationship to government and authority. "
    "The colonial grievances ran deep, and the resulting documents endure."
)

# ── Paragraph / stanza chunking ────────────────────────────────────────────

def test_prose_chunks_on_blank_lines():
    chunks = chunk_document(PROSE, "literary")
    assert len(chunks) == 3


def test_poem_chunks_on_stanzas():
    chunks = chunk_document(POEM, "poem")
    assert len(chunks) == 3


def test_lyric_produces_same_chunks_as_poem():
    assert chunk_document(POEM, "lyric") == chunk_document(POEM, "poem")


def test_philosophy_uses_paragraph_strategy():
    chunks = chunk_document(PROSE, "philosophy")
    assert len(chunks) == 3


def test_history_uses_paragraph_strategy():
    chunks = chunk_document(PROSE, "history")
    assert len(chunks) == 3


# ── Section chunking ───────────────────────────────────────────────────────

def test_textbook_chunks_on_chapter_headings():
    chunks = chunk_document(TEXTBOOK, "textbook_us_history")
    assert len(chunks) >= 2


def test_textbook_world_history_uses_section_strategy():
    chunks = chunk_document(TEXTBOOK, "textbook_world_history")
    assert len(chunks) >= 2


def test_textbook_design_uses_section_strategy():
    chunks = chunk_document(TEXTBOOK, "textbook_design")
    assert len(chunks) >= 2


# ── Filtering ──────────────────────────────────────────────────────────────

def test_short_chunks_are_discarded():
    text = "Too short.\n\nAlso tiny.\n\n" + ("This is a long enough paragraph. " * 5)
    chunks = chunk_document(text, "literary")
    for chunk in chunks:
        assert len(chunk) >= 50


def test_oversized_chunk_is_truncated():
    long_chunk = "A" * 1400 + ". Final sentence ends here properly."
    chunks = _filter_chunks([long_chunk])
    assert len(chunks) == 1
    assert len(chunks[0]) <= 1500


def test_empty_text_returns_empty_list():
    assert chunk_document("", "literary") == []


def test_whitespace_only_text_returns_empty_list():
    assert chunk_document("   \n\n   \t  ", "literary") == []


def test_unknown_doc_type_falls_back_to_paragraph():
    # Unknown types default to paragraph strategy without raising
    chunks = chunk_document(PROSE, "unknown_type")
    assert len(chunks) == 3


# ── Truncation ─────────────────────────────────────────────────────────────

def test_truncate_at_sentence_respects_max_length():
    text = ("This is a sentence. " * 100)
    result = _truncate_at_sentence(text, 200)
    assert len(result) <= 200


def test_truncate_short_text_unchanged():
    text = "Short text."
    assert _truncate_at_sentence(text, 500) == text
