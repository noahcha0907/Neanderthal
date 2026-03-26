"""
Single generation cycle — PRD 2.2 / PRD 2.4

Encapsulates the full pipeline for one artwork creation event:
  select voters → add talent cluster → vote → render SVG →
  build justification trace → save trace → ingest artwork → notify

In default (public) mode, voters are sampled from graph SourceNodes by
connectivity weight.  In private session mode (PRD 2.4), user-uploaded
chunks are added to the pool at an elevated UPLOAD_WEIGHT_BIAS weight so
they dominate parameter selection; graph ingestion is skipped so the
artwork is held in session state until consent is given (PRD 2.5).

Separated from the timer so the pipeline can be called directly in tests,
CLI scripts, and the FastAPI layer (PRD 2.7) without spinning up a thread.

Public API:
  select_humanities_voters(graph, n, rng)              → list[tuple[str, float]]
  select_private_voters(graph, upload_chunk_ids, n, rng) → list[tuple[str, float]]
  run_generation_cycle(graph, chunks, trace_store, output_dir,
                       on_artwork_ready, rng,
                       upload_chunk_ids, fixed_n, ingest) → dict | None
"""
import logging
import random
from pathlib import Path
from typing import Callable

from src.config.settings import (
    MAX_PARAMETERS,
    MIN_PARAMETERS,
    TALENT_DIR,
    UPLOAD_WEIGHT_BIAS,
)
from src.controllers.generate import save_artwork
from src.controllers.talent_ingest import ingest_artwork, select_talent_voters
from src.helpers.text_utils import extract_excerpt
from src.models.corpus import CorpusChunk
from src.models.graph import SemanticGraph
from src.models.trace import build_trace
from src.models.trace_store import TraceStore
from src.models.voting import vote_on_parameters

logger = logging.getLogger(__name__)


def select_humanities_voters(
    graph: SemanticGraph,
    n: int,
    rng: random.Random,
) -> list[tuple[str, float]]:
    """
    Weighted-random sample of n SourceNodes from the graph.

    Selection probability is proportional to total similarity edge weight —
    well-connected nodes (familiar combinations) are preferred, but every node
    has a non-zero chance via a small floor weight so the robot occasionally
    samples unfamiliar territory.

    n is clamped to the number of available source nodes.
    Returns [] if the graph contains no SourceNodes.
    Each returned voter carries weight 1.0 — normalisation happens inside
    vote_on_parameters.
    """
    sources = graph.source_node_weights()
    if not sources:
        return []

    n = min(n, len(sources))

    # Floor weight ensures isolated nodes can be sampled
    ids = [cid for cid, _ in sources]
    weights = [max(w, 0.01) for _, w in sources]

    # Weighted sampling without replacement
    selected: list[str] = []
    while len(selected) < n:
        total = sum(weights)
        threshold = rng.uniform(0.0, total)
        cumulative = 0.0
        for i, (chunk_id, w) in enumerate(zip(ids, weights)):
            cumulative += w
            if cumulative >= threshold:
                selected.append(chunk_id)
                ids.pop(i)
                weights.pop(i)
                break

    return [(cid, 1.0) for cid in selected]


def select_private_voters(
    graph: SemanticGraph,
    upload_chunk_ids: list[str],
    n: int,
    rng: random.Random,
) -> list[tuple[str, float]]:
    """
    Weighted-random sample of n voters from a biased pool — PRD 2.4.

    The pool combines:
    - Graph SourceNodes, weighted by connectivity (floor 0.01 for isolated nodes)
    - Uploaded chunks, weighted at UPLOAD_WEIGHT_BIAS — elevated above typical
      graph connectivity scores so user-provided content dominates selection

    Uploaded chunk_ids that already exist as graph SourceNodes are not
    duplicated — they are treated as graph nodes at their connectivity weight.
    Uploaded chunk_ids not in the graph participate in voting via their
    hash-derived proposals without needing to be graph members.

    n is clamped to the total pool size. Returns [] if the pool is empty.
    Each returned voter carries weight 1.0 — normalisation happens inside
    vote_on_parameters.
    """
    sources = graph.source_node_weights()
    ids: list[str] = [cid for cid, _ in sources]
    weights: list[float] = [max(w, 0.01) for _, w in sources]

    # Add uploads that are not already in the graph
    graph_id_set = set(ids)
    for cid in upload_chunk_ids:
        if cid not in graph_id_set:
            ids.append(cid)
            weights.append(UPLOAD_WEIGHT_BIAS)

    if not ids:
        return []

    n = min(n, len(ids))

    # Weighted sampling without replacement
    selected: list[str] = []
    while len(selected) < n:
        total = sum(weights)
        threshold = rng.uniform(0.0, total)
        cumulative = 0.0
        for i, (chunk_id, w) in enumerate(zip(ids, weights)):
            cumulative += w
            if cumulative >= threshold:
                selected.append(chunk_id)
                ids.pop(i)
                weights.pop(i)
                break

    return [(cid, 1.0) for cid in selected]


