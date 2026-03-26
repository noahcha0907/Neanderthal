"""
Parameter voting engine — PRD 1.5

Converts a weighted list of source nodes (from SemanticGraph.source_neighbors)
into a fully specified ArtParameters by having each node "vote" on every
parameter.

Each source node derives its proposals deterministically from its chunk_id,
so the same node always votes the same way. Combining different nodes with
different weights produces emergent variation without randomness.

Discrete fields (colors, shape type, stroke width) use weighted plurality:
the option with the highest total weight wins.

Continuous fields (x, y, size, opacity, shape count) use weighted average:
proposals are summed proportionally by weight.

Public API:
  vote_on_parameters(voters) → ArtParameters
    voters: list[tuple[str, float]]  — (chunk_id, similarity_weight)
"""
import hashlib
import logging
from typing import Any, Sequence

from src.config.settings import (
    COLOR_PALETTE,
    MAX_SHAPES,
    MIN_SHAPES,
    SHAPE_TYPES,
    STROKE_WIDTHS,
)
from src.models.art_params import ArtParameters, ShapeParams

logger = logging.getLogger(__name__)

# Ordered option lists derived from settings — order must be stable because
# hash-based choice uses index arithmetic.  Never sort these at runtime.
_COLOR_VALUES: list[str] = list(COLOR_PALETTE.values())
_STROKE_VALUES: list[int] = sorted(STROKE_WIDTHS.values())   # [1, 3, 6]


# ── Deterministic hash helpers ────────────────────────────────────────────────

def _hash_float(chunk_id: str, key: str) -> float:
    """
    Deterministic float in [0.0, 1.0) derived from chunk_id and a named key.

    Uses the first 8 hex digits of a SHA-256 digest to produce a 32-bit
    integer, then normalises to [0, 1).  Same inputs always yield the same
    output — no randomness, no state.
    """
    digest = hashlib.sha256(f"{chunk_id}:{key}".encode()).hexdigest()
    return int(digest[:8], 16) / 0x1_0000_0000   # divide by 2^32


def _hash_choice(chunk_id: str, key: str, options: Sequence) -> Any:
    """Return the element from options at the deterministic hash-derived index."""
    idx = int(_hash_float(chunk_id, key) * len(options)) % len(options)
    return options[idx]


# ── Vote aggregation ──────────────────────────────────────────────────────────

def _weighted_average(proposals: list[tuple[float, float]]) -> float:
    """
    Return the weighted mean of (value, weight) pairs.

    Weights are assumed to already sum to 1.0 (normalised by the caller).
    """
    return sum(v * w for v, w in proposals)


def _weighted_plurality(proposals: list[tuple[Any, float]]) -> Any:
    """
    Return the option with the highest cumulative weight.

    Ties broken by first-encountered option (stable for deterministic inputs).
    """
    tally: dict[Any, float] = {}
    for option, weight in proposals:
        tally[option] = tally.get(option, 0.0) + weight
    return max(tally, key=lambda k: tally[k])


# ── Shape voting ──────────────────────────────────────────────────────────────

def _vote_shape(voters: list[tuple[str, float]], index: int) -> ShapeParams:
    """
    Produce one ShapeParams by aggregating votes for shape slot `index`.

    Each voter proposes values for all fields of the shape.  Discrete fields
    use plurality; continuous fields use weighted average.
    """
    p = f"shape_{index}"   # prefix keeps each shape's keys distinct

    shape_type = _weighted_plurality([
        (_hash_choice(cid, f"{p}_type",         SHAPE_TYPES),    w) for cid, w in voters
    ])
    fill_color = _weighted_plurality([
        (_hash_choice(cid, f"{p}_fill",         _COLOR_VALUES),  w) for cid, w in voters
    ])
    stroke_color = _weighted_plurality([
        (_hash_choice(cid, f"{p}_stroke",       _COLOR_VALUES),  w) for cid, w in voters
    ])
    stroke_width = _weighted_plurality([
        (_hash_choice(cid, f"{p}_stroke_width", _STROKE_VALUES), w) for cid, w in voters
    ])
    x       = _weighted_average([(_hash_float(cid, f"{p}_x"),       w) for cid, w in voters])
    y       = _weighted_average([(_hash_float(cid, f"{p}_y"),       w) for cid, w in voters])
    size    = _weighted_average([(_hash_float(cid, f"{p}_size"),    w) for cid, w in voters])
    opacity = _weighted_average([(_hash_float(cid, f"{p}_opacity"), w) for cid, w in voters])

    return ShapeParams(
        shape_type=shape_type,
        fill_color=fill_color,
        stroke_color=stroke_color,
        stroke_width=stroke_width,
        x=x, y=y, size=size, opacity=opacity,
    )


# ── Public API ────────────────────────────────────────────────────────────────

def vote_on_parameters(voters: list[tuple[str, float]]) -> ArtParameters:
    """
    Produce ArtParameters from a weighted list of source-node voters.

    voters: list of (chunk_id, weight) — typically the output of
            SemanticGraph.source_neighbors(query_chunk_id, k).

    Weights need not be normalised; this function normalises them internally.
    Raises ValueError if voters is empty.
    """
    if not voters:
        raise ValueError("vote_on_parameters requires at least one voter")

    # Normalise weights so they sum to 1.0 for correct averaging/plurality
    total = sum(w for _, w in voters)
    normed: list[tuple[str, float]] = [(cid, w / total) for cid, w in voters]

    # Background color — one discrete vote across all voters
    background_color: str = _weighted_plurality([
        (_hash_choice(cid, "background_color", _COLOR_VALUES), w) for cid, w in normed
    ])

    # Shape count — weighted average of each voter's hash-derived proposal,
    # scaled to [MIN_SHAPES, MAX_SHAPES] and clamped for safety
    shape_count_proposals = [
        (_hash_float(cid, "shape_count"), w) for cid, w in normed
    ]
    raw_count = _weighted_average(shape_count_proposals)
    shape_count = MIN_SHAPES + round(raw_count * (MAX_SHAPES - MIN_SHAPES))
    shape_count = max(MIN_SHAPES, min(MAX_SHAPES, shape_count))

    shapes = [_vote_shape(normed, i) for i in range(shape_count)]

    logger.debug(
        "vote_on_parameters: %d voter(s), %d shape(s), bg=%s",
        len(voters), shape_count, background_color,
    )

    return ArtParameters(background_color=background_color, shapes=shapes)
