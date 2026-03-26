"""
Unit tests for the semantic graph engine — PRD 1.3

All tests use in-memory graphs (path=None) so no filesystem I/O occurs except
in the save/load round-trip test, which uses pytest's tmp_path fixture.
No database connection is required.
"""
import pytest

from src.models.corpus import CorpusChunk
from src.models.embeddings import ScoredChunk
from src.models.graph import SemanticGraph, _concept_node_id, _artwork_node_id


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def graph():
    """A fresh in-memory SemanticGraph."""
    return SemanticGraph(path=None)


def make_chunk(chunk_id: str, title: str = "Test Work", chunk_index: int = 0) -> CorpusChunk:
    return CorpusChunk(
        chunk_id=chunk_id,
        source_path=f"data/humanities/{title.lower().replace(' ', '_')}.txt",
        title=title,
        author="Test Author",
        doc_type="literary",
        year=2024,
        chunk_index=chunk_index,
        text=f"Sample text for chunk {chunk_id}.",
        chunk_strategy="paragraph",
    )


def make_scored(chunk: CorpusChunk, similarity: float) -> ScoredChunk:
    return ScoredChunk(chunk=chunk, similarity=similarity)


# ── Source nodes ──────────────────────────────────────────────────────────────

def test_add_source_node_stores_attributes(graph):
    """Node is present in the graph with the correct kind and metadata."""
    chunk = make_chunk("abc123", title="Meditations", chunk_index=1)
    graph.add_source_node(chunk)

    assert graph.node_count() == 1
    data = graph._graph.nodes["abc123"]
    assert data["kind"] == "source"
    assert data["title"] == "Meditations"
    assert data["author"] == "Test Author"
    assert data["chunk_index"] == 1


def test_add_source_node_is_idempotent(graph):
    """Adding the same chunk twice does not create duplicate nodes."""
    chunk = make_chunk("abc123")
    graph.add_source_node(chunk)
    graph.add_source_node(chunk)
    assert graph.node_count() == 1


# ── Source edges ──────────────────────────────────────────────────────────────

def test_add_source_edges_creates_bidirectional_edges(graph):
    """Similarity edges are created in both directions with the given weight."""
    c1 = make_chunk("chunk_1")
    c2 = make_chunk("chunk_2")
    graph.add_source_node(c1)
    graph.add_source_node(c2)

    graph.add_source_edges("chunk_1", [make_scored(c2, 0.85)])

    assert graph._graph.has_edge("chunk_1", "chunk_2")
    assert graph._graph.has_edge("chunk_2", "chunk_1")
    assert graph._graph["chunk_1"]["chunk_2"]["weight"] == pytest.approx(0.85)
    assert graph._graph["chunk_2"]["chunk_1"]["weight"] == pytest.approx(0.85)


def test_add_source_edges_skips_below_threshold(graph):
    """Neighbors with similarity below the threshold produce no edges."""
    c1 = make_chunk("chunk_1")
    c2 = make_chunk("chunk_2")
    graph.add_source_node(c1)
    graph.add_source_node(c2)

    graph.add_source_edges("chunk_1", [make_scored(c2, 0.30)], threshold=0.50)

    assert not graph._graph.has_edge("chunk_1", "chunk_2")
    assert graph.edge_count() == 0


def test_add_source_edges_skips_self(graph):
    """A chunk is never connected to itself even if it appears in its own neighbor list."""
    c1 = make_chunk("chunk_1")
    graph.add_source_node(c1)

    graph.add_source_edges("chunk_1", [make_scored(c1, 1.0)])

    assert graph.edge_count() == 0


def test_add_source_edges_skips_unknown_neighbor(graph):
    """If a neighbor is not in the graph, no edge is created and no error is raised."""
    c1 = make_chunk("chunk_1")
    c_unknown = make_chunk("not_in_graph")
    graph.add_source_node(c1)

    graph.add_source_edges("chunk_1", [make_scored(c_unknown, 0.90)])

    assert graph.edge_count() == 0


def test_add_source_edges_keeps_higher_weight(graph):
    """On repeated calls, the higher weight is retained (idempotent rebuilds)."""
    c1 = make_chunk("chunk_1")
    c2 = make_chunk("chunk_2")
    graph.add_source_node(c1)
    graph.add_source_node(c2)

    graph.add_source_edges("chunk_1", [make_scored(c2, 0.80)])
    graph.add_source_edges("chunk_1", [make_scored(c2, 0.60)])  # lower — should not overwrite

    assert graph._graph["chunk_1"]["chunk_2"]["weight"] == pytest.approx(0.80)


# ── Concept nodes ─────────────────────────────────────────────────────────────

