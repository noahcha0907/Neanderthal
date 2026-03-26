"""
REST API route handlers — PRD 2.7

All ten endpoints defined in the PRD:

  POST   /session/start      Create a new anonymous session
  POST   /session/end        Return session summary for consent UI
  GET    /graph/state        Full graph snapshot (nodes + edges)
  GET    /graph/node/{id}    Single node detail
  POST   /generate           Trigger one generation cycle
  GET    /portfolio          All public artworks, chronological
  GET    /portfolio/{id}     One artwork with SVG content + trace
  POST   /upload             Add a document to a private session
  POST   /consent            Submit consent decisions + end session
  GET    /stream             Server-sent events for live updates

Design rules:
  - No raw file-system paths in responses
  - All POST bodies validated via Pydantic models
  - 404 for missing resources, 503 for empty generation pool,
    400 for bad requests, 422 handled automatically by FastAPI
"""
import asyncio
import logging
import random
from pathlib import Path
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.api.state import AppState
from src.config.settings import ROOT_DIR, TALENT_DIR
from src.controllers.consent import process_consent
from src.controllers.generation_cycle import run_generation_cycle
from src.controllers.upload_pipeline import UploadError, process_upload
from src.models.corpus import CorpusChunk
from src.models.graph import SemanticGraph

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Dependency ────────────────────────────────────────────────────────────────

def _state(request: Request) -> AppState:
    """Extract shared AppState from the FastAPI application state."""
    return request.app.state.app_state


# ── Request / response models ─────────────────────────────────────────────────

class SessionEndRequest(BaseModel):
    session_id: str


class SessionParamsRequest(BaseModel):
    session_id: str
    parameter_count: int | None = None   # None → "Random" (robot picks); 1–5 → fixed


class GenerateRequest(BaseModel):
    session_id: str | None = None


class ConsentRequest(BaseModel):
    session_id: str
    artwork_consent: bool
    document_consent: bool


# ── Session ───────────────────────────────────────────────────────────────────

@router.post("/session/start")
def session_start(request: Request) -> dict:
    """Create a new anonymous session and return its ID."""
    state = _state(request)
    session = state.session_manager.create()
    return {
        "session_id": session.session_id,
        "started_at": session.started_at.isoformat(),
    }


@router.post("/session/params")
def session_params(body: SessionParamsRequest, request: Request) -> dict:
    """
    Set the parameter count mode for an active session.

    parameter_count=None  → robot picks randomly (default).
    parameter_count=1–5   → fixed count for every generation cycle.
    Returns 400 for invalid values, 404 for unknown session.
    """
    state = _state(request)
    try:
        if body.parameter_count is None:
            state.session_manager.set_parameter_mode(body.session_id, "default")
        else:
            state.session_manager.set_parameter_mode(
                body.session_id, "user_directed", body.parameter_count
            )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"session_id": body.session_id, "parameter_count": body.parameter_count}


@router.post("/session/end")
def session_end(body: SessionEndRequest, request: Request) -> dict:
    """
    Return a summary of session state so the client can show consent prompts.

    Does NOT destroy the session — call POST /consent to finalize.
    Returns 404 if the session is not active.
    """
    state = _state(request)
    session = state.session_manager.get(body.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "session_id": session.session_id,
        "artwork_count": len(session.artworks),
        "had_uploads": bool(session.uploads),
    }


# ── Graph ─────────────────────────────────────────────────────────────────────

@router.get("/graph/state")
def graph_state(request: Request, top_k: int = 5) -> dict:
    """
    Return a snapshot of the semantic graph.

    top_k: maximum similarity edges returned per source node (default 5).
    Set to 0 to disable filtering and return all edges — browser will struggle
    above a few thousand edges, so only use 0 for offline/CLI consumers.

    Nodes include kind and public metadata; internal file paths are omitted.
    """
    graph: SemanticGraph = _state(request).graph
    raw_nodes, raw_edges = graph.all_nodes_and_edges(
        top_k_similarity=top_k if top_k > 0 else None,
    )

    # Strip internal file paths before returning
    nodes = [_sanitize_node(n) for n in raw_nodes]

    return {
        "node_count": graph.node_count(),
        "edge_count": graph.edge_count(),
        "nodes": nodes,
        "edges": raw_edges,
    }


@router.get("/graph/node/{node_id:path}")
def graph_node(node_id: str, request: Request) -> dict:
    """
    Return detail for a single graph node.

    Returns 404 if the node does not exist.
    """
    graph: SemanticGraph = _state(request).graph
    data = graph.node_data(node_id)
    if data is None:
        raise HTTPException(status_code=404, detail=f"Node '{node_id}' not found")
    return {"id": node_id, **_sanitize_node(data)}


