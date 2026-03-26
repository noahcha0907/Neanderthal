"""
Semantic graph engine — PRD 1.3

SemanticGraph is the robot's persistent memory: a directed weighted graph whose
nodes represent corpus chunks (SourceNode), humanistic concepts (ConceptNode),
and generated artworks (ArtworkNode). Edges encode semantic proximity, concept
affinity, and creative lineage.

Public API:
  SemanticGraph.add_source_node(chunk)                 → None
  SemanticGraph.add_source_edges(chunk_id, neighbors)  → None
  SemanticGraph.seed_concepts(labels)                  → None
  SemanticGraph.link_concept(chunk_id, label, weight)  → None
  SemanticGraph.add_artwork_node(artwork_id, svg_path) → None
  SemanticGraph.link_artwork(artwork_id, chunk_ids)    → None
  SemanticGraph.decay_edges(factor)                    → None
  SemanticGraph.prune_edges(min_weight)                → None
  SemanticGraph.source_neighbors(chunk_id, k)          → list[tuple[str, float]]
  SemanticGraph.concept_neighbors(chunk_id, k)         → list[tuple[str, float]]
  SemanticGraph.save()                                 → None
  SemanticGraph.load()                                 → None
"""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import networkx as nx

from src.config.settings import (
    COACTIVATION_BUMP,
    EDGE_DECAY_FACTOR,
    GRAPH_PATH,
    HUMANISTIC_CONCEPTS,
    MIN_EDGE_WEIGHT,
    SIMILARITY_EDGE_THRESHOLD,
    TALENT_SIMILARITY_THRESHOLD,
)
from src.models.corpus import CorpusChunk
from src.models.embeddings import ScoredChunk

logger = logging.getLogger(__name__)

# Node kind identifiers stored in each node's 'kind' attribute
_KIND_SOURCE  = "source"
_KIND_CONCEPT = "concept"
_KIND_ARTWORK = "artwork"

# Edge kind identifiers stored in each edge's 'kind' attribute
_EDGE_SIMILARITY = "similarity"
_EDGE_CONCEPT    = "concept"
_EDGE_INFLUENCE  = "influence"


def _concept_node_id(label: str) -> str:
    """Stable node ID for a concept label."""
    return f"concept:{label.lower().strip()}"


def _artwork_node_id(artwork_id: str) -> str:
    """Stable node ID for an artwork."""
    return f"artwork:{artwork_id}"


