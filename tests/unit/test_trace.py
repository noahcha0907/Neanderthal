"""
Unit tests for the justification trace system — PRD 1.7

Covers:
  - extract_excerpt helper
  - TraceEntry and JustificationTrace dataclasses
  - build_trace attribution logic
  - JustificationTrace.to_text() formatting
  - TraceStore DB round-trip (uses shared-connection rollback isolation)
"""
import pytest

from src.helpers.text_utils import extract_excerpt
from src.models.art_params import ArtParameters, ShapeParams
from src.models.corpus import CorpusChunk
from src.models.trace import JustificationTrace, TraceEntry, build_trace
from src.models.trace_store import TraceStore
from src.models.voting import vote_on_parameters


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_chunk(chunk_id: str, title: str = "Test Work", author: str = "Test Author",
               text: str = "First sentence here. Second sentence follows. Third one too.") -> CorpusChunk:
    return CorpusChunk(
        chunk_id=chunk_id,
        source_path="data/humanities/test.txt",
        title=title,
        author=author,
        doc_type="literary",
        year=2024,
        chunk_index=0,
        text=text,
        chunk_strategy="paragraph",
    )


def make_shape(**overrides) -> ShapeParams:
    defaults = dict(
        shape_type="circle", fill_color="#FF0000", stroke_color="#000000",
        stroke_width=1, x=0.5, y=0.5, size=0.2, opacity=1.0,
    )
    defaults.update(overrides)
    return ShapeParams(**defaults)


# ── extract_excerpt ────────────────────────────────────────────────────────────

def test_extract_excerpt_returns_two_sentences():
    text = "First sentence here. Second sentence follows. Third one too."
    result = extract_excerpt(text, n_sentences=2)
    assert result == "First sentence here. Second sentence follows."


def test_extract_excerpt_handles_fewer_sentences():
    text = "Only one sentence here"
    result = extract_excerpt(text, n_sentences=2)
    assert result == "Only one sentence here"


def test_extract_excerpt_strips_whitespace():
    text = "  First sentence.  Second sentence.  "
    result = extract_excerpt(text, n_sentences=2)
    assert not result.startswith(" ")
    assert not result.endswith(" ")


def test_extract_excerpt_empty_string():
    assert extract_excerpt("") == ""


def test_extract_excerpt_handles_exclamation_and_question():
    text = "Is this a question? Yes it is! And this is third."
    result = extract_excerpt(text, n_sentences=2)
    assert "Is this a question?" in result
    assert "Yes it is!" in result
    assert "And this is third." not in result


# ── TraceEntry and JustificationTrace ─────────────────────────────────────────

def test_trace_entry_stores_all_fields():
    entry = TraceEntry(
        label="background_color",
        value="#0000FF",
        title="Meditations",
        author="Marcus Aurelius",
        excerpt="The weight of history. We inherit failures.",
        other_count=2,
    )
    assert entry.label == "background_color"
    assert entry.value == "#0000FF"
    assert entry.other_count == 2


def test_justification_trace_to_text_contains_artwork_id():
    trace = JustificationTrace(artwork_id="test-id-123", entries=[])
    assert "test-id-123" in trace.to_text()


def test_justification_trace_to_text_formats_entry():
    entry = TraceEntry(
        label="background_color", value="#FF0000",
        title="Meditations", author="Marcus Aurelius",
        excerpt="The weight of history. We inherit failures.",
        other_count=2,
    )
    trace = JustificationTrace(artwork_id="art-1", entries=[entry])
    text = trace.to_text()

    assert "background_color: #FF0000" in text
    assert "Meditations (Marcus Aurelius)" in text
    assert '"The weight of history.' in text
    assert "+2 chunks affected" in text


def test_justification_trace_singular_chunk_grammar():
    """'+1 chunk affected' uses singular, not '+1 chunks affected'."""
    entry = TraceEntry(
        label="shape_count", value="3",
        title="Test", author="Author",
        excerpt="Some text.",
        other_count=1,
    )
    trace = JustificationTrace(artwork_id="art-1", entries=[entry])
    assert "+1 chunk affected" in trace.to_text()
    assert "+1 chunks" not in trace.to_text()


def test_justification_trace_zero_other_chunks():
    entry = TraceEntry(
        label="x", value="0.5000",
        title="Test", author="Author",
        excerpt="Some text.",
        other_count=0,
    )
    trace = JustificationTrace(artwork_id="art-1", entries=[entry])
    assert "+0 chunks affected" in trace.to_text()


# ── build_trace ───────────────────────────────────────────────────────────────

VOTERS_SINGLE = [("chunk_a", 1.0)]
VOTERS_MULTI  = [("chunk_a", 0.7), ("chunk_b", 0.3)]

CHUNKS = {
    "chunk_a": make_chunk("chunk_a", title="Meditations",       author="Marcus Aurelius"),
    "chunk_b": make_chunk("chunk_b", title="Thus Spoke Zarathustra", author="Nietzsche"),
}


def test_build_trace_raises_for_empty_voters():
    params = vote_on_parameters([("chunk_a", 1.0)])
    with pytest.raises(ValueError):
        build_trace("art-1", [], params, CHUNKS)


def test_build_trace_returns_justification_trace():
    params = vote_on_parameters(VOTERS_SINGLE)
    trace = build_trace("art-1", VOTERS_SINGLE, params, CHUNKS)
    assert isinstance(trace, JustificationTrace)
    assert trace.artwork_id == "art-1"


