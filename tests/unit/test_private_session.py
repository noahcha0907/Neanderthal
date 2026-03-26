"""
Unit tests for private session mode — PRD 2.4

Covers:
  - select_private_voters: biased pool composition, upload dominance, clamping,
    empty graph with uploads, no duplicates from graph-resident uploads,
    empty pool, upload-only pool
  - run_generation_cycle with private flags:
      - ingest=False skips graph ingestion
      - fixed_n overrides random count
      - upload_chunk_ids routes to private voter selection
      - private cycle still produces valid result dict
      - default behaviour (ingest=True, no uploads) unchanged
"""
import random

import pytest

from src.config.settings import MAX_PARAMETERS, MIN_PARAMETERS, UPLOAD_WEIGHT_BIAS
from src.controllers.generation_cycle import (
    run_generation_cycle,
    select_private_voters,
)
from src.models.corpus import CorpusChunk
from src.models.graph import SemanticGraph
from src.models.trace import JustificationTrace


# ── Stubs and helpers ─────────────────────────────────────────────────────────

class _StubTraceStore:
    def __init__(self):
        self.saved: list[JustificationTrace] = []
        self.commits = 0

    def save(self, trace: JustificationTrace) -> None:
        self.saved.append(trace)

    def commit(self) -> None:
        self.commits += 1


def make_graph() -> SemanticGraph:
    return SemanticGraph(path=None)


def make_chunk(chunk_id: str) -> CorpusChunk:
    return CorpusChunk(
        chunk_id=chunk_id,
        source_path="data/test.txt",
        title="Test Work",
        author="Test Author",
        doc_type="literary",
        year=2024,
        chunk_index=0,
        text="Sample text.",
        chunk_strategy="paragraph",
    )


def add_source(graph: SemanticGraph, chunk_id: str) -> None:
    graph.add_source_node(make_chunk(chunk_id))


def add_similarity_edge(graph: SemanticGraph, a: str, b: str, w: float) -> None:
    graph._graph.add_edge(a, b, kind="similarity", weight=w)
    graph._graph.add_edge(b, a, kind="similarity", weight=w)


def populated_graph(n: int = 5) -> SemanticGraph:
    g = make_graph()
    for i in range(n):
        add_source(g, f"chunk_{i}")
    for i in range(n - 1):
        add_similarity_edge(g, f"chunk_{i}", f"chunk_{i + 1}", 0.7)
    return g


# ── select_private_voters ─────────────────────────────────────────────────────

def test_private_voters_empty_graph_with_uploads():
    """Upload-only pool — graph is empty but uploads produce voters."""
    g = make_graph()
    result = select_private_voters(g, ["upload_a", "upload_b"], 2, random.Random(0))
    assert len(result) == 2
    ids = {cid for cid, _ in result}
    assert ids == {"upload_a", "upload_b"}


def test_private_voters_empty_graph_no_uploads_returns_empty():
    g = make_graph()
    result = select_private_voters(g, [], 3, random.Random(0))
    assert result == []


def test_private_voters_no_uploads_behaves_like_graph_pool():
    """No uploads → pool is graph nodes only, same as select_humanities_voters."""
    g = populated_graph(4)
    graph_ids = {cid for cid, _ in g.source_node_weights()}
    result = select_private_voters(g, [], 3, random.Random(42))
    assert len(result) == 3
    for cid, w in result:
        assert cid in graph_ids
        assert w == pytest.approx(1.0)


def test_private_voters_includes_upload_ids():
    """Upload chunk IDs can appear in selections even when not in the graph."""
    g = populated_graph(3)
    result = select_private_voters(
        g, ["upload_x"], 4, random.Random(0)
    )
    ids = [cid for cid, _ in result]
    # Pool has 4 nodes (3 graph + 1 upload) → all selected
    assert "upload_x" in ids


def test_private_voters_no_duplicates():
    g = populated_graph(4)
    result = select_private_voters(g, ["upload_a", "upload_b"], 6, random.Random(0))
    ids = [cid for cid, _ in result]
    assert len(ids) == len(set(ids))


def test_private_voters_clamps_n_to_pool_size():
    g = populated_graph(2)
    result = select_private_voters(g, ["upload_a"], 99, random.Random(0))
    # Pool = 2 graph + 1 upload = 3
    assert len(result) == 3


def test_private_voters_returns_weight_one():
    g = populated_graph(3)
    result = select_private_voters(g, ["upload_a"], 4, random.Random(0))
    for _, w in result:
        assert w == pytest.approx(1.0)


def test_private_voters_upload_dominates_graph_nodes():
    """Over many samples, upload chunk is selected more often than isolated graph nodes."""
    g = make_graph()
    add_source(g, "graph_isolated")  # weight 0.0 → floor 0.01
    uploads = ["upload_dominant"]    # weight = UPLOAD_WEIGHT_BIAS (3.0)

    rng = random.Random(0)
    upload_count = 0
    graph_count = 0
    trials = 400
    for _ in range(trials):
        voters = select_private_voters(g, uploads, 1, rng)
        if voters[0][0] == "upload_dominant":
            upload_count += 1
        else:
            graph_count += 1

    # UPLOAD_WEIGHT_BIAS >> floor weight → upload wins the vast majority
    assert upload_count > graph_count * 10


