"""
Unit tests for the talent data ingestion pipeline — PRD 2.1

Covers:
  - SemanticGraph.artwork_neighbors: threshold filtering, direct match, empty pool
  - SemanticGraph.coactivate: edge creation, weight bumping, cap at 1.0, bidirectionality
  - ingest_artwork: node creation, influence edges, coactivation, single-voter edge case
  - select_talent_voters: empty pool, weight distribution, weight sum equals multiplier
"""
import pytest

from src.config.settings import COACTIVATION_BUMP, TALENT_WEIGHT_MULTIPLIER
from src.controllers.talent_ingest import ingest_artwork, select_talent_voters
from src.models.art_params import ArtParameters, ShapeParams
from src.models.corpus import CorpusChunk
from src.models.graph import SemanticGraph


# ── Fixtures and helpers ──────────────────────────────────────────────────────

def make_graph() -> SemanticGraph:
    """In-memory graph — no disk I/O."""
    return SemanticGraph(path=None)


def make_chunk(chunk_id: str) -> CorpusChunk:
    return CorpusChunk(
        chunk_id=chunk_id,
        source_path="data/test.txt",
        title="Test",
        author="Author",
        doc_type="literary",
        year=2024,
        chunk_index=0,
        text="Some text here.",
        chunk_strategy="paragraph",
    )


def make_params() -> ArtParameters:
    shape = ShapeParams(
        shape_type="circle", fill_color="#FF0000", stroke_color="#000000",
        stroke_width=1, x=0.5, y=0.5, size=0.2, opacity=1.0,
    )
    return ArtParameters(background_color="#FFFFFF", shapes=[shape])


def add_source(graph: SemanticGraph, chunk_id: str) -> None:
    graph.add_source_node(make_chunk(chunk_id))


def add_similarity_edge(graph: SemanticGraph, a: str, b: str, weight: float) -> None:
    """Add a bidirectional similarity edge directly via the internal graph."""
    graph._graph.add_edge(a, b, kind="similarity", weight=weight)
    graph._graph.add_edge(b, a, kind="similarity", weight=weight)


def add_artwork(graph: SemanticGraph, artwork_id: str, chunk_ids: list[str]) -> None:
    """Register an artwork linked to source chunks."""
    graph.add_artwork_node(artwork_id, f"data/talent/{artwork_id}.svg")
    graph.link_artwork(artwork_id, chunk_ids)


# ── SemanticGraph.artwork_neighbors ──────────────────────────────────────────

def test_artwork_neighbors_empty_talent_pool():
    """Returns [] when no artwork nodes exist in the graph."""
    graph = make_graph()
    add_source(graph, "chunk_a")
    assert graph.artwork_neighbors(["chunk_a"]) == []


def test_artwork_neighbors_direct_chunk_match():
    """Artwork whose source IS a param chunk is included (similarity = 1.0)."""
    graph = make_graph()
    add_source(graph, "chunk_a")
    add_artwork(graph, "art_1", ["chunk_a"])
    result = graph.artwork_neighbors(["chunk_a"])
    assert "art_1" in result


def test_artwork_neighbors_high_similarity_included():
    """Artwork connected via ≥ 0.90 similarity edge is included."""
    graph = make_graph()
    add_source(graph, "chunk_a")
    add_source(graph, "chunk_b")
    add_similarity_edge(graph, "chunk_a", "chunk_b", 0.92)
    add_artwork(graph, "art_1", ["chunk_b"])
    result = graph.artwork_neighbors(["chunk_a"])
    assert "art_1" in result


def test_artwork_neighbors_at_threshold_included():
    """Artwork at exactly 0.90 similarity is included (boundary inclusive)."""
    graph = make_graph()
    add_source(graph, "chunk_a")
    add_source(graph, "chunk_b")
    add_similarity_edge(graph, "chunk_a", "chunk_b", 0.90)
    add_artwork(graph, "art_1", ["chunk_b"])
    result = graph.artwork_neighbors(["chunk_a"], min_similarity=0.90)
    assert "art_1" in result


