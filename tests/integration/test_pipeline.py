"""
Integration tests for the core generation pipeline — PRD 2.8

Covers full cross-layer flows without a database or network:
  - run_generation_cycle end-to-end (generation → SVG → trace → graph)
  - process_consent cross-layer (session → graph ingestion)
  - upload_pipeline → session → consent → graph (document consent flow)
  - private voter bias (upload chunks preferred over graph chunks)

All state is in-memory.  No database, no disk state persists after each test.
SVG files are written to pytest's tmp_path and cleaned up automatically.
"""
import random
from pathlib import Path

import pytest

from src.controllers.consent import process_consent
from src.controllers.generation_cycle import (
    run_generation_cycle,
    select_private_voters,
)
from src.controllers.session_manager import SessionManager
from src.controllers.upload_pipeline import process_upload
from src.models.corpus import CorpusChunk
from src.models.graph import SemanticGraph


# ── Stubs ──────────────────────────────────────────────────────────────────────

class _StubTraceStore:
    def __init__(self):
        self._traces: dict[str, str] = {}

    def save(self, trace) -> None:
        self._traces[trace.artwork_id] = trace.to_text()

    def get(self, artwork_id: str) -> str | None:
        return self._traces.get(artwork_id)

    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        pass

    def close(self) -> None:
        pass


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_chunk(chunk_id: str, text: str | None = None) -> CorpusChunk:
    return CorpusChunk(
        chunk_id=chunk_id,
        source_path="data/test.txt",
        title="Test Work",
        author="Author",
        doc_type="literary",
        year=2024,
        chunk_index=0,
        text=text or "Sample text for testing purposes. Long enough for the chunker.",
        chunk_strategy="paragraph",
    )


def _populated_graph(n: int = 5) -> SemanticGraph:
    g = SemanticGraph(path=None)
    for i in range(n):
        g.add_source_node(_make_chunk(f"chunk_{i}"))
    return g