def test_private_voters_graph_resident_upload_not_duplicated():
    """An upload chunk_id already in the graph is not added a second time."""
    g = populated_graph(3)
    existing_id = "chunk_0"  # already a graph SourceNode
    # Request n large enough to select all available
    result = select_private_voters(g, [existing_id], 10, random.Random(0))
    ids = [cid for cid, _ in result]
    assert ids.count(existing_id) == 1


def test_private_voters_upload_only_empty_graph_clamps_to_uploads():
    g = make_graph()
    result = select_private_voters(g, ["u1", "u2", "u3"], 10, random.Random(0))
    assert len(result) == 3
    ids = {cid for cid, _ in result}
    assert ids == {"u1", "u2", "u3"}


# ── run_generation_cycle private flags ───────────────────────────────────────

def test_private_cycle_ingest_false_skips_graph_ingestion(tmp_path):
    """With ingest=False, no ArtworkNode is added to the graph."""
    g = populated_graph(3)
    result = run_generation_cycle(
        graph=g,
        chunks={},
        trace_store=_StubTraceStore(),
        output_dir=tmp_path,
        rng=random.Random(0),
        ingest=False,
    )
    assert result is not None
    artwork_node = f"artwork:{result['artwork_id']}"
    assert not g._graph.has_node(artwork_node)


def test_public_cycle_ingest_true_adds_artwork_node(tmp_path):
    """Default ingest=True still ingests — existing behaviour preserved."""
    g = populated_graph(3)
    chunks = {cid: make_chunk(cid) for cid, _ in g.source_node_weights()}
    result = run_generation_cycle(
        graph=g,
        chunks=chunks,
        trace_store=_StubTraceStore(),
        output_dir=tmp_path,
        rng=random.Random(0),
    )
    assert g._graph.has_node(f"artwork:{result['artwork_id']}")


def test_private_cycle_fixed_n_sets_voter_count(tmp_path):
    """fixed_n overrides the random selection count."""
    g = populated_graph(5)
    for fixed in range(MIN_PARAMETERS, MAX_PARAMETERS + 1):
        result = run_generation_cycle(
            graph=g,
            chunks={},
            trace_store=_StubTraceStore(),
            output_dir=tmp_path,
            rng=random.Random(fixed),
            fixed_n=fixed,
            ingest=False,
        )
        assert result["voter_count"] == fixed


def test_private_cycle_with_uploads_produces_result(tmp_path):
    """Private cycle with upload_chunk_ids completes successfully."""
    g = make_graph()  # empty graph — voters come from uploads only
    upload_ids = ["upload_a", "upload_b", "upload_c"]
    chunks = {cid: make_chunk(cid) for cid in upload_ids}
    result = run_generation_cycle(
        graph=g,
        chunks=chunks,
        trace_store=_StubTraceStore(),
        output_dir=tmp_path,
        rng=random.Random(7),
        upload_chunk_ids=upload_ids,
        fixed_n=2,
        ingest=False,
    )
    assert result is not None
    assert "artwork_id" in result
    assert "svg_path" in result


def test_private_cycle_upload_voters_appear_in_result(tmp_path):
    """Upload chunk IDs selected as voters contribute to voter_count."""
    g = make_graph()
    upload_ids = ["upload_a", "upload_b"]
    result = run_generation_cycle(
        graph=g,
        chunks={},
        trace_store=_StubTraceStore(),
        output_dir=tmp_path,
        rng=random.Random(0),
        upload_chunk_ids=upload_ids,
        fixed_n=2,
        ingest=False,
    )
    assert result["voter_count"] == 2


def test_private_cycle_saves_trace(tmp_path):
    """Trace is still persisted in private mode."""
    g = populated_graph(3)
    trace_store = _StubTraceStore()
    run_generation_cycle(
        graph=g,
        chunks={},
        trace_store=trace_store,
        output_dir=tmp_path,
        rng=random.Random(1),
        ingest=False,
    )
    assert len(trace_store.saved) == 1
    assert trace_store.commits == 1


def test_private_cycle_calls_on_artwork_ready(tmp_path):
    """on_artwork_ready callback fires even when ingest=False."""
    g = populated_graph(3)
    received: list[dict] = []
    run_generation_cycle(
        graph=g,
        chunks={},
        trace_store=_StubTraceStore(),
        output_dir=tmp_path,
        on_artwork_ready=received.append,
        rng=random.Random(2),
        ingest=False,
    )
    assert len(received) == 1


def test_private_cycle_empty_pool_returns_none(tmp_path):
    """Empty graph with no uploads → None, no crash."""
    g = make_graph()
    result = run_generation_cycle(
        graph=g,
        chunks={},
        trace_store=_StubTraceStore(),
        output_dir=tmp_path,
        rng=random.Random(0),
        ingest=False,
    )
    assert result is None


def test_private_cycle_upload_only_no_graph_nodes(tmp_path):
    """Cycle works when the graph has no SourceNodes and voters are all uploads."""
    g = make_graph()
    upload_ids = ["private_upload_1"]
    result = run_generation_cycle(
        graph=g,
        chunks={},
        trace_store=_StubTraceStore(),
        output_dir=tmp_path,
        rng=random.Random(5),
        upload_chunk_ids=upload_ids,
        fixed_n=1,
        ingest=False,
    )
    assert result is not None
    assert result["voter_count"] == 1