def run_generation_cycle(
    graph: SemanticGraph,
    chunks: dict[str, CorpusChunk],
    trace_store: TraceStore,
    output_dir: Path = TALENT_DIR,
    on_artwork_ready: Callable[[dict], None] | None = None,
    on_thinking_event: Callable[[str, dict], None] | None = None,
    rng: random.Random | None = None,
    upload_chunk_ids: list[str] | None = None,
    fixed_n: int | None = None,
    ingest: bool = True,
) -> dict | None:
    """
    Execute one complete artwork generation cycle.

    Steps:
      1. Select voters: default mode samples from graph SourceNodes; private
         mode (upload_chunk_ids set) uses the biased pool from
         select_private_voters so user uploads dominate selection.
      2. Build the talent cluster (all artworks at ≥90% similarity) as the
         n+1 voter at 1.5× weight.
      3. Vote on all art parameters.
      4. Render and save the SVG.
      5. Build and persist the justification trace.
      6. Ingest the new artwork into the graph and save (skipped if ingest=False).
      7. Call on_artwork_ready if provided.

    upload_chunk_ids: chunk IDs from the session's private uploads.  When set,
                      the voter pool is biased toward these chunks (PRD 2.4).
                      Need not be present in the graph.
    fixed_n:          Override the random voter count with a fixed value.
                      Used when the user has set "consider N parameters" (PRD 2.4).
    ingest:           If False, skip graph ingestion and save (PRD 2.4 private
                      sessions hold artwork in session state until consent).

    chunks: pre-resolved {chunk_id: CorpusChunk} dict for trace attribution.
            Missing chunk_ids fall back to 'Unknown' in the trace (no crash).

    Returns a result dict on success; None if the voter pool is empty.
    Raises on unexpected errors so the caller (timer) can log and continue.
    """
    if rng is None:
        rng = random.Random()

    # ── 1. Voter selection ────────────────────────────────────────────────────

    n = fixed_n if fixed_n is not None else rng.randint(MIN_PARAMETERS, MAX_PARAMETERS)

    if upload_chunk_ids:
        humanities_voters = select_private_voters(graph, upload_chunk_ids, n, rng)
    else:
        humanities_voters = select_humanities_voters(graph, n, rng)

    if not humanities_voters:
        logger.warning("No voters available — skipping generation cycle")
        return None

    # ── B2.2 — Emit corpus passages consulted by this generation ─────────────
    # Surfaces existing voter data as SSE events for the Consciousness Terminal.

    if on_thinking_event is not None:
        on_thinking_event("generation_reasoning", {
            "step": "voter_selection",
            "description": (
                f"Drawing from {len(humanities_voters)} "
                f"source{'s' if len(humanities_voters) != 1 else ''} in the corpus"
            ),
        })
        total_w = sum(w for _, w in humanities_voters)
        for chunk_id, weight in humanities_voters:
            chunk = chunks.get(chunk_id)
            if chunk:
                on_thinking_event("thinking_passage", {
                    "node_id": chunk_id,
                    "source_title": chunk.title,
                    "author": chunk.author,
                    "passage": extract_excerpt(chunk.text, n_sentences=4),
                    "weight": round(weight / total_w, 4),
                })

    # ── 2. Talent cluster (n+1) ───────────────────────────────────────────────

    chunk_ids = [cid for cid, _ in humanities_voters]
    talent_voters = select_talent_voters(chunk_ids, graph)
    all_voters = humanities_voters + talent_voters

    # ── 3. Vote ───────────────────────────────────────────────────────────────

    params = vote_on_parameters(all_voters)

    # ── 4. Render ─────────────────────────────────────────────────────────────

    svg_path = save_artwork(params, output_dir=output_dir)

    # ── 5. Justification trace ────────────────────────────────────────────────

    trace = build_trace(params.artwork_id, humanities_voters, params, chunks)
    trace_store.save(trace)
    trace_store.commit()

    # ── B2.2 — Emit parameter decisions for the Consciousness Terminal ────────
    # Reuses the trace entries already computed — no new data derived here.

    if on_thinking_event is not None:
        on_thinking_event("generation_reasoning", {
            "step": "parameters_resolved",
            "description": (
                f"Resolved {len(trace.entries)} parameter"
                f"{'s' if len(trace.entries) != 1 else ''} "
                f"across {len(humanities_voters)} voter"
                f"{'s' if len(humanities_voters) != 1 else ''}"
            ),
        })
        for entry in trace.entries:
            reason = f'{entry.title} ({entry.author})'
            if entry.excerpt:
                reason += f' — "{entry.excerpt}"'
            on_thinking_event("parameter_decided", {
                "parameter": entry.label,
                "value": entry.value,
                "reason": reason,
            })

    # ── 6. Ingest ─────────────────────────────────────────────────────────────
    # Skipped in private sessions — artwork is held in session state until
    # the user consents at session end (PRD 2.4 / PRD 2.5).

    if ingest:
        ingest_artwork(params, svg_path, humanities_voters, graph)
        if graph._path is not None:
            graph.save()

    # ── 7. Emit ───────────────────────────────────────────────────────────────

    result = {
        "artwork_id": params.artwork_id,
        "svg_path": str(svg_path),
        "trace_text": trace.to_text(),
        "voter_count": len(humanities_voters),
        # voter_ids retained so the consent handler (PRD 2.5) can link artwork
        # nodes to the source chunks that influenced them at ingestion time.
        "voter_ids": [cid for cid, _ in humanities_voters],
    }

    if on_artwork_ready is not None:
        on_artwork_ready(result)

    logger.info(
        "Generation cycle complete: artwork=%s, voters=%d (+%d talent)",
        params.artwork_id, len(humanities_voters), len(talent_voters),
    )
    return result
