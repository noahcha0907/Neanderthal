"""
Unit tests for the FastAPI REST layer — PRD 2.7

Uses TestClient with a fully in-memory AppState so no database or disk
access is required.  All 10 endpoints are covered.
"""
import io
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.api.app import create_app
from src.api.state import AppState, SSEBroadcaster
from src.controllers.session_manager import SessionManager
from src.models.corpus import CorpusChunk
from src.models.graph import SemanticGraph


# ── Stubs ─────────────────────────────────────────────────────────────────────

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


# ── Fixtures ──────────────────────────────────────────────────────────────────

def make_chunk(chunk_id: str) -> CorpusChunk:
    return CorpusChunk(
        chunk_id=chunk_id,
        source_path="data/test.txt",
        title="Test Work",
        author="Author",
        doc_type="literary",
        year=2024,
        chunk_index=0,
        text="Sample text for testing purposes.",
        chunk_strategy="paragraph",
    )


def populated_graph(n: int = 3) -> SemanticGraph:
    g = SemanticGraph(path=None)
    for i in range(n):
        g.add_source_node(make_chunk(f"chunk_{i}"))
    return g


@pytest.fixture
def state():
    return AppState(
        graph=populated_graph(3),
        session_manager=SessionManager(),
        trace_store=_StubTraceStore(),
        sse=SSEBroadcaster(),
    )


@pytest.fixture
def client(state):
    app = create_app(state=state)
    with TestClient(app) as c:
        yield c


# ── POST /session/start ───────────────────────────────────────────────────────

def test_session_start_returns_200(client):
    r = client.post("/session/start")
    assert r.status_code == 200


def test_session_start_returns_session_id(client):
    r = client.post("/session/start")
    assert "session_id" in r.json()


def test_session_start_returns_started_at(client):
    r = client.post("/session/start")
    assert "started_at" in r.json()


def test_session_start_creates_active_session(client, state):
    r = client.post("/session/start")
    sid = r.json()["session_id"]
    assert state.session_manager.get(sid) is not None


def test_session_start_each_call_unique(client):
    a = client.post("/session/start").json()["session_id"]
    b = client.post("/session/start").json()["session_id"]
    assert a != b


# ── POST /session/end ─────────────────────────────────────────────────────────

def test_session_end_returns_200(client):
    sid = client.post("/session/start").json()["session_id"]
    r = client.post("/session/end", json={"session_id": sid})
    assert r.status_code == 200


def test_session_end_returns_summary(client):
    sid = client.post("/session/start").json()["session_id"]
    r = client.post("/session/end", json={"session_id": sid})
    body = r.json()
    assert body["session_id"] == sid
    assert "artwork_count" in body
    assert "had_uploads" in body


def test_session_end_does_not_destroy_session(client, state):
    sid = client.post("/session/start").json()["session_id"]
    client.post("/session/end", json={"session_id": sid})
    # Session should still be active (consent not submitted yet)
    assert state.session_manager.get(sid) is not None


def test_session_end_unknown_session_returns_404(client):
    r = client.post("/session/end", json={"session_id": "nonexistent"})
    assert r.status_code == 404


# ── GET /graph/state ──────────────────────────────────────────────────────────

def test_graph_state_returns_200(client):
    assert client.get("/graph/state").status_code == 200


def test_graph_state_has_counts(client):
    body = client.get("/graph/state").json()
    assert "node_count" in body
    assert "edge_count" in body


def test_graph_state_has_nodes_list(client):
    body = client.get("/graph/state").json()
    assert isinstance(body["nodes"], list)


def test_graph_state_has_edges_list(client):
    body = client.get("/graph/state").json()
    assert isinstance(body["edges"], list)


def test_graph_state_no_file_paths_in_nodes(client):
    body = client.get("/graph/state").json()
    for node in body["nodes"]:
        assert "source_path" not in node
        assert "svg_path" not in node


def test_graph_state_node_count_matches_list(client, state):
    body = client.get("/graph/state").json()
    assert body["node_count"] == len(body["nodes"])


# ── GET /graph/node/{id} ──────────────────────────────────────────────────────

def test_graph_node_returns_200_for_existing(client):
    r = client.get("/graph/node/chunk_0")
    assert r.status_code == 200


def test_graph_node_returns_node_kind(client):
    body = client.get("/graph/node/chunk_0").json()
    assert body["kind"] == "source"


def test_graph_node_no_file_paths(client):
    body = client.get("/graph/node/chunk_0").json()
    assert "source_path" not in body


def test_graph_node_returns_404_for_missing(client):
    r = client.get("/graph/node/does_not_exist")
    assert r.status_code == 404


# ── POST /generate ────────────────────────────────────────────────────────────

