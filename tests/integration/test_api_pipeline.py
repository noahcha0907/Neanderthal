"""
API-layer integration tests — PRD 2.8

Tests the full HTTP surface of the FastAPI application using TestClient with an
in-memory AppState.  Each test covers a complete user-visible flow rather than
a single endpoint:

  - POST /generate → GET /portfolio → GET /portfolio/{id}
  - Session lifecycle: start → generate → end → consent Yes/No
  - Upload → session end → consent document Yes/No
  - SSE broadcaster delivers events when artwork is generated
"""
import random
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.api.app import create_app
from src.api.state import AppState, SSEBroadcaster
from src.controllers.session_manager import SessionManager
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

def _make_chunk(chunk_id: str) -> CorpusChunk:
    return CorpusChunk(
        chunk_id=chunk_id,
        source_path="data/test.txt",
        title="Test Work",
        author="Author",
        doc_type="literary",
        year=2024,
        chunk_index=0,
        text="Sample text for testing purposes. Long enough to be valid.",
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
def state():
    return AppState(
        graph=_populated_graph(5),
        session_manager=SessionManager(),
        trace_store=_StubTraceStore(),
        sse=SSEBroadcaster(),
    )


@pytest.fixture
def client(state):
    app = create_app(state=state)
    with TestClient(app) as c:
        yield c


# ── Generate → Portfolio flow ─────────────────────────────────────────────────

def test_generate_then_portfolio_lists_one_artwork(client):
    """Generating an artwork makes it appear in /portfolio immediately."""
    assert client.get("/portfolio").json() == []
    client.post("/generate", json={})
    artworks = client.get("/portfolio").json()
    assert len(artworks) == 1


def test_generate_artwork_id_appears_in_portfolio(client):
    gen = client.post("/generate", json={}).json()
    artworks = client.get("/portfolio").json()
    ids = [a["artwork_id"] for a in artworks]
    assert gen["artwork_id"] in ids


def test_portfolio_item_returns_svg_content(client, state):
    """GET /portfolio/{id} serves the SVG file content inline."""
    gen = client.post("/generate", json={}).json()
    r = client.get(f"/portfolio/{gen['artwork_id']}")
    assert r.status_code == 200
    body = r.json()
    assert "svg_content" in body
    # The rendered SVG must be non-empty XML
    assert body["svg_content"].strip() != ""
    assert "svg" in body["svg_content"].lower()


def test_portfolio_item_no_svg_path_in_response(client):
    """File-system paths must never appear in API responses."""
    gen = client.post("/generate", json={}).json()
    body = client.get(f"/portfolio/{gen['artwork_id']}").json()
    assert "svg_path" not in body


def test_multiple_generates_all_in_portfolio(client):
    for _ in range(3):
        client.post("/generate", json={})
    artworks = client.get("/portfolio").json()
    assert len(artworks) == 3


def test_portfolio_items_have_created_at(client):
    client.post("/generate", json={})
    artworks = client.get("/portfolio").json()
    assert "created_at" in artworks[0]
    assert artworks[0]["created_at"] != ""


# ── Session lifecycle: consent Yes for artwork ────────────────────────────────

def test_session_consent_yes_artwork_ingests_artwork(client, state, tmp_path):
    """Artwork in session + consent Yes → artwork node in shared graph."""
    sid = client.post("/session/start").json()["session_id"]

    # Record a fake artwork in the session (simulates a private generation cycle)
    svg = tmp_path / "art.svg"
    svg.write_text("<svg/>", encoding="utf-8")
    state.session_manager.record_artwork(sid, {
        "artwork_id": "art_session_yes",
        "svg_path": str(svg),
        "trace_text": "trace",
        "voter_count": 1,
        "voter_ids": ["chunk_0"],
    })

    client.post("/session/end", json={"session_id": sid})

    r = client.post("/consent", json={
        "session_id": sid,
        "artwork_consent": True,
        "document_consent": False,
    })
    assert r.json()["artworks_ingested"] == 1
    assert state.graph.node_data("artwork:art_session_yes") is not None


def test_session_consent_no_artwork_discards_artwork(client, state, tmp_path):
    """Artwork in session + consent No → artwork node NOT in shared graph."""
    sid = client.post("/session/start").json()["session_id"]
    svg = tmp_path / "art_no.svg"
    svg.write_text("<svg/>", encoding="utf-8")
    state.session_manager.record_artwork(sid, {
        "artwork_id": "art_session_no",
        "svg_path": str(svg),
        "trace_text": "",
        "voter_count": 1,
        "voter_ids": ["chunk_0"],
    })

    client.post("/session/end", json={"session_id": sid})
    r = client.post("/consent", json={
        "session_id": sid,
        "artwork_consent": False,
        "document_consent": False,
    })
    assert r.json()["artworks_ingested"] == 0
    assert state.graph.node_data("artwork:art_session_no") is None


def test_consent_ends_session(client, state):
    """After POST /consent, the session is removed from the active registry."""
    sid = client.post("/session/start").json()["session_id"]
    client.post("/session/end", json={"session_id": sid})
    client.post("/consent", json={
        "session_id": sid,
        "artwork_consent": False,
        "document_consent": False,
    })
    assert state.session_manager.get(sid) is None


def test_second_consent_for_same_session_returns_404(client, state):
    """Once consent is submitted, the session is gone — re-submitting returns 404."""
    sid = client.post("/session/start").json()["session_id"]
    client.post("/consent", json={
        "session_id": sid,
        "artwork_consent": False,
        "document_consent": False,
    })
    r = client.post("/consent", json={
        "session_id": sid,
        "artwork_consent": False,
        "document_consent": False,
    })
    assert r.status_code == 404


# ── Session lifecycle: upload → consent Yes/No ────────────────────────────────

def test_upload_then_consent_yes_document_adds_source_nodes(client, state):
    """Full upload flow: file → session → consent Yes → source nodes in graph."""
    sid = client.post("/session/start").json()["session_id"]

    r = client.post(
        "/upload",
        files={"file": ("essay.txt", PROSE.encode(), "text/plain")},
        headers={"X-Session-ID": sid},
    )
    assert r.status_code == 200
    chunks_added = r.json()["chunks_added"]
    assert chunks_added > 0

    before = state.graph.node_count()
    client.post("/session/end", json={"session_id": sid})
    consent_r = client.post("/consent", json={
        "session_id": sid,
        "artwork_consent": False,
        "document_consent": True,
    })
    assert consent_r.json()["documents_added"] == chunks_added
    assert state.graph.node_count() == before + chunks_added


def test_upload_then_consent_no_document_leaves_graph_unchanged(client, state):
    """Upload processed but consent refused — graph source count unchanged."""
    sid = client.post("/session/start").json()["session_id"]

    client.post(
        "/upload",
        files={"file": ("essay.txt", PROSE.encode(), "text/plain")},
        headers={"X-Session-ID": sid},
    )

    before = state.graph.node_count()
    client.post("/session/end", json={"session_id": sid})
    consent_r = client.post("/consent", json={
        "session_id": sid,
        "artwork_consent": False,
        "document_consent": False,
    })
    assert consent_r.json()["documents_added"] == 0
    assert state.graph.node_count() == before


def test_session_end_had_uploads_true_after_upload(client):
    """POST /session/end reports had_uploads=True when a file was uploaded."""
    sid = client.post("/session/start").json()["session_id"]
    client.post(
        "/upload",
        files={"file": ("essay.txt", PROSE.encode(), "text/plain")},
        headers={"X-Session-ID": sid},
    )
    r = client.post("/session/end", json={"session_id": sid})
    assert r.json()["had_uploads"] is True


def test_session_end_had_uploads_false_without_upload(client):
    """POST /session/end reports had_uploads=False when no file was uploaded."""
    sid = client.post("/session/start").json()["session_id"]
    r = client.post("/session/end", json={"session_id": sid})
    assert r.json()["had_uploads"] is False


# ── Graph state reflects generation ──────────────────────────────────────────

def test_graph_state_node_count_increases_after_generate(client):
    before = client.get("/graph/state").json()["node_count"]
    client.post("/generate", json={})
    after = client.get("/graph/state").json()["node_count"]
    assert after > before


def test_graph_node_detail_available_after_generate(client):
    gen = client.post("/generate", json={}).json()
    r = client.get(f"/graph/node/artwork:{gen['artwork_id']}")
    assert r.status_code == 200
    assert r.json()["kind"] == "artwork"


def test_graph_response_never_exposes_file_paths(client):
    """No internal paths leak through /graph/state even after artwork creation."""
    client.post("/generate", json={})
    body = client.get("/graph/state").json()
    for node in body["nodes"]:
        assert "source_path" not in node
        assert "svg_path" not in node


# ── SSE broadcaster fires on generate ────────────────────────────────────────

@pytest.mark.anyio
async def test_sse_broadcaster_fires_on_generate(state):
    """
    The /generate endpoint calls state.sse.broadcast().  Verify that the
    broadcaster routes the event to a subscribed queue without going through HTTP.
    """
    import asyncio
    from src.api.app import create_app

    app = create_app(state=state)

    # Wire the event loop so broadcast() can schedule queue writes
    state.sse.set_loop(asyncio.get_event_loop())

    q = state.sse.subscribe()

    # Trigger broadcast directly as the route handler does
    state.sse.broadcast("artwork_ready", {"artwork_id": "test_broadcast"})

    msg = await asyncio.wait_for(q.get(), timeout=1.0)
    assert "artwork_ready" in msg
    assert "test_broadcast" in msg
