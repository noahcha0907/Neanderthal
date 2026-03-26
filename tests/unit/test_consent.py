"""
Unit tests for the session end consent flow — PRD 2.5

Covers:
  - run_generation_cycle result dict now includes voter_ids
  - process_consent: artwork consent Yes/No, document consent Yes/No,
    independence of both decisions, ConsentResult counts, coactivation,
    graph-save guard (in-memory graphs not saved), corpus_ingest_fn callback
"""
import random
from datetime import datetime, timezone

import pytest

from src.controllers.consent import ConsentResult, process_consent
from src.controllers.generation_cycle import run_generation_cycle
from src.models.corpus import CorpusChunk
from src.models.graph import SemanticGraph
from src.models.session import Session
from src.models.trace import JustificationTrace


# ── Stubs ─────────────────────────────────────────────────────────────────────

class _StubTraceStore:
    def save(self, trace: JustificationTrace) -> None:
        pass
    def commit(self) -> None:
        pass


class _StubChunkStore:
    def __init__(self):
        self.stored: list[CorpusChunk] = []
        self.committed = False

    def add(self, chunk: CorpusChunk) -> bool:
        self.stored.append(chunk)
        return True

    def commit(self) -> None:
        self.committed = True


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_graph() -> SemanticGraph:
    return SemanticGraph(path=None)


def make_chunk(chunk_id: str) -> CorpusChunk:
    return CorpusChunk(
        chunk_id=chunk_id,
        source_path="data/test.txt",
        title="Test Work",
        author="Author",
        doc_type="literary",
        year=2024,
        chunk_index=0,
        text="Sample text.",
        chunk_strategy="paragraph",
    )


def make_session(session_id: str = "test-session") -> Session:
    return Session(
        session_id=session_id,
        started_at=datetime.now(timezone.utc),
    )


def make_result(
    artwork_id: str,
    svg_path: str = "data/talent/art.svg",
    voter_ids: list[str] | None = None,
) -> dict:
    return {
        "artwork_id": artwork_id,
        "svg_path": svg_path,
        "trace_text": "trace",
        "voter_count": len(voter_ids or []),
        "voter_ids": voter_ids or [],
    }


def populated_graph(n: int = 3) -> SemanticGraph:
    g = make_graph()
    for i in range(n):
        g.add_source_node(make_chunk(f"chunk_{i}"))
    return g


# ── run_generation_cycle result includes voter_ids ────────────────────────────

def test_generation_cycle_result_includes_voter_ids(tmp_path):
    g = populated_graph(3)
    chunks = {cid: make_chunk(cid) for cid, _ in g.source_node_weights()}
    result = run_generation_cycle(
        graph=g,
        chunks=chunks,
        trace_store=_StubTraceStore(),
        output_dir=tmp_path,
        rng=random.Random(0),
    )
    assert "voter_ids" in result
    assert isinstance(result["voter_ids"], list)
    assert len(result["voter_ids"]) == result["voter_count"]


def test_generation_cycle_voter_ids_are_valid_chunk_ids(tmp_path):
    g = populated_graph(3)
    known_ids = {cid for cid, _ in g.source_node_weights()}
    chunks = {cid: make_chunk(cid) for cid in known_ids}
    result = run_generation_cycle(
        graph=g,
        chunks=chunks,
        trace_store=_StubTraceStore(),
        output_dir=tmp_path,
        rng=random.Random(1),
    )
    for cid in result["voter_ids"]:
        assert cid in known_ids


# ── process_consent: artwork consent ─────────────────────────────────────────

def test_artwork_consent_yes_ingests_artwork_node():
    session = make_session()
    g = populated_graph(2)
    session.artworks.append(make_result("art_1", voter_ids=["chunk_0", "chunk_1"]))

    result = process_consent(session, artwork_consent=True, document_consent=False, graph=g)

    assert g._graph.has_node("artwork:art_1")
    assert result.artworks_ingested == 1


def test_artwork_consent_yes_links_voter_chunks():
    session = make_session()
    g = populated_graph(2)
    session.artworks.append(make_result("art_1", voter_ids=["chunk_0", "chunk_1"]))

    process_consent(session, artwork_consent=True, document_consent=False, graph=g)

    assert g._graph.has_edge("artwork:art_1", "chunk_0")
    assert g._graph.has_edge("artwork:art_1", "chunk_1")


def test_artwork_consent_yes_coactivates_multi_voter():
    session = make_session()
    g = populated_graph(2)
    session.artworks.append(make_result("art_1", voter_ids=["chunk_0", "chunk_1"]))

    process_consent(session, artwork_consent=True, document_consent=False, graph=g)

    assert g._graph.has_edge("chunk_0", "chunk_1")
    assert g._graph.has_edge("chunk_1", "chunk_0")


def test_artwork_consent_yes_single_voter_no_coactivation():
    session = make_session()
    g = populated_graph(2)
    session.artworks.append(make_result("art_1", voter_ids=["chunk_0"]))

    before = g.edge_count()
    process_consent(session, artwork_consent=True, document_consent=False, graph=g)

    # Only the influence edge was added (artwork→chunk); no coactivation edge
    assert g._graph.has_edge("artwork:art_1", "chunk_0")


def test_artwork_consent_yes_ingests_all_artworks():
    session = make_session()
    g = populated_graph(3)
    for i in range(3):
        session.artworks.append(make_result(f"art_{i}", voter_ids=["chunk_0"]))

    result = process_consent(session, artwork_consent=True, document_consent=False, graph=g)

    assert result.artworks_ingested == 3
    for i in range(3):
        assert g._graph.has_node(f"artwork:art_{i}")