def test_generate_returns_200_with_populated_graph(client):
    r = client.post("/generate", json={})
    assert r.status_code == 200


def test_generate_returns_artwork_id(client):
    r = client.post("/generate", json={})
    assert "artwork_id" in r.json()


def test_generate_returns_voter_count(client):
    r = client.post("/generate", json={})
    assert "voter_count" in r.json()


def test_generate_returns_trace_text(client):
    r = client.post("/generate", json={})
    assert "trace_text" in r.json()


def test_generate_no_svg_path_in_response(client):
    r = client.post("/generate", json={})
    assert "svg_path" not in r.json()


def test_generate_empty_graph_returns_503():
    empty_state = AppState(
        graph=SemanticGraph(path=None),
        session_manager=SessionManager(),
        trace_store=_StubTraceStore(),
        sse=SSEBroadcaster(),
    )
    app = create_app(state=empty_state)
    with TestClient(app) as c:
        r = c.post("/generate", json={})
    assert r.status_code == 503


# ── GET /portfolio ─────────────────────────────────────────────────────────────

def test_portfolio_returns_200(client):
    assert client.get("/portfolio").status_code == 200


def test_portfolio_returns_list(client):
    body = client.get("/portfolio").json()
    assert isinstance(body, list)


def test_portfolio_empty_initially(client):
    body = client.get("/portfolio").json()
    assert body == []


def test_portfolio_lists_artwork_after_generate(client, tmp_path, state):
    # Run a generation cycle so an artwork node appears in the graph
    client.post("/generate", json={})
    artworks = client.get("/portfolio").json()
    assert len(artworks) >= 1


def test_portfolio_item_has_artwork_id(client):
    client.post("/generate", json={})
    artworks = client.get("/portfolio").json()
    assert "artwork_id" in artworks[0]


def test_portfolio_item_has_created_at(client):
    client.post("/generate", json={})
    artworks = client.get("/portfolio").json()
    assert "created_at" in artworks[0]


# ── GET /portfolio/{id} ───────────────────────────────────────────────────────

def test_portfolio_by_id_returns_svg_content(client, state, tmp_path):
    # Manually add an artwork node pointing at a real SVG file
    svg = tmp_path / "test.svg"
    svg.write_text("<svg/>", encoding="utf-8")
    state.graph.add_artwork_node("art_test", str(svg))

    r = client.get("/portfolio/art_test")
    assert r.status_code == 200
    assert r.json()["svg_content"] == "<svg/>"


def test_portfolio_by_id_returns_artwork_id(client, state, tmp_path):
    svg = tmp_path / "test2.svg"
    svg.write_text("<svg/>", encoding="utf-8")
    state.graph.add_artwork_node("art_test2", str(svg))

    body = client.get("/portfolio/art_test2").json()
    assert body["artwork_id"] == "art_test2"


def test_portfolio_by_id_unknown_returns_404(client):
    r = client.get("/portfolio/does_not_exist")
    assert r.status_code == 404


def test_portfolio_by_id_no_file_path_in_response(client, state, tmp_path):
    svg = tmp_path / "test3.svg"
    svg.write_text("<svg/>", encoding="utf-8")
    state.graph.add_artwork_node("art_test3", str(svg))

    body = client.get("/portfolio/art_test3").json()
    assert "svg_path" not in body


# ── POST /upload ───────────────────────────────────────────────────────────────

PROSE = (
    "The weight of history presses down upon each generation in turn. "
    "We inherit not only the achievements of those who came before, but also "
    "their failures — the long chain of cause and effect that stretches back "
    "through centuries of human striving and suffering.\n\n"
    "What we call progress is often nothing more than the reordering of old "
    "mistakes into new configurations that feel, for a brief time, like solutions. "
    "The mind finds comfort in novelty even when the underlying structure endures."
)


def test_upload_returns_200(client):
    sid = client.post("/session/start").json()["session_id"]
    r = client.post(
        "/upload",
        files={"file": ("essay.txt", PROSE.encode(), "text/plain")},
        headers={"X-Session-ID": sid},
    )
    assert r.status_code == 200


def test_upload_returns_chunks_added(client):
    sid = client.post("/session/start").json()["session_id"]
    r = client.post(
        "/upload",
        files={"file": ("essay.txt", PROSE.encode(), "text/plain")},
        headers={"X-Session-ID": sid},
    )
    assert r.json()["chunks_added"] > 0


def test_upload_adds_to_session(client, state):
    sid = client.post("/session/start").json()["session_id"]
    client.post(
        "/upload",
        files={"file": ("essay.txt", PROSE.encode(), "text/plain")},
        headers={"X-Session-ID": sid},
    )
    session = state.session_manager.get(sid)
    assert len(session.uploads) > 0