def test_build_trace_entry_count():
    """
    Entry count = 2 (artwork-level) + n_shapes * 8 (per-shape fields).
    """
    voters = [("chunk_a", 1.0)]
    params = vote_on_parameters(voters)
    trace = build_trace("art-1", voters, params, CHUNKS)
    expected = 2 + len(params.shapes) * 8
    assert len(trace.entries) == expected


def test_build_trace_first_entry_is_background_color():
    params = vote_on_parameters(VOTERS_SINGLE)
    trace = build_trace("art-1", VOTERS_SINGLE, params, CHUNKS)
    assert trace.entries[0].label == "background_color"
    assert trace.entries[0].value == params.background_color


def test_build_trace_second_entry_is_shape_count():
    params = vote_on_parameters(VOTERS_SINGLE)
    trace = build_trace("art-1", VOTERS_SINGLE, params, CHUNKS)
    assert trace.entries[1].label == "shape_count"
    assert trace.entries[1].value == str(len(params.shapes))


def test_build_trace_shape_entries_have_correct_labels():
    """Shape entries follow the pattern 'Shape N — field_name'."""
    params = vote_on_parameters(VOTERS_SINGLE)
    trace = build_trace("art-1", VOTERS_SINGLE, params, CHUNKS)
    shape_entries = trace.entries[2:]
    fields_per_shape = ["shape_type", "fill_color", "stroke_color", "stroke_width",
                        "x", "y", "size", "opacity"]
    for i in range(len(params.shapes)):
        for j, field in enumerate(fields_per_shape):
            idx = i * 8 + j
            assert trace.entries[2 + idx].label == f"Shape {i} — {field}"


def test_build_trace_uses_chunk_title_and_author():
    """Entries reference the correct title and author from the chunks dict."""
    params = vote_on_parameters(VOTERS_SINGLE)
    trace = build_trace("art-1", VOTERS_SINGLE, params, CHUNKS)
    # All entries must come from one of the known chunks
    known_titles = {c.title for c in CHUNKS.values()} | {"Unknown"}
    for entry in trace.entries:
        assert entry.title in known_titles


def test_build_trace_excerpt_is_two_sentences():
    """Excerpts contain at most two sentences."""
    params = vote_on_parameters(VOTERS_SINGLE)
    trace = build_trace("art-1", VOTERS_SINGLE, params, CHUNKS)
    for entry in trace.entries:
        # The excerpt should not be longer than the chunk text's first two sentences
        assert len(entry.excerpt) <= 200   # rough upper bound for 2 sentences


def test_build_trace_other_count_equals_voters_minus_one():
    """other_count is always len(voters) - 1, regardless of the parameter."""
    for voters in [VOTERS_SINGLE, VOTERS_MULTI]:
        params = vote_on_parameters(voters)
        trace = build_trace("art-1", voters, params, CHUNKS)
        expected = len(voters) - 1
        for entry in trace.entries:
            assert entry.other_count == expected


def test_build_trace_unknown_chunk_id_handled_gracefully():
    """A voter whose chunk_id is not in chunks dict does not raise."""
    voters = [("unknown_id", 1.0)]
    params = vote_on_parameters(voters)
    trace = build_trace("art-1", voters, params, {})
    for entry in trace.entries:
        assert entry.title == "Unknown"
        assert entry.excerpt == ""


def test_build_trace_is_deterministic():
    """Same inputs always produce the same trace."""
    params = vote_on_parameters(VOTERS_MULTI)
    t1 = build_trace("art-1", VOTERS_MULTI, params, CHUNKS)
    t2 = build_trace("art-1", VOTERS_MULTI, params, CHUNKS)
    assert t1.to_text() == t2.to_text()


# ── TraceStore (DB) ────────────────────────────────────────────────────────────

@pytest.fixture
def trace_store(store):
    """TraceStore sharing the ChunkStore's connection for rollback isolation."""
    return TraceStore(store._conn)


def test_trace_store_save_and_get(trace_store):
    """A saved trace is retrievable by artwork_id."""
    trace = JustificationTrace(
        artwork_id="test-artwork-001",
        entries=[TraceEntry("background_color", "#FF0000", "Meditations",
                            "Aurelius", "First. Second.", 1)],
    )
    trace_store.save(trace)
    result = trace_store.get("test-artwork-001")
    assert result is not None
    assert "background_color" in result
    assert "Meditations" in result


def test_trace_store_get_nonexistent(trace_store):
    """get() returns None for an artwork_id that was never saved."""
    assert trace_store.get("does-not-exist-xyz") is None


def test_trace_store_save_upserts_on_conflict(trace_store):
    """Saving twice with the same artwork_id updates the trace, not errors."""
    trace_v1 = JustificationTrace(
        artwork_id="test-artwork-002",
        entries=[TraceEntry("background_color", "#FF0000", "Work A", "Author A", "Text.", 0)],
    )
    trace_v2 = JustificationTrace(
        artwork_id="test-artwork-002",
        entries=[TraceEntry("background_color", "#0000FF", "Work B", "Author B", "Text.", 0)],
    )
    trace_store.save(trace_v1)
    trace_store.save(trace_v2)
    result = trace_store.get("test-artwork-002")
    assert "Work B" in result
    assert "Work A" not in result


def test_trace_store_get_returns_full_text(trace_store):
    """The text returned by get() matches what to_text() produced."""
    voters = VOTERS_MULTI
    params = vote_on_parameters(voters)
    trace = build_trace("art-full-text", voters, params, CHUNKS)
    trace_store.save(trace)
    result = trace_store.get("art-full-text")
    assert result == trace.to_text()