def test_artwork_neighbors_below_threshold_excluded():
    """Artwork connected at < 0.90 similarity is excluded."""
    graph = make_graph()
    add_source(graph, "chunk_a")
    add_source(graph, "chunk_b")
    add_similarity_edge(graph, "chunk_a", "chunk_b", 0.75)
    add_artwork(graph, "art_1", ["chunk_b"])
    result = graph.artwork_neighbors(["chunk_a"])
    assert "art_1" not in result


def test_artwork_neighbors_returns_multiple():
    """All artworks meeting the threshold are returned."""
    graph = make_graph()
    add_source(graph, "chunk_a")
    add_source(graph, "chunk_b")
    add_source(graph, "chunk_c")
    add_similarity_edge(graph, "chunk_a", "chunk_b", 0.95)
    add_similarity_edge(graph, "chunk_a", "chunk_c", 0.91)
    add_artwork(graph, "art_1", ["chunk_b"])
    add_artwork(graph, "art_2", ["chunk_c"])
    result = graph.artwork_neighbors(["chunk_a"])
    assert "art_1" in result
    assert "art_2" in result


def test_artwork_neighbors_mixed_inclusion():
    """Only artworks meeting the threshold are included; others are excluded."""
    graph = make_graph()
    add_source(graph, "chunk_a")
    add_source(graph, "chunk_b")
    add_source(graph, "chunk_c")
    add_similarity_edge(graph, "chunk_a", "chunk_b", 0.95)
    add_similarity_edge(graph, "chunk_a", "chunk_c", 0.50)
    add_artwork(graph, "art_1", ["chunk_b"])
    add_artwork(graph, "art_2", ["chunk_c"])
    result = graph.artwork_neighbors(["chunk_a"])
    assert "art_1" in result
    assert "art_2" not in result


def test_artwork_neighbors_artwork_with_no_sources_skipped():
    """ArtworkNode with no influence edges is never included."""
    graph = make_graph()
    add_source(graph, "chunk_a")
    graph.add_artwork_node("orphan_art", "data/talent/orphan_art.svg")
    # No link_artwork call — no influence edges
    result = graph.artwork_neighbors(["chunk_a"])
    assert "orphan_art" not in result


# ── SemanticGraph.coactivate ──────────────────────────────────────────────────

def test_coactivate_creates_edges_between_pair():
    """Creates bidirectional similarity edges when none exist."""
    graph = make_graph()
    add_source(graph, "chunk_a")
    add_source(graph, "chunk_b")
    graph.coactivate(["chunk_a", "chunk_b"])
    assert graph._graph.has_edge("chunk_a", "chunk_b")
    assert graph._graph.has_edge("chunk_b", "chunk_a")


def test_coactivate_new_edge_weight_equals_bump():
    """A newly created co-activation edge has weight == COACTIVATION_BUMP."""
    graph = make_graph()
    add_source(graph, "chunk_a")
    add_source(graph, "chunk_b")
    graph.coactivate(["chunk_a", "chunk_b"])
    assert graph._graph["chunk_a"]["chunk_b"]["weight"] == pytest.approx(COACTIVATION_BUMP)


def test_coactivate_bumps_existing_edge():
    """An existing similarity edge's weight is increased by COACTIVATION_BUMP."""
    graph = make_graph()
    add_source(graph, "chunk_a")
    add_source(graph, "chunk_b")
    add_similarity_edge(graph, "chunk_a", "chunk_b", 0.60)
    graph.coactivate(["chunk_a", "chunk_b"])
    assert graph._graph["chunk_a"]["chunk_b"]["weight"] == pytest.approx(0.60 + COACTIVATION_BUMP)


def test_coactivate_caps_at_one():
    """Weight is capped at 1.0 even if bump would exceed it."""
    graph = make_graph()
    add_source(graph, "chunk_a")
    add_source(graph, "chunk_b")
    add_similarity_edge(graph, "chunk_a", "chunk_b", 0.99)
    graph.coactivate(["chunk_a", "chunk_b"])
    assert graph._graph["chunk_a"]["chunk_b"]["weight"] <= 1.0