def test_artwork_consent_no_ingests_nothing():
    session = make_session()
    g = populated_graph(2)
    session.artworks.append(make_result("art_1", voter_ids=["chunk_0"]))

    result = process_consent(session, artwork_consent=False, document_consent=False, graph=g)

    assert result.artworks_ingested == 0
    assert not g._graph.has_node("artwork:art_1")


def test_artwork_consent_empty_session():
    session = make_session()
    g = populated_graph(2)

    result = process_consent(session, artwork_consent=True, document_consent=False, graph=g)

    assert result.artworks_ingested == 0


def test_artwork_consent_missing_voter_ids_graceful():
    """Result dicts without voter_ids default to [] — no crash."""
    session = make_session()
    g = make_graph()
    session.artworks.append({
        "artwork_id": "art_1",
        "svg_path": "data/talent/art_1.svg",
        "trace_text": "",
        "voter_count": 0,
        # voter_ids intentionally absent
    })

    result = process_consent(session, artwork_consent=True, document_consent=False, graph=g)

    assert result.artworks_ingested == 1
    assert g._graph.has_node("artwork:art_1")


# ── process_consent: document consent ────────────────────────────────────────

def test_document_consent_yes_adds_source_nodes():
    session = make_session()
    g = make_graph()
    session.uploads.append(make_chunk("upload_a"))
    session.uploads.append(make_chunk("upload_b"))

    result = process_consent(session, artwork_consent=False, document_consent=True, graph=g)

    assert g._graph.has_node("upload_a")
    assert g._graph.has_node("upload_b")
    assert result.documents_added == 2


def test_document_consent_yes_stores_in_chunk_store():
    session = make_session()
    g = make_graph()
    session.uploads.append(make_chunk("upload_a"))
    store = _StubChunkStore()

    process_consent(
        session, artwork_consent=False, document_consent=True,
        graph=g, chunk_store=store,
    )

    assert len(store.stored) == 1
    assert store.stored[0].chunk_id == "upload_a"
    assert store.committed


def test_document_consent_yes_calls_corpus_ingest_fn():
    session = make_session()
    g = make_graph()
    session.uploads.append(make_chunk("upload_a"))
    session.uploads.append(make_chunk("upload_b"))
    received: list[list[CorpusChunk]] = []

    process_consent(
        session, artwork_consent=False, document_consent=True,
        graph=g, corpus_ingest_fn=received.append,
    )

    assert len(received) == 1
    assert {c.chunk_id for c in received[0]} == {"upload_a", "upload_b"}


def test_document_consent_no_discards_uploads():
    session = make_session()
    g = make_graph()
    session.uploads.append(make_chunk("upload_a"))
    store = _StubChunkStore()

    result = process_consent(
        session, artwork_consent=False, document_consent=False,
        graph=g, chunk_store=store,
    )

    assert result.documents_added == 0
    assert not g._graph.has_node("upload_a")
    assert len(store.stored) == 0


def test_document_consent_yes_no_uploads_returns_zero():
    """document_consent=True but session has no uploads → 0 added, no crash."""
    session = make_session()
    g = make_graph()

    result = process_consent(session, artwork_consent=False, document_consent=True, graph=g)

    assert result.documents_added == 0


def test_document_consent_no_chunk_store_still_adds_to_graph():
    """chunk_store=None — skips DB storage but still updates the graph."""
    session = make_session()
    g = make_graph()
    session.uploads.append(make_chunk("upload_a"))

    process_consent(
        session, artwork_consent=False, document_consent=True,
        graph=g, chunk_store=None,
    )

    assert g._graph.has_node("upload_a")


# ── Independence of both consents ─────────────────────────────────────────────

def test_artwork_yes_document_no():
    session = make_session()
    g = populated_graph(2)
    session.artworks.append(make_result("art_1", voter_ids=["chunk_0"]))
    session.uploads.append(make_chunk("upload_a"))

    result = process_consent(session, artwork_consent=True, document_consent=False, graph=g)

    assert result.artworks_ingested == 1
    assert result.documents_added == 0
    assert g._graph.has_node("artwork:art_1")
    assert not g._graph.has_node("upload_a")


def test_artwork_no_document_yes():
    session = make_session()
    g = populated_graph(2)
    session.artworks.append(make_result("art_1", voter_ids=["chunk_0"]))
    session.uploads.append(make_chunk("upload_a"))

    result = process_consent(session, artwork_consent=False, document_consent=True, graph=g)

    assert result.artworks_ingested == 0
    assert result.documents_added == 1
    assert not g._graph.has_node("artwork:art_1")
    assert g._graph.has_node("upload_a")


def test_both_yes():
    session = make_session()
    g = populated_graph(2)
    session.artworks.append(make_result("art_1", voter_ids=["chunk_0"]))
    session.uploads.append(make_chunk("upload_a"))

    result = process_consent(session, artwork_consent=True, document_consent=True, graph=g)

    assert result.artworks_ingested == 1
    assert result.documents_added == 1
    assert g._graph.has_node("artwork:art_1")
    assert g._graph.has_node("upload_a")


def test_both_no():
    session = make_session()
    g = populated_graph(2)
    session.artworks.append(make_result("art_1", voter_ids=["chunk_0"]))
    session.uploads.append(make_chunk("upload_a"))

    result = process_consent(session, artwork_consent=False, document_consent=False, graph=g)

    assert result.artworks_ingested == 0
    assert result.documents_added == 0


# ── In-memory graph not saved to disk ────────────────────────────────────────

def test_in_memory_graph_not_saved(tmp_path):
    """Graph with path=None must not attempt a save (would raise)."""
    session = make_session()
    g = make_graph()  # path=None
    session.artworks.append(make_result("art_1", voter_ids=[]))

    # Must not raise RuntimeError("Cannot save an in-memory graph")
    process_consent(session, artwork_consent=True, document_consent=False, graph=g)
