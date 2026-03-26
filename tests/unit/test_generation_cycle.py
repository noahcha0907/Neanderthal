"""
Unit tests for the autonomous generation cycle — PRD 2.2

Covers:
  - SemanticGraph.source_node_weights: connectivity scoring, isolation floor
  - select_humanities_voters: sampling count, clamping, empty graph
  - run_generation_cycle: full pipeline with in-memory graph + stub stores
  - GenerationTimer: start/stop/is_running lifecycle, no-overlap guarantee
"""
import random
import threading
import time

import pytest

from src.controllers.generation_cycle import (
    run_generation_cycle,
    select_humanities_voters,
)
from src.controllers.generation_timer import GenerationTimer
from src.models.art_params import ArtParameters, ShapeParams
from src.models.corpus import CorpusChunk
from src.models.graph import SemanticGraph
from src.models.trace import JustificationTrace


# ── Stubs ─────────────────────────────────────────────────────────────────────

class _StubTraceStore:
    """In-memory TraceStore stub — no database required."""
    def __init__(self):
        self.saved: list[JustificationTrace] = []
        self.commits = 0

    def save(self, trace: JustificationTrace) -> None:
        self.saved.append(trace)

    def commit(self) -> None:
        self.commits += 1


class _StubChunkStore:
    """In-memory ChunkStore stub for the timer tests."""
    def __init__(self, chunks: list[CorpusChunk]):
        self._chunks = chunks

    def all_chunks(self) -> list[CorpusChunk]:
        return list(self._chunks)


# ── Fixtures and helpers ──────────────────────────────────────────────────────

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
        text="First sentence here. Second sentence follows.",
        chunk_strategy="paragraph",
    )


def add_source(graph: SemanticGraph, chunk_id: str) -> None:
    graph.add_source_node(make_chunk(chunk_id))


def add_similarity_edge(graph: SemanticGraph, a: str, b: str, w: float) -> None:
    graph._graph.add_edge(a, b, kind="similarity", weight=w)
    graph._graph.add_edge(b, a, kind="similarity", weight=w)


def populated_graph(n: int = 5) -> SemanticGraph:
    """Graph with n connected source nodes."""
    g = make_graph()
    ids = [f"chunk_{i}" for i in range(n)]
    for cid in ids:
        add_source(g, cid)
    # Wire adjacent pairs so nodes have non-zero weight
    for i in range(len(ids) - 1):
        add_similarity_edge(g, ids[i], ids[i + 1], 0.7)
    return g


# ── SemanticGraph.source_node_weights ─────────────────────────────────────────

def test_source_node_weights_empty_graph():
    g = make_graph()
    assert g.source_node_weights() == []


def test_source_node_weights_isolated_node_has_zero():
    g = make_graph()
    add_source(g, "chunk_a")
    weights = dict(g.source_node_weights())
    assert weights["chunk_a"] == 0.0


def test_source_node_weights_connected_node_has_positive_weight():
    g = make_graph()
    add_source(g, "chunk_a")
    add_source(g, "chunk_b")
    add_similarity_edge(g, "chunk_a", "chunk_b", 0.8)
    weights = dict(g.source_node_weights())
    assert weights["chunk_a"] > 0
    assert weights["chunk_b"] > 0


def test_source_node_weights_excludes_non_source_nodes():
    """ConceptNodes and ArtworkNodes must not appear in the result."""
    g = make_graph()
    add_source(g, "chunk_a")
    g.seed_concepts(["freedom"])
    g.add_artwork_node("art_1", "data/talent/art_1.svg")
    ids = [cid for cid, _ in g.source_node_weights()]
    assert "chunk_a" in ids
    assert "concept:freedom" not in ids
    assert "artwork:art_1" not in ids


def test_source_node_weights_weight_proportional_to_edges():
    """More edges → higher weight."""
    g = make_graph()
    for cid in ("a", "b", "c", "d"):
        add_source(g, cid)
    # 'a' connected to b and c; 'b' connected only to 'a'
    add_similarity_edge(g, "a", "b", 0.6)
    add_similarity_edge(g, "a", "c", 0.6)
    weights = dict(g.source_node_weights())
    assert weights["a"] > weights["b"]


# ── select_humanities_voters ───────────────────────────────────────────────────