PROSE = (
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


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def graph():
    return _populated_graph(5)


@pytest.fixture
def trace_store():
    return _StubTraceStore()


@pytest.fixture
def session_manager():
    return SessionManager()


# ── Full generation cycle ──────────────────────────────────────────────────────

def test_generation_cycle_returns_result(graph, trace_store, tmp_path):
    result = run_generation_cycle(
        graph=graph,
        chunks={},
        trace_store=trace_store,
        output_dir=tmp_path,
        rng=random.Random(42),
    )
    assert result is not None


def test_generation_cycle_svg_written_to_disk(graph, trace_store, tmp_path):
    result = run_generation_cycle(
        graph=graph,
        chunks={},
        trace_store=trace_store,
        output_dir=tmp_path,
        rng=random.Random(42),
    )
    svg_path = Path(result["svg_path"])
    assert svg_path.exists(), f"SVG not found at {svg_path}"


def test_generation_cycle_svg_is_valid_xml(graph, trace_store, tmp_path):
    result = run_generation_cycle(
        graph=graph,
        chunks={},
        trace_store=trace_store,
        output_dir=tmp_path,
        rng=random.Random(42),
    )
    content = Path(result["svg_path"]).read_text(encoding="utf-8")
    assert content.startswith("<svg") or "<?xml" in content


def test_generation_cycle_adds_artwork_node_to_graph(graph, trace_store, tmp_path):
    before = graph.node_count()
    result = run_generation_cycle(
        graph=graph,
        chunks={},
        trace_store=trace_store,
        output_dir=tmp_path,
        rng=random.Random(42),
        ingest=True,
    )
    assert graph.node_count() > before
    # Artwork node should be retrievable
    assert graph.node_data(f"artwork:{result['artwork_id']}") is not None


def test_generation_cycle_ingest_false_skips_graph(graph, trace_store, tmp_path):
    before = graph.node_count()
    result = run_generation_cycle(
        graph=graph,
        chunks={},
        trace_store=trace_store,
        output_dir=tmp_path,
        rng=random.Random(42),
        ingest=False,
    )
    assert graph.node_count() == before
    assert graph.node_data(f"artwork:{result['artwork_id']}") is None


def test_generation_cycle_result_has_required_keys(graph, trace_store, tmp_path):
    result = run_generation_cycle(
        graph=graph,
        chunks={},
        trace_store=trace_store,
        output_dir=tmp_path,
        rng=random.Random(42),
    )
    for key in ("artwork_id", "svg_path", "trace_text", "voter_count", "voter_ids"):
        assert key in result, f"Missing key: {key}"


def test_generation_cycle_trace_text_is_nonempty(graph, trace_store, tmp_path):
    result = run_generation_cycle(
        graph=graph,
        chunks={},
        trace_store=trace_store,
        output_dir=tmp_path,
        rng=random.Random(42),
    )
    assert result["trace_text"].strip() != ""


def test_generation_cycle_trace_saved_to_store(graph, trace_store, tmp_path):
    result = run_generation_cycle(
        graph=graph,
        chunks={},
        trace_store=trace_store,
        output_dir=tmp_path,
        rng=random.Random(42),
    )
    saved = trace_store.get(result["artwork_id"])
    assert saved is not None
    assert saved.strip() != ""


def test_generation_cycle_voter_count_matches_voter_ids(graph, trace_store, tmp_path):
    result = run_generation_cycle(
        graph=graph,
        chunks={},
        trace_store=trace_store,
        output_dir=tmp_path,
        rng=random.Random(42),
    )
    assert result["voter_count"] == len(result["voter_ids"])


def test_generation_cycle_empty_graph_returns_none(trace_store, tmp_path):
    empty_graph = SemanticGraph(path=None)
    result = run_generation_cycle(
        graph=empty_graph,
        chunks={},
        trace_store=trace_store,
        output_dir=tmp_path,
        rng=random.Random(42),
    )
    assert result is None


def test_generation_cycle_multiple_artworks_all_in_graph(graph, trace_store, tmp_path):
    ids = []
    for seed in range(3):
        result = run_generation_cycle(
            graph=graph,
            chunks={},
            trace_store=trace_store,
            output_dir=tmp_path,
            rng=random.Random(seed),
            ingest=True,
        )
        ids.append(result["artwork_id"])

    # All artwork IDs are unique
    assert len(ids) == len(set(ids))
    # All are in the graph
    for artwork_id in ids:
        assert graph.node_data(f"artwork:{artwork_id}") is not None


# ── process_consent — artwork consent ─────────────────────────────────────────

def _fake_artwork_result(tmp_path: Path) -> dict:
    """Build a minimal artwork result dict with a real SVG file."""
    svg = tmp_path / "art.svg"
    svg.write_text("<svg/>", encoding="utf-8")
    return {
        "artwork_id": "art_consent_test",
        "svg_path": str(svg),
        "trace_text": "trace",
        "voter_count": 2,
        "voter_ids": ["chunk_0", "chunk_1"],
    }


def test_consent_artwork_yes_adds_artwork_node(graph, session_manager, tmp_path):
    sid = session_manager.create().session_id
    session_manager.record_artwork(sid, _fake_artwork_result(tmp_path))
    session = session_manager.end(sid)

    result = process_consent(
        session=session,
        artwork_consent=True,
        document_consent=False,
        graph=graph,
    )

    assert result.artworks_ingested == 1
    assert graph.node_data("artwork:art_consent_test") is not None


def test_consent_artwork_no_skips_graph(graph, session_manager, tmp_path):
    sid = session_manager.create().session_id
    session_manager.record_artwork(sid, _fake_artwork_result(tmp_path))
    session = session_manager.end(sid)

    before = graph.node_count()
    result = process_consent(
        session=session,
        artwork_consent=False,
        document_consent=False,
        graph=graph,
    )

    assert result.artworks_ingested == 0
    assert graph.node_count() == before
    assert graph.node_data("artwork:art_consent_test") is None


def test_consent_artwork_yes_returns_correct_count(graph, session_manager, tmp_path):
    sid = session_manager.create().session_id
    for i in range(3):
        svg = tmp_path / f"art_{i}.svg"
        svg.write_text("<svg/>", encoding="utf-8")
        session_manager.record_artwork(sid, {
            "artwork_id": f"art_{i}",
            "svg_path": str(svg),
            "trace_text": "",
            "voter_count": 1,
            "voter_ids": ["chunk_0"],
        })
    session = session_manager.end(sid)

    result = process_consent(
        session=session,
        artwork_consent=True,
        document_consent=False,
        graph=graph,
    )
    assert result.artworks_ingested == 3


# ── process_consent — document consent ────────────────────────────────────────

def test_consent_document_yes_adds_source_nodes(graph, session_manager):
    sid = session_manager.create().session_id
    chunk = _make_chunk("upload_chunk_0")
    session_manager.add_upload(sid, chunk)
    session = session_manager.end(sid)

    before = graph.node_count()
    result = process_consent(
        session=session,
        artwork_consent=False,
        document_consent=True,
        graph=graph,
    )

    assert result.documents_added == 1
    assert graph.node_count() == before + 1


def test_consent_document_no_skips_graph(graph, session_manager):
    sid = session_manager.create().session_id
    session_manager.add_upload(sid, _make_chunk("upload_chunk_discard"))
    session = session_manager.end(sid)

    before = graph.node_count()
    result = process_consent(
        session=session,
        artwork_consent=False,
        document_consent=False,
        graph=graph,
    )

    assert result.documents_added == 0
    assert graph.node_count() == before


def test_consent_no_for_both_discards_all(graph, session_manager, tmp_path):
    """No consent on either type leaves the graph completely unchanged."""
    sid = session_manager.create().session_id
    session_manager.record_artwork(sid, _fake_artwork_result(tmp_path))
    session_manager.add_upload(sid, _make_chunk("upload_discard_both"))
    session = session_manager.end(sid)

    before = graph.node_count()
    result = process_consent(
        session=session,
        artwork_consent=False,
        document_consent=False,
        graph=graph,
    )

    assert result.artworks_ingested == 0
    assert result.documents_added == 0
    assert graph.node_count() == before


def test_consent_both_yes_ingests_everything(graph, session_manager, tmp_path):
    sid = session_manager.create().session_id
    session_manager.record_artwork(sid, _fake_artwork_result(tmp_path))
    session_manager.add_upload(sid, _make_chunk("upload_both_yes"))
    session = session_manager.end(sid)

    result = process_consent(
        session=session,
        artwork_consent=True,
        document_consent=True,
        graph=graph,
    )

    assert result.artworks_ingested == 1
    assert result.documents_added == 1


# ── Upload pipeline → consent → graph ─────────────────────────────────────────

def test_upload_pipeline_then_consent_adds_source_nodes(graph, session_manager):
    """End-to-end: parse bytes → chunks → session → consent Yes → graph."""
    sid = session_manager.create().session_id

    # process_upload produces CorpusChunks from raw bytes
    chunks = process_upload("essay.txt", PROSE.encode("utf-8"))
    assert len(chunks) > 0

    for chunk in chunks:
        session_manager.add_upload(sid, chunk)

    session = session_manager.end(sid)
    before = graph.node_count()

    result = process_consent(
        session=session,
        artwork_consent=False,
        document_consent=True,
        graph=graph,
    )

    assert result.documents_added == len(chunks)
    assert graph.node_count() == before + len(chunks)


def test_upload_pipeline_consent_no_leaves_graph_unchanged(graph, session_manager):
    """Upload processed but consent refused — graph must not change."""
    sid = session_manager.create().session_id

    chunks = process_upload("essay.txt", PROSE.encode("utf-8"))
    for chunk in chunks:
        session_manager.add_upload(sid, chunk)

    session = session_manager.end(sid)
    before = graph.node_count()

    result = process_consent(
        session=session,
        artwork_consent=False,
        document_consent=False,
        graph=graph,
    )

    assert result.documents_added == 0
    assert graph.node_count() == before


def test_upload_chunks_have_user_upload_doc_type():
    """Uploaded chunks must be tagged user_upload — not a shared corpus type."""
    chunks = process_upload("essay.txt", PROSE.encode("utf-8"))
    for chunk in chunks:
        assert chunk.doc_type == "user_upload"


# ── Private voter bias ────────────────────────────────────────────────────────

def test_private_voters_prefer_uploaded_chunks():
    """
    Upload chunks carry UPLOAD_WEIGHT_BIAS (3.0) vs ~0.01 floor for isolated
    graph nodes.  Over many trials, uploads should win the majority of selections.
    """
    graph = SemanticGraph(path=None)
    # Add a few graph source nodes (isolated → floor weight 0.01 each)
    for i in range(3):
        graph.add_source_node(_make_chunk(f"graph_chunk_{i}"))

    upload_ids = ["upload_0", "upload_1", "upload_2"]
    rng = random.Random(99)
    upload_selections = 0
    trials = 200

    for _ in range(trials):
        voters = select_private_voters(graph, upload_ids, n=1, rng=rng)
        if voters and voters[0][0] in upload_ids:
            upload_selections += 1

    # With UPLOAD_WEIGHT_BIAS=3.0 vs 0.01 floor, uploads should dominate
    ratio = upload_selections / trials
    assert ratio > 0.80, f"Upload bias too weak: {ratio:.2%} upload selections"


def test_private_voters_include_graph_nodes():
    """When n >= pool size, all chunks (graph + uploads) are selected."""
    graph = SemanticGraph(path=None)
    graph.add_source_node(_make_chunk("graph_chunk_0"))
    upload_ids = ["upload_0"]

    voters = select_private_voters(graph, upload_ids, n=2, rng=random.Random(1))
    voter_ids = {v[0] for v in voters}

    assert "graph_chunk_0" in voter_ids
    assert "upload_0" in voter_ids


def test_private_voters_no_duplicates():
    """Each chunk_id appears at most once in the voter list."""
    graph = SemanticGraph(path=None)
    for i in range(5):
        graph.add_source_node(_make_chunk(f"chunk_{i}"))
    upload_ids = [f"upload_{i}" for i in range(5)]

    voters = select_private_voters(graph, upload_ids, n=8, rng=random.Random(7))
    ids = [v[0] for v in voters]
    assert len(ids) == len(set(ids))