def test_coactivate_is_bidirectional():
    """Both directions of the edge are updated equally."""
    graph = make_graph()
    add_source(graph, "chunk_a")
    add_source(graph, "chunk_b")
    graph.coactivate(["chunk_a", "chunk_b"])
    w_fwd = graph._graph["chunk_a"]["chunk_b"]["weight"]
    w_rev = graph._graph["chunk_b"]["chunk_a"]["weight"]
    assert w_fwd == pytest.approx(w_rev)


def test_coactivate_single_chunk_no_edges():
    """Single chunk produces no edges — combinations(n=1, r=2) is empty."""
    graph = make_graph()
    add_source(graph, "chunk_a")
    before = graph.edge_count()
    graph.coactivate(["chunk_a"])
    assert graph.edge_count() == before


def test_coactivate_three_chunks_creates_three_pairs():
    """Three chunks produce 3 bidirectional pairs = 6 directed edges."""
    graph = make_graph()
    for cid in ("a", "b", "c"):
        add_source(graph, cid)
    graph.coactivate(["a", "b", "c"])
    assert graph._graph.has_edge("a", "b")
    assert graph._graph.has_edge("a", "c")
    assert graph._graph.has_edge("b", "c")


def test_coactivate_skips_unknown_chunk_ids():
    """Chunk IDs not in the graph are silently ignored."""
    graph = make_graph()
    add_source(graph, "chunk_a")
    before = graph.edge_count()
    graph.coactivate(["chunk_a", "nonexistent"])
    # Only one known node → no pair → no edges added
    assert graph.edge_count() == before


# ── ingest_artwork ────────────────────────────────────────────────────────────

def test_ingest_artwork_adds_artwork_node(tmp_path):
    """An ArtworkNode is present in the graph after ingestion."""
    graph = make_graph()
    add_source(graph, "chunk_a")
    params = make_params()
    svg_path = tmp_path / f"{params.artwork_id}.svg"
    svg_path.write_text("<svg/>", encoding="utf-8")

    ingest_artwork(params, svg_path, [("chunk_a", 1.0)], graph)

    assert graph._graph.has_node(f"artwork:{params.artwork_id}")


def test_ingest_artwork_links_source_chunks(tmp_path):
    """Influence edges are created from artwork to each voter source chunk."""
    graph = make_graph()
    add_source(graph, "chunk_a")
    add_source(graph, "chunk_b")
    params = make_params()
    svg_path = tmp_path / f"{params.artwork_id}.svg"
    svg_path.write_text("<svg/>", encoding="utf-8")
    voters = [("chunk_a", 0.7), ("chunk_b", 0.3)]

    ingest_artwork(params, svg_path, voters, graph)

    art_node = f"artwork:{params.artwork_id}"
    assert graph._graph.has_edge(art_node, "chunk_a")
    assert graph._graph.has_edge(art_node, "chunk_b")


def test_ingest_artwork_coactivates_multiple_voters(tmp_path):
    """Co-activation edges are created when more than one voter is present."""
    graph = make_graph()
    add_source(graph, "chunk_a")
    add_source(graph, "chunk_b")
    params = make_params()
    svg_path = tmp_path / f"{params.artwork_id}.svg"
    svg_path.write_text("<svg/>", encoding="utf-8")

    ingest_artwork(params, svg_path, [("chunk_a", 0.6), ("chunk_b", 0.4)], graph)

    assert graph._graph.has_edge("chunk_a", "chunk_b")
    assert graph._graph.has_edge("chunk_b", "chunk_a")


def test_ingest_artwork_single_voter_no_coactivation(tmp_path):
    """No co-activation edges are created when only one voter exists."""
    graph = make_graph()
    add_source(graph, "chunk_a")
    params = make_params()
    svg_path = tmp_path / f"{params.artwork_id}.svg"
    svg_path.write_text("<svg/>", encoding="utf-8")

    ingest_artwork(params, svg_path, [("chunk_a", 1.0)], graph)

    # No other source node → no co-activation edges possible
    assert not graph._graph.has_edge("chunk_a", "chunk_a")


def test_ingest_artwork_empty_voters_raises(tmp_path):
    """ingest_artwork raises ValueError when voters is empty."""
    graph = make_graph()
    params = make_params()
    svg_path = tmp_path / f"{params.artwork_id}.svg"
    svg_path.write_text("<svg/>", encoding="utf-8")

    with pytest.raises(ValueError):
        ingest_artwork(params, svg_path, [], graph)