def test_seed_concepts_creates_concept_nodes(graph):
    """seed_concepts creates one ConceptNode per label."""
    labels = ["suffering", "freedom", "memory"]
    graph.seed_concepts(labels)

    assert graph.node_count() == 3
    for label in labels:
        node_id = _concept_node_id(label)
        assert graph._graph.has_node(node_id)
        assert graph._graph.nodes[node_id]["kind"] == "concept"
        assert graph._graph.nodes[node_id]["label"] == label


def test_seed_concepts_is_idempotent(graph):
    """Calling seed_concepts twice does not duplicate nodes."""
    labels = ["suffering", "freedom"]
    graph.seed_concepts(labels)
    graph.seed_concepts(labels)
    assert graph.node_count() == 2


def test_link_concept_creates_edge(graph):
    """link_concept creates a directed edge with the given weight."""
    chunk = make_chunk("chunk_1")
    graph.add_source_node(chunk)
    graph.link_concept("chunk_1", "suffering", 0.75)

    concept_id = _concept_node_id("suffering")
    assert graph._graph.has_edge("chunk_1", concept_id)
    assert graph._graph["chunk_1"][concept_id]["weight"] == pytest.approx(0.75)
    assert graph._graph["chunk_1"][concept_id]["kind"] == "concept"


def test_link_concept_auto_creates_concept_node(graph):
    """link_concept creates the ConceptNode if it does not already exist."""
    chunk = make_chunk("chunk_1")
    graph.add_source_node(chunk)

    graph.link_concept("chunk_1", "solitude", 0.6)

    assert graph._graph.has_node(_concept_node_id("solitude"))


def test_link_concept_raises_for_unknown_source(graph):
    """Linking a concept to a non-existent source node raises ValueError."""
    with pytest.raises(ValueError, match="not found"):
        graph.link_concept("nonexistent_chunk", "suffering", 0.5)


# ── Artwork nodes ─────────────────────────────────────────────────────────────

def test_add_artwork_node_is_idempotent(graph):
    """Adding the same artwork twice does not duplicate the node."""
    graph.add_artwork_node("art_001", "data/talent/art_001.svg")
    graph.add_artwork_node("art_001", "data/talent/art_001.svg")
    assert graph.node_count() == 1


def test_add_artwork_node_stores_attributes(graph):
    """ArtworkNode carries artwork_id, svg_path, and created_at."""
    graph.add_artwork_node("art_001", "data/talent/art_001.svg")

    node_id = _artwork_node_id("art_001")
    data = graph._graph.nodes[node_id]
    assert data["kind"] == "artwork"
    assert data["artwork_id"] == "art_001"
    assert data["svg_path"] == "data/talent/art_001.svg"
    assert "created_at" in data


def test_link_artwork_creates_influence_edges(graph):
    """link_artwork adds directed influence edges from artwork to its sources."""
    c1 = make_chunk("chunk_1")
    c2 = make_chunk("chunk_2")
    graph.add_source_node(c1)
    graph.add_source_node(c2)
    graph.add_artwork_node("art_001", "data/talent/art_001.svg")

    graph.link_artwork("art_001", ["chunk_1", "chunk_2"])

    art_id = _artwork_node_id("art_001")
    assert graph._graph.has_edge(art_id, "chunk_1")
    assert graph._graph.has_edge(art_id, "chunk_2")
    assert graph._graph[art_id]["chunk_1"]["kind"] == "influence"


def test_link_artwork_skips_unknown_chunks(graph):
    """chunk_ids not in the graph are silently skipped; no error is raised."""
    graph.add_artwork_node("art_001", "data/talent/art_001.svg")

    graph.link_artwork("art_001", ["nonexistent_chunk"])

    art_id = _artwork_node_id("art_001")
    assert graph._graph.out_degree(art_id) == 0


def test_link_artwork_raises_for_unknown_artwork(graph):
    """Linking sources to a non-existent artwork raises ValueError."""
    c1 = make_chunk("chunk_1")
    graph.add_source_node(c1)

    with pytest.raises(ValueError, match="not found"):
        graph.link_artwork("nonexistent_art", ["chunk_1"])


# ── Edge decay and pruning ────────────────────────────────────────────────────

def test_decay_edges_scales_all_weights(graph):
    """decay_edges multiplies every edge weight by the given factor."""
    c1 = make_chunk("chunk_1")
    c2 = make_chunk("chunk_2")
    graph.add_source_node(c1)
    graph.add_source_node(c2)
    graph.add_source_edges("chunk_1", [make_scored(c2, 0.80)])

    graph.decay_edges(factor=0.95)

    assert graph._graph["chunk_1"]["chunk_2"]["weight"] == pytest.approx(0.80 * 0.95)
    assert graph._graph["chunk_2"]["chunk_1"]["weight"] == pytest.approx(0.80 * 0.95)