def test_upload_unknown_session_returns_404(client):
    r = client.post(
        "/upload",
        files={"file": ("essay.txt", PROSE.encode(), "text/plain")},
        headers={"X-Session-ID": "bad-session-id"},
    )
    assert r.status_code == 404


def test_upload_invalid_extension_returns_400(client):
    sid = client.post("/session/start").json()["session_id"]
    r = client.post(
        "/upload",
        files={"file": ("payload.exe", b"content", "application/octet-stream")},
        headers={"X-Session-ID": sid},
    )
    assert r.status_code == 400


def test_upload_empty_file_returns_400(client):
    sid = client.post("/session/start").json()["session_id"]
    r = client.post(
        "/upload",
        files={"file": ("blank.txt", b"", "text/plain")},
        headers={"X-Session-ID": sid},
    )
    assert r.status_code == 400


# ── POST /consent ──────────────────────────────────────────────────────────────

def test_consent_returns_200(client):
    sid = client.post("/session/start").json()["session_id"]
    r = client.post("/consent", json={
        "session_id": sid,
        "artwork_consent": False,
        "document_consent": False,
    })
    assert r.status_code == 200


def test_consent_returns_counts(client):
    sid = client.post("/session/start").json()["session_id"]
    r = client.post("/consent", json={
        "session_id": sid,
        "artwork_consent": False,
        "document_consent": False,
    })
    body = r.json()
    assert "artworks_ingested" in body
    assert "documents_added" in body


def test_consent_ends_session(client, state):
    sid = client.post("/session/start").json()["session_id"]
    client.post("/consent", json={
        "session_id": sid,
        "artwork_consent": False,
        "document_consent": False,
    })
    assert state.session_manager.get(sid) is None


def test_consent_unknown_session_returns_404(client):
    r = client.post("/consent", json={
        "session_id": "ghost-session",
        "artwork_consent": False,
        "document_consent": False,
    })
    assert r.status_code == 404


def test_consent_artwork_yes_ingests_artworks(client, state):
    sid = client.post("/session/start").json()["session_id"]
    # Record a fake artwork in the session
    state.session_manager.record_artwork(sid, {
        "artwork_id": "art_consent_test",
        "svg_path": "data/talent/art.svg",
        "trace_text": "",
        "voter_count": 1,
        "voter_ids": ["chunk_0"],
    })
    r = client.post("/consent", json={
        "session_id": sid,
        "artwork_consent": True,
        "document_consent": False,
    })
    assert r.json()["artworks_ingested"] == 1


def test_consent_document_yes_adds_uploads(client, state):
    sid = client.post("/session/start").json()["session_id"]
    state.session_manager.add_upload(sid, make_chunk("upload_x"))
    r = client.post("/consent", json={
        "session_id": sid,
        "artwork_consent": False,
        "document_consent": True,
    })
    assert r.json()["documents_added"] == 1


# ── GET /stream ────────────────────────────────────────────────────────────────
# TestClient cannot drain an infinite SSE stream; HTTP-level streaming is
# covered by the integration test suite (PRD 2.8).  Unit tests verify:
#   1. The route is registered and returns 405 for non-GET methods (not 404)
#   2. The SSEBroadcaster delivers events to async queues correctly

def test_stream_route_is_registered():
    """GET /stream route exists in the router."""
    from src.api.routes import router
    paths = [getattr(r, "path", "") for r in router.routes]
    assert "/stream" in paths


def test_stream_route_does_not_accept_post(client):
    """POST /stream returns 405 (method not allowed), confirming the route exists."""
    r = client.post("/stream")
    assert r.status_code == 405


@pytest.mark.anyio
async def test_sse_broadcaster_delivers_event():
    """SSEBroadcaster routes an event to a subscribed async queue — no HTTP needed."""
    import asyncio
    from src.api.state import SSEBroadcaster

    sse = SSEBroadcaster()
    sse.set_loop(asyncio.get_event_loop())

    q = sse.subscribe()
    sse.broadcast("artwork_ready", {"artwork_id": "test_art"})

    msg = await asyncio.wait_for(q.get(), timeout=1.0)
    assert '"type": "artwork_ready"' in msg
    assert '"artwork_id": "test_art"' in msg


@pytest.mark.anyio
async def test_sse_broadcaster_unsubscribe_stops_delivery():
    """After unsubscribing, no further events are routed to the queue."""
    import asyncio
    from src.api.state import SSEBroadcaster

    sse = SSEBroadcaster()
    sse.set_loop(asyncio.get_event_loop())

    q = sse.subscribe()
    sse.unsubscribe(q)
    sse.broadcast("artwork_ready", {"artwork_id": "ghost"})

    assert q.empty()
