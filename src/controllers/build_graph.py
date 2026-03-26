"""
Semantic graph builder — PRD 1.3

Reads all corpus chunks and pre-computed embeddings from PostgreSQL, then
constructs the semantic graph (SourceNodes + similarity edges + ConceptNodes)
and saves it to DATA_DIR/graph.json.

Run this once after corpus ingestion + embedding are complete, and again
whenever the corpus grows significantly.

Steps:
  1. Load all CorpusChunks from the chunks table
  2. Load all (chunk_id, vector) pairs from the embeddings table
  3. Add a SourceNode (with text) for every chunk
  4. Compute pairwise cosine similarity in one numpy batch pass
  5. Wire similarity edges for all pairs above SIMILARITY_EDGE_THRESHOLD
  6. Seed ConceptNodes from HUMANISTIC_CONCEPTS
  7. Save graph.json

CLI: python -m src.controllers.build_graph
"""
import logging
import sys
import time

import numpy as np

from src.config.settings import SIMILARITY_EDGE_THRESHOLD
from src.models.corpus import ChunkStore
from src.models.embeddings import EmbeddingStore, ScoredChunk
from src.models.graph import SemanticGraph

logger = logging.getLogger(__name__)


def build_graph() -> SemanticGraph:
    """
    Build and return a fully-populated SemanticGraph from the DB.

    Saves to graph.json before returning.
    """
    t0 = time.monotonic()

    # ── 1. Load chunks ────────────────────────────────────────────────────────

    logger.info("Loading chunks from database…")
    chunk_store = ChunkStore()
    all_chunks = chunk_store.all_chunks()
    chunk_store.close()

    chunks_by_id = {c.chunk_id: c for c in all_chunks}
    logger.info("  %d chunks loaded", len(all_chunks))

    # ── 2. Load embeddings ────────────────────────────────────────────────────

    logger.info("Loading embeddings from database…")
    emb_store = EmbeddingStore()
    emb_pairs = emb_store.all_embeddings()
    emb_store.close()

    logger.info("  %d embedding vectors loaded", len(emb_pairs))

    emb_ids = [cid for cid, _ in emb_pairs]
    # float64 avoids BLAS overflow/NaN warnings that can appear with float32
    # when pgvector returns denormal or extreme values.
    matrix = np.array([vec for _, vec in emb_pairs], dtype=np.float64)
    matrix = np.nan_to_num(matrix, nan=0.0, posinf=0.0, neginf=0.0)

    # Normalise rows so dot-product == cosine similarity.
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    matrix /= np.maximum(norms, 1e-8)

    # ── 3. Populate graph with source nodes ───────────────────────────────────

    logger.info("Adding %d SourceNodes…", len(all_chunks))
    graph = SemanticGraph()  # loads graph.json if it exists; else starts fresh

    for chunk in all_chunks:
        graph.add_source_node(chunk)

    # ── 4. Compute pairwise cosine similarity ─────────────────────────────────
    # For 6k-7k vectors of dim 384, the full matrix fits comfortably in memory.

    logger.info(
        "Computing pairwise similarity matrix (%d × %d)…",
        len(emb_ids), len(emb_ids),
    )
    # np.errstate suppresses spurious Accelerate BLAS warnings on macOS for
    # large float64 matmuls — the computation and results are numerically correct.
    with np.errstate(divide="ignore", over="ignore", invalid="ignore"):
        sim_matrix = matrix @ matrix.T   # shape: (n_emb, n_emb)

    # ── 5. Wire similarity edges ──────────────────────────────────────────────

    logger.info(
        "Wiring similarity edges (threshold=%.2f)…", SIMILARITY_EDGE_THRESHOLD,
    )
    edges_added = 0

    for i, chunk_id in enumerate(emb_ids):
        if chunk_id not in chunks_by_id:
            # Embedding row exists without a matching chunk — skip silently.
            continue

        sims = sim_matrix[i]
        # Indices of neighbours that clear the threshold (excluding self)
        candidate_indices = np.where(sims >= SIMILARITY_EDGE_THRESHOLD)[0]

        neighbors: list[ScoredChunk] = []
        for j in candidate_indices:
            if j == i:
                continue
            neighbor_id = emb_ids[j]
            if neighbor_id not in chunks_by_id:
                continue
            neighbors.append(
                ScoredChunk(
                    chunk=chunks_by_id[neighbor_id],
                    similarity=float(sims[j]),
                )
            )

        if neighbors:
            graph.add_source_edges(chunk_id, neighbors)
            edges_added += len(neighbors)

        if (i + 1) % 500 == 0:
            logger.info("  … %d / %d chunks processed", i + 1, len(emb_ids))

    logger.info("  %d directed similarity edges added", edges_added)

    # ── 6. Seed concept nodes ─────────────────────────────────────────────────

    logger.info("Seeding ConceptNodes…")
    graph.seed_concepts()

    # ── 7. Save ───────────────────────────────────────────────────────────────

    graph.save()
    elapsed = time.monotonic() - t0
    logger.info(
        "Graph saved: %d nodes, %d edges (%.1fs)",
        graph.node_count(), graph.edge_count(), elapsed,
    )

    return graph


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s — %(message)s",
        stream=sys.stdout,
    )
    g = build_graph()
    print(
        f"\nDone — {g.node_count()} nodes, {g.edge_count()} edges written to graph.json"
    )