class SemanticGraph:
    """
    Directed weighted graph representing the robot's world model.

    SourceNodes  — one per corpus chunk, connected by cosine similarity edges.
    ConceptNodes — humanistic themes (suffering, freedom, …), linked from sources.
    ArtworkNodes — generated artworks, linked to the sources that inspired them.

    Edge weights decay each generation cycle so that recently reinforced
    associations dominate over stale ones.

    The graph serialises to a JSON file on disk so memory persists across runs.
    Pass path=None to get a purely in-memory graph (useful in tests).
    """

    def __init__(self, path: Optional[Path] = GRAPH_PATH):
        self._graph: nx.DiGraph = nx.DiGraph()
        self._path = path
        if path is not None and Path(path).exists():
            self.load()

    # ── Source nodes ─────────────────────────────────────────────────────────

    def add_source_node(self, chunk: CorpusChunk) -> None:
        """
        Add a SourceNode for this corpus chunk.

        Calling with the same chunk_id twice is idempotent — the node is not
        duplicated, but its attributes are updated to reflect any changes.
        """
        self._graph.add_node(
            chunk.chunk_id,
            kind=_KIND_SOURCE,
            source_path=chunk.source_path,
            title=chunk.title,
            author=chunk.author,
            doc_type=chunk.doc_type,
            year=chunk.year,
            chunk_index=chunk.chunk_index,
            text=chunk.text,
        )

    def add_source_edges(
        self,
        chunk_id: str,
        neighbors: list[ScoredChunk],
        threshold: float = SIMILARITY_EDGE_THRESHOLD,
    ) -> None:
        """
        Wire chunk_id to each neighbor whose similarity meets the threshold.

        Similarity edges are bidirectional — both directions carry the same weight.
        If an edge already exists, the higher of the two weights is kept so that
        idempotent graph rebuilds never weaken existing associations.

        Neighbors not already present as nodes in the graph are silently skipped.
        """
        for sc in neighbors:
            neighbor_id = sc.chunk.chunk_id
            if neighbor_id == chunk_id:
                continue
            if sc.similarity < threshold:
                continue
            if not self._graph.has_node(neighbor_id):
                continue

            weight = float(sc.similarity)
            for src, dst in [(chunk_id, neighbor_id), (neighbor_id, chunk_id)]:
                existing = self._graph.get_edge_data(src, dst)
                if existing is None or existing["weight"] < weight:
                    self._graph.add_edge(src, dst, kind=_EDGE_SIMILARITY, weight=weight)

    # ── Concept nodes ─────────────────────────────────────────────────────────

    def seed_concepts(self, labels: list[str] = None) -> None:
        """
        Add ConceptNodes for all humanistic themes in the labels list.

        Defaults to HUMANISTIC_CONCEPTS from settings. Safe to call multiple
        times — existing nodes are not modified.
        """
        if labels is None:
            labels = HUMANISTIC_CONCEPTS
        for label in labels:
            node_id = _concept_node_id(label)
            if not self._graph.has_node(node_id):
                self._graph.add_node(node_id, kind=_KIND_CONCEPT, label=label.lower().strip())

    def link_concept(self, chunk_id: str, concept_label: str, weight: float) -> None:
        """
        Add a weighted directed edge from a SourceNode to a ConceptNode.

        Creates the ConceptNode if it does not already exist.
        Raises ValueError if chunk_id is not in the graph.
        """
        if not self._graph.has_node(chunk_id):
            raise ValueError(f"Source node '{chunk_id}' not found — call add_source_node first")

        node_id = _concept_node_id(concept_label)
        if not self._graph.has_node(node_id):
            self._graph.add_node(node_id, kind=_KIND_CONCEPT, label=concept_label.lower().strip())

        self._graph.add_edge(chunk_id, node_id, kind=_EDGE_CONCEPT, weight=float(weight))

    # ── Artwork nodes ─────────────────────────────────────────────────────────

    def add_artwork_node(self, artwork_id: str, svg_path: str) -> None:
        """
        Add an ArtworkNode. Calling with the same artwork_id twice is a no-op.
        """
        node_id = _artwork_node_id(artwork_id)
        if not self._graph.has_node(node_id):
            self._graph.add_node(
                node_id,
                kind=_KIND_ARTWORK,
                artwork_id=artwork_id,
                svg_path=svg_path,
                created_at=datetime.now(timezone.utc).isoformat(),
            )

    def link_artwork(self, artwork_id: str, chunk_ids: list[str]) -> None:
        """
        Record which SourceNodes influenced this artwork.

        Adds a directed influence edge from the ArtworkNode to each source.
        chunk_ids not present in the graph are silently skipped.
        Raises ValueError if the ArtworkNode itself is not in the graph.
        """
        node_id = _artwork_node_id(artwork_id)
        if not self._graph.has_node(node_id):
            raise ValueError(f"Artwork node '{artwork_id}' not found — call add_artwork_node first")

        for chunk_id in chunk_ids:
            if self._graph.has_node(chunk_id):
                self._graph.add_edge(node_id, chunk_id, kind=_EDGE_INFLUENCE, weight=1.0)

    # ── Edge lifecycle ────────────────────────────────────────────────────────

    def decay_edges(self, factor: float = EDGE_DECAY_FACTOR) -> None:
        """
        Multiply every edge weight by factor.

        Decay prevents early associations from dominating indefinitely as the
        corpus grows and new artworks accumulate. Call once per generation cycle.
        """
        for _, _, data in self._graph.edges(data=True):
            data["weight"] *= factor

    def prune_edges(self, min_weight: float = MIN_EDGE_WEIGHT) -> None:
        """
        Remove edges whose weight has decayed below min_weight.

        Keeps the graph sparse so traversal stays fast at the 6,000+ node scale.
        """
        dead = [
            (u, v)
            for u, v, data in self._graph.edges(data=True)
            if data["weight"] < min_weight
        ]
        self._graph.remove_edges_from(dead)
        if dead:
            logger.debug("Pruned %d edges below weight %.4f", len(dead), min_weight)

    # ── Query ─────────────────────────────────────────────────────────────────

    def source_neighbors(self, chunk_id: str, k: int = 5) -> list[tuple[str, float]]:
        """
        Return the k SourceNodes most similar to chunk_id, by descending edge weight.

        Only follows similarity edges. Returns (chunk_id, weight) pairs.
        Returns [] if chunk_id is not in the graph or has no similarity edges.
        """
        if not self._graph.has_node(chunk_id):
            return []

        edges = [
            (nbr, data["weight"])
            for nbr, data in self._graph[chunk_id].items()
            if data.get("kind") == _EDGE_SIMILARITY
            and self._graph.nodes[nbr].get("kind") == _KIND_SOURCE
        ]
        edges.sort(key=lambda x: x[1], reverse=True)
        return edges[:k]

    def source_node_weights(self) -> list[tuple[str, float]]:
        """
        Return (chunk_id, weight) for every SourceNode in the graph.

        Weight is the total outgoing similarity edge weight — a proxy for how
        well-connected the node is. Isolated nodes receive weight 0.0 so they
        remain selectable but are deprioritised by weighted sampling.
        """
        results: list[tuple[str, float]] = []
        for node_id, attrs in self._graph.nodes(data=True):
            if attrs.get("kind") != _KIND_SOURCE:
                continue
            weight = sum(
                data["weight"]
                for _, data in self._graph[node_id].items()
                if data.get("kind") == _EDGE_SIMILARITY
            )
            results.append((node_id, weight))
        return results

    def concept_neighbors(self, chunk_id: str, k: int = 5) -> list[tuple[str, float]]:
        """
        Return the k ConceptNodes most strongly linked to chunk_id, by descending weight.

        Only follows concept edges originating at this node.
        Returns (concept_node_id, weight) pairs.
        Returns [] if chunk_id is not in the graph or has no concept edges.
        """
        if not self._graph.has_node(chunk_id):
            return []

        edges = [
            (nbr, data["weight"])
            for nbr, data in self._graph[chunk_id].items()
            if data.get("kind") == _EDGE_CONCEPT
            and self._graph.nodes[nbr].get("kind") == _KIND_CONCEPT
        ]
        edges.sort(key=lambda x: x[1], reverse=True)
        return edges[:k]

    # ── Talent cluster queries ────────────────────────────────────────────────

    def artwork_neighbors(
        self,
        chunk_ids: list[str],
        min_similarity: float = TALENT_SIMILARITY_THRESHOLD,
    ) -> list[str]:
        """
        Return artwork_ids whose source lineage is connected to chunk_ids at or
        above min_similarity.

        For each ArtworkNode the connection score is the maximum pairwise
        similarity between any of the artwork's source chunks and any of the
        given chunk_ids.  A direct chunk_id match counts as similarity 1.0.

        Only similarity edges are consulted — influence edges record lineage
        but carry no semantic weight.  Returns a list of bare artwork_ids
        (not the internal 'artwork:{id}' node key).
        """
        chunk_id_set = set(chunk_ids)
        results: list[str] = []

        for node_id, attrs in self._graph.nodes(data=True):
            if attrs.get("kind") != _KIND_ARTWORK:
                continue

            # Influence edges run artwork → source, so successors are source nodes
            art_sources = [
                nbr for nbr in self._graph.successors(node_id)
                if self._graph.nodes[nbr].get("kind") == _KIND_SOURCE
            ]
            if not art_sources:
                continue

            max_sim = 0.0
            for art_chunk in art_sources:
                if art_chunk in chunk_id_set:
                    max_sim = 1.0
                    break
                for param_chunk in chunk_ids:
                    for src, dst in [(art_chunk, param_chunk), (param_chunk, art_chunk)]:
                        edge = self._graph.get_edge_data(src, dst)
                        if edge and edge.get("kind") == _EDGE_SIMILARITY:
                            max_sim = max(max_sim, edge["weight"])
                if max_sim >= min_similarity:
                    break  # no need to check remaining art_sources

            if max_sim >= min_similarity:
                results.append(attrs["artwork_id"])

        return results

    def coactivate(
        self,
        chunk_ids: list[str],
        bump: float = COACTIVATION_BUMP,
    ) -> None:
        """
        Strengthen associations between every pair of source chunks in chunk_ids.

        When two source nodes co-occur in the same artwork their similarity edge
        weight is increased by bump (capped at 1.0).  If no similarity edge
        exists between the pair yet, one is created with weight=bump so future
        artworks can reinforce it further.

        chunk_ids that are not present in the graph are silently skipped.
        """
        from itertools import combinations
        present = [cid for cid in chunk_ids if self._graph.has_node(cid)]
        for a, b in combinations(present, 2):
            for src, dst in [(a, b), (b, a)]:
                existing = self._graph.get_edge_data(src, dst)
                if existing and existing.get("kind") == _EDGE_SIMILARITY:
                    existing["weight"] = min(1.0, existing["weight"] + bump)
                else:
                    self._graph.add_edge(src, dst, kind=_EDGE_SIMILARITY, weight=bump)

    # ── Serialisation ─────────────────────────────────────────────────────────

    def save(self) -> None:
        """Persist the graph to the configured JSON file."""
        if self._path is None:
            raise RuntimeError("Cannot save an in-memory graph — path was set to None")

        data = nx.node_link_data(self._graph, edges="links")
        path = Path(self._path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        logger.info(
            "Graph saved: %d nodes, %d edges → %s",
            self._graph.number_of_nodes(),
            self._graph.number_of_edges(),
            path,
        )

    def load(self) -> None:
        """Load the graph from the configured JSON file, replacing current state."""
        if self._path is None:
            raise RuntimeError("Cannot load an in-memory graph — path was set to None")

        path = Path(self._path)
        if not path.exists():
            logger.info("No graph file at %s — starting with empty graph", path)
            return

        data = json.loads(path.read_text(encoding="utf-8"))
        self._graph = nx.node_link_graph(data, directed=True, multigraph=False, edges="links")
        logger.info(
            "Graph loaded: %d nodes, %d edges ← %s",
            self._graph.number_of_nodes(),
            self._graph.number_of_edges(),
            path,
        )

    # ── Introspection ─────────────────────────────────────────────────────────

    def node_count(self) -> int:
        """Total number of nodes across all types."""
        return self._graph.number_of_nodes()

    def edge_count(self) -> int:
        """Total number of directed edges across all types."""
        return self._graph.number_of_edges()

    def node_data(self, node_id: str) -> dict | None:
        """
        Return a copy of the attribute dict for node_id, or None if absent.

        Used by the API layer to inspect individual nodes without exposing
        the internal NetworkX graph object.
        """
        if not self._graph.has_node(node_id):
            return None
        return dict(self._graph.nodes[node_id])

    def all_artwork_nodes(self) -> list[dict]:
        """
        Return attribute dicts for every ArtworkNode in the graph.

        Each dict contains at least: kind, artwork_id, svg_path, created_at.
        Ordered by creation time (ascending) so the portfolio is chronological.
        Used by the API portfolio endpoints (PRD 2.7).
        """
        nodes = [
            {"node_id": nid, **dict(attrs)}
            for nid, attrs in self._graph.nodes(data=True)
            if attrs.get("kind") == _KIND_ARTWORK
        ]
        nodes.sort(key=lambda n: n.get("created_at", ""))
        return nodes

    def artwork_source_nodes(self, artwork_id: str) -> list[str]:
        """
        Return the chunk_ids of SourceNodes that influenced this artwork.

        Traverses outgoing influence edges from the ArtworkNode. Returns an
        empty list if the artwork is not in the graph or has no influence edges.
        """
        node_id = _artwork_node_id(artwork_id)
        if not self._graph.has_node(node_id):
            return []
        return [
            target
            for target in self._graph.successors(node_id)
            if self._graph.edges[node_id, target].get("kind") == _EDGE_INFLUENCE
        ]

    def all_nodes_and_edges(
        self,
        top_k_similarity: int | None = None,
    ) -> tuple[list[dict], list[dict]]:
        """
        Return serialisable snapshots of every node and edge.

        Node dicts: {id, kind, ...attributes}
        Edge dicts: {source, target, kind, weight}
        Used by the GET /graph/state API endpoint (PRD 2.7).

        top_k_similarity: when set, only the top-K highest-weight similarity
        edges per source node are included.  Non-similarity edges (concept,
        influence) are always returned.  This is essential for browser rendering:
        the full similarity graph has O(n²) edges which is far too large to
        transfer or render in WebGL.
        """
        nodes = [
            {"id": nid, **dict(attrs)}
            for nid, attrs in self._graph.nodes(data=True)
        ]

        if top_k_similarity is None:
            edges = [
                {
                    "source": u,
                    "target": v,
                    "kind": data.get("kind", ""),
                    "weight": round(data.get("weight", 0.0), 6),
                }
                for u, v, data in self._graph.edges(data=True)
            ]
            return nodes, edges

        # For similarity edges, keep only the top-K outgoing per source node.
        # Concept and influence edges are always included — they are sparse by design.
        from collections import defaultdict
        similarity_candidates: dict[str, list[tuple[float, str, str]]] = defaultdict(list)
        non_similarity: list[dict] = []

        for u, v, data in self._graph.edges(data=True):
            kind = data.get("kind", "")
            weight = data.get("weight", 0.0)
            if kind == _EDGE_SIMILARITY:
                # (weight, source, target) — we sort descending by weight later
                similarity_candidates[u].append((weight, u, v))
            else:
                non_similarity.append({
                    "source": u,
                    "target": v,
                    "kind": kind,
                    "weight": round(weight, 6),
                })

        similarity_edges: list[dict] = []
        for candidates in similarity_candidates.values():
            candidates.sort(reverse=True)  # highest weight first
            for weight, u, v in candidates[:top_k_similarity]:
                similarity_edges.append({
                    "source": u,
                    "target": v,
                    "kind": _EDGE_SIMILARITY,
                    "weight": round(weight, 6),
                })

        return nodes, similarity_edges + non_similarity

    def __len__(self) -> int:
        return self.node_count()