# ── Generation ────────────────────────────────────────────────────────────────

@router.post("/generate")
def generate(body: GenerateRequest, request: Request) -> dict:
    """
    Manually trigger one artwork generation cycle.

    If session_id is provided and the session has uploads, the private
    voter pool is used.  Returns 503 if the voter pool is empty.
    """
    state = _state(request)
    graph = state.graph

    upload_chunk_ids: list[str] | None = None
    fixed_n: int | None = None

    if body.session_id is not None:
        session = state.session_manager.get(body.session_id)
        if session is not None and session.uploads:
            upload_chunk_ids = [c.chunk_id for c in session.uploads]
        if session is not None and session.parameter_count is not None:
            fixed_n = session.parameter_count

    # Notify clients that a generation cycle is starting so they can begin
    # their "thinking" animation before the result arrives.
    state.sse.broadcast("generation_started", {})

    # Build chunk lookup from graph source nodes so the justification trace
    # carries real title/author/excerpt instead of 'Unknown'.
    chunks = _chunks_from_graph(graph)

    # Private sessions hold artwork until consent (PRD 2.4/2.5); public
    # mode ingests immediately so the artwork node appears in the graph.
    is_private = body.session_id is not None

    def _thinking(event_type: str, payload: dict) -> None:
        state.sse.broadcast(event_type, payload)

    result = run_generation_cycle(
        graph=graph,
        chunks=chunks,
        trace_store=state.trace_store,
        output_dir=TALENT_DIR,
        rng=random.Random(),
        on_thinking_event=_thinking,
        upload_chunk_ids=upload_chunk_ids,
        fixed_n=fixed_n,
        ingest=not is_private,
    )

    if result is None:
        raise HTTPException(
            status_code=503,
            detail="Voter pool is empty — add corpus chunks before generating",
        )

    # Track artwork in session so consent UI can show correct count.
    if body.session_id is not None:
        state.session_manager.record_artwork(body.session_id, result)

    # Read SVG content now so private-session clients can render the artwork
    # panel immediately without a /portfolio lookup (artwork not in graph yet).
    # Strip the XML declaration — it is only valid for standalone XML files and
    # causes HTML parsers to misrender inline SVG.
    svg_raw = Path(result["svg_path"]).read_text(encoding="utf-8")
    svg_content = svg_raw.replace('<?xml version="1.0" encoding="utf-8"?>', "").strip()

    # Broadcast voter_ids so the frontend can animate the specific nodes consulted.
    state.sse.broadcast("artwork_ready", {
        "artwork_id": result["artwork_id"],
        "voter_count": result["voter_count"],
        "voter_ids": result["voter_ids"],
        "svg_content": svg_content,
        "trace_text": result["trace_text"],
    })

    # Public mode: artwork node already in graph — notify clients to refresh.
    if not is_private:
        state.sse.broadcast("graph_updated", {})

    # Return result without internal file path
    return {
        "artwork_id": result["artwork_id"],
        "trace_text": result["trace_text"],
        "voter_count": result["voter_count"],
        "voter_ids": result["voter_ids"],
    }


# ── Portfolio ─────────────────────────────────────────────────────────────────

@router.get("/portfolio")
def portfolio(request: Request) -> list:
    """Return all public artworks in chronological order."""
    graph: SemanticGraph = _state(request).graph
    artworks = graph.all_artwork_nodes()
    return [
        {
            "artwork_id": a["artwork_id"],
            "created_at": a.get("created_at", ""),
        }
        for a in artworks
    ]


@router.get("/portfolio/{artwork_id}")
def portfolio_item(artwork_id: str, request: Request) -> dict:
    """
    Return one artwork with its SVG content and justification trace.

    Returns 404 if the artwork is not in the graph or its SVG file is missing.
    """
    state = _state(request)
    node = state.graph.node_data(f"artwork:{artwork_id}")
    if node is None:
        raise HTTPException(status_code=404, detail=f"Artwork '{artwork_id}' not found")

    svg_path = Path(node.get("svg_path", ""))
    # Relative paths were stored by older server instances; resolve against
    # the project root so they remain valid regardless of working directory.
    if not svg_path.is_absolute():
        svg_path = ROOT_DIR / svg_path
    if not svg_path.exists():
        raise HTTPException(status_code=404, detail="SVG file not found")

    svg_raw = svg_path.read_text(encoding="utf-8")
    # Strip the XML declaration — it is only valid for standalone XML files
    # and causes HTML parsers to misrender inline SVG.
    svg_content = svg_raw.replace('<?xml version="1.0" encoding="utf-8"?>', "").strip()
    trace_text = state.trace_store.get(artwork_id) or ""
    voter_ids = state.graph.artwork_source_nodes(artwork_id)

    return {
        "artwork_id": artwork_id,
        "svg_content": svg_content,
        "trace_text": trace_text,
        "created_at": node.get("created_at", ""),
        "voter_ids": voter_ids,
    }