def test_prune_edges_removes_below_threshold(graph):
    """prune_edges removes edges whose weight is below min_weight."""
    c1 = make_chunk("chunk_1")
    c2 = make_chunk("chunk_2")
    c3 = make_chunk("chunk_3")
    graph.add_source_node(c1)
    graph.add_source_node(c2)
    graph.add_source_node(c3)
    graph.add_source_edges("chunk_1", [make_scored(c2, 0.80)])
    graph.add_source_edges("chunk_1", [make_scored(c3, 0.60)])

    # Force chunk_1↔chunk_3 edges below threshold
    graph._graph["chunk_1"]["chunk_3"]["weight"] = 0.005
    graph._graph["chunk_3"]["chunk_1"]["weight"] = 0.005

    graph.prune_edges(min_weight=0.01)

    assert graph._graph.has_edge("chunk_1", "chunk_2")   # kept
    assert not graph._graph.has_edge("chunk_1", "chunk_3")  # pruned
    assert not graph._graph.has_edge("chunk_3", "chunk_1")  # pruned


# ── Query ─────────────────────────────────────────────────────────────────────

def test_source_neighbors_ordered_by_weight(graph):
    """source_neighbors returns the k highest-weight neighbors in descending order."""
    chunks = [make_chunk(f"chunk_{i}") for i in range(4)]
    for c in chunks:
        graph.add_source_node(c)

    # chunk_0 → chunk_1 (0.90), chunk_2 (0.70), chunk_3 (0.55)
    graph.add_source_edges("chunk_0", [
        make_scored(chunks[1], 0.90),
        make_scored(chunks[2], 0.70),
        make_scored(chunks[3], 0.55),
    ])

    neighbors = graph.source_neighbors("chunk_0", k=2)

    assert len(neighbors) == 2
    assert neighbors[0] == ("chunk_1", pytest.approx(0.90))
    assert neighbors[1] == ("chunk_2", pytest.approx(0.70))


def test_source_neighbors_returns_empty_for_unknown_node(graph):
    """source_neighbors returns [] for a node not in the graph."""
    assert graph.source_neighbors("does_not_exist") == []


def test_concept_neighbors_ordered_by_weight(graph):
    """concept_neighbors returns the k highest-weight concepts in descending order."""
    chunk = make_chunk("chunk_1")
    graph.add_source_node(chunk)
    graph.link_concept("chunk_1", "suffering", 0.9)
    graph.link_concept("chunk_1", "memory",    0.6)
    graph.link_concept("chunk_1", "freedom",   0.4)

    neighbors = graph.concept_neighbors("chunk_1", k=2)

    assert len(neighbors) == 2
    assert neighbors[0][0] == _concept_node_id("suffering")
    assert neighbors[0][1] == pytest.approx(0.9)
    assert neighbors[1][0] == _concept_node_id("memory")
    assert neighbors[1][1] == pytest.approx(0.6)


def test_concept_neighbors_returns_empty_for_unknown_node(graph):
    """concept_neighbors returns [] for a node not in the graph."""
    assert graph.concept_neighbors("does_not_exist") == []


# ── Save / load round-trip ────────────────────────────────────────────────────

def test_save_load_roundtrip(tmp_path):
    """A saved graph is fully restored after load, preserving nodes and edge weights."""
    graph_path = tmp_path / "graph.json"
    g = SemanticGraph(path=graph_path)

    c1 = make_chunk("chunk_1")
    c2 = make_chunk("chunk_2")
    g.add_source_node(c1)
    g.add_source_node(c2)
    g.add_source_edges("chunk_1", [make_scored(c2, 0.75)])
    g.seed_concepts(["suffering"])
    g.link_concept("chunk_1", "suffering", 0.85)
    g.save()

    # Load into a fresh graph object
    g2 = SemanticGraph(path=graph_path)

    assert g2.node_count() == g.node_count()
    assert g2.edge_count() == g.edge_count()
    assert g2._graph.has_edge("chunk_1", "chunk_2")
    assert g2._graph["chunk_1"]["chunk_2"]["weight"] == pytest.approx(0.75)
    assert g2._graph.has_edge("chunk_1", _concept_node_id("suffering"))


def test_save_raises_for_in_memory_graph():
    """Calling save() on a path=None graph raises RuntimeError."""
    g = SemanticGraph(path=None)
    with pytest.raises(RuntimeError):
        g.save()


def test_load_raises_for_in_memory_graph():
    """Calling load() on a path=None graph raises RuntimeError."""
    g = SemanticGraph(path=None)
    with pytest.raises(RuntimeError):
        g.load()