def test_ingest_artwork_idempotent(tmp_path):
    """Re-ingesting the same artwork_id does not raise or duplicate nodes."""
    graph = make_graph()
    add_source(graph, "chunk_a")
    params = make_params()
    svg_path = tmp_path / f"{params.artwork_id}.svg"
    svg_path.write_text("<svg/>", encoding="utf-8")

    ingest_artwork(params, svg_path, [("chunk_a", 1.0)], graph)
    node_count_before = graph.node_count()

    ingest_artwork(params, svg_path, [("chunk_a", 1.0)], graph)
    assert graph.node_count() == node_count_before


def test_ingest_artwork_unknown_chunk_ids_skipped(tmp_path):
    """Voters whose chunk_ids are not in the graph are silently skipped."""
    graph = make_graph()
    # No source nodes added to the graph
    params = make_params()
    svg_path = tmp_path / f"{params.artwork_id}.svg"
    svg_path.write_text("<svg/>", encoding="utf-8")

    # Should not raise — unknown chunk_ids are harmless
    ingest_artwork(params, svg_path, [("unknown_chunk", 1.0)], graph)
    assert graph._graph.has_node(f"artwork:{params.artwork_id}")


# ── select_talent_voters ──────────────────────────────────────────────────────

def test_select_talent_voters_empty_graph_returns_empty():
    """Returns [] when no artworks exist in the graph."""
    graph = make_graph()
    add_source(graph, "chunk_a")
    assert select_talent_voters(["chunk_a"], graph) == []


def test_select_talent_voters_no_match_returns_empty():
    """Returns [] when no artwork meets the similarity threshold."""
    graph = make_graph()
    add_source(graph, "chunk_a")
    add_source(graph, "chunk_b")
    add_similarity_edge(graph, "chunk_a", "chunk_b", 0.50)  # below 0.90
    add_artwork(graph, "art_1", ["chunk_b"])

    assert select_talent_voters(["chunk_a"], graph) == []


def test_select_talent_voters_single_artwork_gets_full_multiplier():
    """When one artwork qualifies, it receives the full TALENT_WEIGHT_MULTIPLIER."""
    graph = make_graph()
    add_source(graph, "chunk_a")
    add_artwork(graph, "art_1", ["chunk_a"])  # direct match → similarity 1.0

    voters = select_talent_voters(["chunk_a"], graph)
    assert len(voters) == 1
    assert voters[0][0] == "art_1"
    assert voters[0][1] == pytest.approx(TALENT_WEIGHT_MULTIPLIER)


def test_select_talent_voters_weights_sum_to_multiplier():
    """Total weight of the talent cluster equals TALENT_WEIGHT_MULTIPLIER."""
    graph = make_graph()
    add_source(graph, "chunk_a")
    for i in range(4):
        add_artwork(graph, f"art_{i}", ["chunk_a"])

    voters = select_talent_voters(["chunk_a"], graph)
    total = sum(w for _, w in voters)
    assert total == pytest.approx(TALENT_WEIGHT_MULTIPLIER)


def test_select_talent_voters_each_artwork_equal_share():
    """Each artwork in the cluster receives equal weight."""
    graph = make_graph()
    add_source(graph, "chunk_a")
    for i in range(3):
        add_artwork(graph, f"art_{i}", ["chunk_a"])

    voters = select_talent_voters(["chunk_a"], graph)
    weights = [w for _, w in voters]
    assert all(w == pytest.approx(weights[0]) for w in weights)


def test_select_talent_voters_returns_artwork_ids_not_node_ids():
    """Voter tuples use bare artwork_ids, not the 'artwork:{id}' node key."""
    graph = make_graph()
    add_source(graph, "chunk_a")
    add_artwork(graph, "my-artwork-123", ["chunk_a"])

    voters = select_talent_voters(["chunk_a"], graph)
    ids = [vid for vid, _ in voters]
    assert "my-artwork-123" in ids
    assert "artwork:my-artwork-123" not in ids