# ── Upload ────────────────────────────────────────────────────────────────────

@router.post("/upload")
async def upload(
    request: Request,
    file: UploadFile = File(...),
    x_session_id: str = Header(..., alias="X-Session-ID"),
) -> dict:
    """
    Validate and chunk an uploaded document, then add it to the session.

    Expects multipart/form-data with a 'file' field and an X-Session-ID header.
    Returns 400 for validation errors, 404 for unknown session.
    """
    state = _state(request)
    session = state.session_manager.get(x_session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    content = await file.read()
    filename = file.filename or "upload.txt"

    try:
        chunks = process_upload(filename, content)
    except UploadError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    for chunk in chunks:
        state.session_manager.add_upload(x_session_id, chunk)

    logger.info(
        "Upload complete: session=%s, file=%s, chunks=%d",
        x_session_id, filename, len(chunks),
    )
    return {"chunks_added": len(chunks), "session_id": x_session_id}


# ── Consent ───────────────────────────────────────────────────────────────────

@router.post("/consent")
def consent(body: ConsentRequest, request: Request) -> dict:
    """
    Process consent decisions and end the session.

    Pops the session from the active registry, then ingests consented data
    into the shared graph/corpus.  Returns 404 if the session is not found.
    """
    state = _state(request)
    session = state.session_manager.end(body.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    result = process_consent(
        session=session,
        artwork_consent=body.artwork_consent,
        document_consent=body.document_consent,
        graph=state.graph,
    )

    # Notify connected clients so their graph view refreshes to show new nodes.
    if result.artworks_ingested > 0 or result.documents_added > 0:
        state.sse.broadcast("graph_updated", {})

    return {
        "artworks_ingested": result.artworks_ingested,
        "documents_added": result.documents_added,
    }


# ── SSE stream ────────────────────────────────────────────────────────────────

@router.get("/stream")
async def stream(request: Request) -> StreamingResponse:
    """
    Server-sent events stream for live graph and artwork updates.

    Emits 'artwork_ready' events whenever a generation cycle completes.
    Clients must keep the connection open to receive events.
    """
    state = _state(request)
    queue = state.sse.subscribe()

    async def event_generator() -> AsyncGenerator[str, None]:
        # Send an initial keep-alive comment so the client knows we're connected
        yield ": connected\n\n"
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=1.0)
                    yield message
                except asyncio.TimeoutError:
                    # Keep-alive ping; also lets the loop re-check is_disconnected
                    yield ": ping\n\n"
        finally:
            state.sse.unsubscribe(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ── Private helpers ───────────────────────────────────────────────────────────

def _sanitize_node(attrs: dict) -> dict:
    """Remove internal file-system paths from a node attribute dict."""
    return {k: v for k, v in attrs.items() if k != "svg_path" and k != "source_path"}


def _chunks_from_graph(graph: SemanticGraph) -> dict[str, CorpusChunk]:
    """
    Build a chunk_id → CorpusChunk lookup from source nodes already in the graph.

    The graph stores title, author, text, doc_type, year, and chunk_index on
    every SourceNode at ingest time. Reconstructing CorpusChunks from this data
    lets the /generate route produce fully attributed justification traces without
    a separate ChunkStore query.

    Uses source_node_weights() + node_data() so only source nodes are visited
    and no edge data is loaded — efficient for a 7K+ node graph.

    Fields not stored in the graph (source_path, chunk_strategy) are filled with
    empty strings — they are not used by build_trace.
    """
    chunks: dict[str, CorpusChunk] = {}
    for chunk_id, _ in graph.source_node_weights():
        data = graph.node_data(chunk_id)
        if data is None:
            continue
        chunks[chunk_id] = CorpusChunk(
            chunk_id=chunk_id,
            source_path="",
            title=data.get("title", ""),
            author=data.get("author", ""),
            doc_type=data.get("doc_type", ""),
            year=data.get("year"),
            chunk_index=data.get("chunk_index", 0),
            text=data.get("text", ""),
            chunk_strategy="",
        )
    return chunks
