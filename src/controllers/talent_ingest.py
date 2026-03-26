"""
Talent data ingestion pipeline — PRD 2.1

Re-ingests the robot's own generated artwork back into the knowledge graph
as a new class of data: ArtworkNodes linked to the SourceNodes that influenced
them, with co-activation edges strengthened between those sources.

Also provides select_talent_voters, which builds the talent cluster voter list
for the next generation cycle: all artworks at or above TALENT_SIMILARITY_THRESHOLD
connection to the current humanities parameter set, collectively weighted at
TALENT_WEIGHT_MULTIPLIER × one humanities parameter.

Public API:
  ingest_artwork(params, svg_path, voters, graph)   → None
  select_talent_voters(chunk_ids, graph)             → list[tuple[str, float]]
"""
import logging
from pathlib import Path

from src.config.settings import TALENT_WEIGHT_MULTIPLIER
from src.models.art_params import ArtParameters
from src.models.graph import SemanticGraph

logger = logging.getLogger(__name__)


def ingest_artwork(
    params: ArtParameters,
    svg_path: Path,
    voters: list[tuple[str, float]],
    graph: SemanticGraph,
) -> None:
    """
    Record a generated artwork in the knowledge graph.

    Adds an ArtworkNode, wires influence edges to each source chunk that voted,
    and strengthens co-activation edges between all voter pairs so the robot
    gravitates toward familiar chunk combinations in future cycles.

    voters must contain only humanities voters (chunk_ids from SourceNodes).
    Talent voters from the generation cycle are not recorded as lineage — they
    are ephemeral inputs, not creative sources.

    Does not call graph.save() — the caller is responsible for persisting.
    Raises ValueError if voters is empty.
    """
    if not voters:
        raise ValueError("ingest_artwork requires at least one voter")

    chunk_ids = [cid for cid, _ in voters]

    graph.add_artwork_node(params.artwork_id, str(svg_path))
    graph.link_artwork(params.artwork_id, chunk_ids)

    if len(chunk_ids) > 1:
        graph.coactivate(chunk_ids)

    logger.debug(
        "Artwork ingested: id=%s, %d source(s), coactivation=%s",
        params.artwork_id, len(chunk_ids), len(chunk_ids) > 1,
    )


def select_talent_voters(
    chunk_ids: list[str],
    graph: SemanticGraph,
) -> list[tuple[str, float]]:
    """
    Build the talent cluster voter list for a generation cycle.

    Finds all ArtworkNodes whose source lineage is connected to chunk_ids at
    or above TALENT_SIMILARITY_THRESHOLD.  Each artwork in the cluster receives
    equal weight so the cluster's total weight equals TALENT_WEIGHT_MULTIPLIER.

    Returns [] when the talent pool is empty or no artwork meets the threshold
    (e.g. on the very first generation cycle).

    The returned list is ready to concatenate with the humanities voters before
    calling vote_on_parameters — the voting engine normalises all weights so the
    1.5× ratio is preserved automatically.
    """
    artwork_ids = graph.artwork_neighbors(chunk_ids)
    if not artwork_ids:
        return []

    weight_each = TALENT_WEIGHT_MULTIPLIER / len(artwork_ids)
    logger.debug(
        "Talent cluster: %d artwork(s), weight_each=%.4f",
        len(artwork_ids), weight_each,
    )
    return [(aid, weight_each) for aid in artwork_ids]