def test_select_humanities_voters_empty_graph():
    g = make_graph()
    result = select_humanities_voters(g, 3, random.Random(42))
    assert result == []


def test_select_humanities_voters_returns_n_voters():
    g = populated_graph(5)
    result = select_humanities_voters(g, 3, random.Random(42))
    assert len(result) == 3


def test_select_humanities_voters_clamps_n_to_available():
    """Requesting more voters than source nodes returns all available."""
    g = populated_graph(2)
    result = select_humanities_voters(g, 10, random.Random(0))
    assert len(result) == 2


def test_select_humanities_voters_no_duplicates():
    g = populated_graph(5)
    result = select_humanities_voters(g, 5, random.Random(7))
    ids = [cid for cid, _ in result]
    assert len(ids) == len(set(ids))


def test_select_humanities_voters_returns_valid_chunk_ids():
    g = populated_graph(4)
    known_ids = {cid for cid, _ in g.source_node_weights()}
    result = select_humanities_voters(g, 4, random.Random(1))
    for cid, _ in result:
        assert cid in known_ids


def test_select_humanities_voters_each_voter_weight_is_one():
    """Returned voters carry equal weight 1.0 — normalisation is vote_on_parameters' job."""
    g = populated_graph(3)
    result = select_humanities_voters(g, 3, random.Random(0))
    for _, w in result:
        assert w == pytest.approx(1.0)


def test_select_humanities_voters_prefers_connected_nodes():
    """Over many samples, the highly connected node wins more often than the isolated one."""
    g = make_graph()
    add_source(g, "popular")
    add_source(g, "isolated")
    add_source(g, "helper_1")
    add_source(g, "helper_2")
    add_similarity_edge(g, "popular", "helper_1", 0.9)
    add_similarity_edge(g, "popular", "helper_2", 0.9)
    # 'isolated' has no edges

    rng = random.Random(0)
    popular_count = 0
    isolated_count = 0
    for _ in range(200):
        voters = select_humanities_voters(g, 1, rng)
        if voters[0][0] == "popular":
            popular_count += 1
        elif voters[0][0] == "isolated":
            isolated_count += 1
    assert popular_count > isolated_count


# ── run_generation_cycle ──────────────────────────────────────────────────────

def test_run_generation_cycle_empty_graph_returns_none(tmp_path):
    g = make_graph()
    result = run_generation_cycle(
        graph=g,
        chunks={},
        trace_store=_StubTraceStore(),
        output_dir=tmp_path,
        rng=random.Random(0),
    )
    assert result is None


def test_run_generation_cycle_returns_result_dict(tmp_path):
    g = populated_graph(3)
    chunks = {cid: make_chunk(cid) for cid, _ in g.source_node_weights()}
    result = run_generation_cycle(
        graph=g,
        chunks=chunks,
        trace_store=_StubTraceStore(),
        output_dir=tmp_path,
        rng=random.Random(0),
    )
    assert result is not None
    assert "artwork_id" in result
    assert "svg_path" in result
    assert "trace_text" in result
    assert "voter_count" in result


def test_run_generation_cycle_saves_svg_file(tmp_path):
    g = populated_graph(3)
    chunks = {cid: make_chunk(cid) for cid, _ in g.source_node_weights()}
    result = run_generation_cycle(
        graph=g, chunks=chunks, trace_store=_StubTraceStore(),
        output_dir=tmp_path, rng=random.Random(1),
    )
    import pathlib
    assert pathlib.Path(result["svg_path"]).exists()


def test_run_generation_cycle_saves_trace(tmp_path):
    g = populated_graph(3)
    chunks = {cid: make_chunk(cid) for cid, _ in g.source_node_weights()}
    trace_store = _StubTraceStore()
    run_generation_cycle(
        graph=g, chunks=chunks, trace_store=trace_store,
        output_dir=tmp_path, rng=random.Random(2),
    )
    assert len(trace_store.saved) == 1
    assert trace_store.commits == 1


def test_run_generation_cycle_ingests_artwork_into_graph(tmp_path):
    g = populated_graph(3)
    chunks = {cid: make_chunk(cid) for cid, _ in g.source_node_weights()}
    result = run_generation_cycle(
        graph=g, chunks=chunks, trace_store=_StubTraceStore(),
        output_dir=tmp_path, rng=random.Random(3),
    )
    artwork_node = f"artwork:{result['artwork_id']}"
    assert g._graph.has_node(artwork_node)


def test_run_generation_cycle_calls_on_artwork_ready(tmp_path):
    g = populated_graph(3)
    chunks = {cid: make_chunk(cid) for cid, _ in g.source_node_weights()}
    received: list[dict] = []
    run_generation_cycle(
        graph=g, chunks=chunks, trace_store=_StubTraceStore(),
        output_dir=tmp_path, on_artwork_ready=received.append,
        rng=random.Random(4),
    )
    assert len(received) == 1
    assert received[0]["artwork_id"] is not None


def test_run_generation_cycle_voter_count_in_bounds(tmp_path):
    """voter_count is always between MIN_PARAMETERS and MAX_PARAMETERS."""
    from src.config.settings import MAX_PARAMETERS, MIN_PARAMETERS
    g = populated_graph(5)
    chunks = {cid: make_chunk(cid) for cid, _ in g.source_node_weights()}
    for seed in range(20):
        result = run_generation_cycle(
            graph=g, chunks=chunks, trace_store=_StubTraceStore(),
            output_dir=tmp_path, rng=random.Random(seed),
        )
        assert MIN_PARAMETERS <= result["voter_count"] <= MAX_PARAMETERS


# ── GenerationTimer ───────────────────────────────────────────────────────────

def _make_timer(graph: SemanticGraph, tmp_path, interval: float = 0.05):
    chunks = [make_chunk(cid) for cid, _ in graph.source_node_weights()]
    return GenerationTimer(
        graph=graph,
        chunk_store=_StubChunkStore(chunks),
        trace_store=_StubTraceStore(),
        output_dir=tmp_path,
        interval=interval,
    )


def test_timer_is_not_running_before_start(tmp_path):
    g = populated_graph(2)
    timer = _make_timer(g, tmp_path)
    assert not timer.is_running


def test_timer_is_running_after_start(tmp_path):
    g = populated_graph(2)
    timer = _make_timer(g, tmp_path)
    timer.start(seed=0)
    assert timer.is_running
    timer.stop()


def test_timer_is_not_running_after_stop(tmp_path):
    g = populated_graph(2)
    timer = _make_timer(g, tmp_path)
    timer.start(seed=0)
    timer.stop(timeout=2.0)
    assert not timer.is_running


def test_timer_raises_if_started_twice(tmp_path):
    g = populated_graph(2)
    timer = _make_timer(g, tmp_path)
    timer.start(seed=0)
    with pytest.raises(RuntimeError):
        timer.start(seed=1)
    timer.stop()


def test_timer_generates_artworks(tmp_path):
    """Timer calls the cycle at least once during its run."""
    g = populated_graph(3)
    results: list[dict] = []

    timer = _make_timer(g, tmp_path, interval=0.05)
    timer.start(on_artwork_ready=results.append, seed=0)
    time.sleep(0.3)
    timer.stop(timeout=2.0)

    assert len(results) >= 1


def test_timer_no_overlapping_cycles(tmp_path):
    """Only one cycle runs at a time — concurrent_count never exceeds 1."""
    g = populated_graph(3)
    concurrent_count = 0
    max_concurrent = 0
    lock = threading.Lock()

    def slow_callback(result: dict) -> None:
        nonlocal concurrent_count, max_concurrent
        with lock:
            concurrent_count += 1
            max_concurrent = max(max_concurrent, concurrent_count)
        time.sleep(0.05)  # simulate slow processing
        with lock:
            concurrent_count -= 1

    # Interval shorter than callback duration — tests no-overlap guarantee
    timer = _make_timer(g, tmp_path, interval=0.02)
    timer.start(on_artwork_ready=slow_callback, seed=0)
    time.sleep(0.4)
    timer.stop(timeout=2.0)

    assert max_concurrent == 1


def test_timer_stop_is_responsive(tmp_path):
    """stop() returns well before the interval expires."""
    g = populated_graph(2)
    timer = _make_timer(g, tmp_path, interval=60.0)  # very long interval
    timer.start(seed=0)
    t_start = time.monotonic()
    timer.stop(timeout=2.0)
    elapsed = time.monotonic() - t_start
    assert elapsed < 2.0
