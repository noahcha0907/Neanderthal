"""
Session end consent flow — PRD 2.5

Processes the binary consent decisions a user makes when ending a session:
  1. Artwork consent: ingest private-session artworks into the shared talent pool
  2. Document consent: add user-uploaded documents to the shared corpus and graph

Both decisions are independent — a user can consent to one but not the other.
Data for a rejected consent is discarded immediately; nothing is retained.

Public API:
  ConsentResult              — dataclass: artworks_ingested, documents_added
  process_consent(session, artwork_consent, document_consent,
                  graph, chunk_store, corpus_ingest_fn) → ConsentResult
"""
import logging
from dataclasses import dataclass
from typing import Callable

from src.models.corpus import ChunkStore, CorpusChunk
from src.models.graph import SemanticGraph
from src.models.session import Session

logger = logging.getLogger(__name__)


@dataclass
class ConsentResult:
    """
    Summary of what was committed during consent processing.

    artworks_ingested: number of artwork nodes added to the shared graph.
    documents_added:   number of uploaded corpus chunks added to the shared
                       corpus and graph.
    """
    artworks_ingested: int
    documents_added: int


def process_consent(
    session: Session,
    artwork_consent: bool,
    document_consent: bool,
    graph: SemanticGraph,
    chunk_store: ChunkStore | None = None,
    corpus_ingest_fn: Callable[[list[CorpusChunk]], None] | None = None,
) -> ConsentResult:
    """
    Execute the user's consent decisions at session end.

    artwork_consent=True:
        Ingest every artwork from session.artworks into the shared graph —
        add an ArtworkNode, link it to its voter source chunks via influence
        edges, and bump co-activation weights for co-occurring source pairs.
        Each result dict in session.artworks must contain a "voter_ids" key
        (list[str]) produced by run_generation_cycle.

    document_consent=True:
        Persist each uploaded CorpusChunk to chunk_store (if provided), add
        its SourceNode to the graph, and call corpus_ingest_fn (if provided)
        for the downstream embedding and edge-building pipeline (PRD 1.2–1.3).
        Injecting corpus_ingest_fn as a callable keeps this module decoupled
        from the embedding layer.

    artwork_consent=False / document_consent=False:
        The respective data is silently discarded — not stored anywhere.

    Both decisions are independent: consenting to one does not affect the other.
    """
    artworks_ingested = 0
    documents_added = 0
    graph_dirty = False

    # ── 1. Artwork consent ────────────────────────────────────────────────────

    if artwork_consent:
        for result in session.artworks:
            artwork_id = result["artwork_id"]
            svg_path = result["svg_path"]
            voter_ids: list[str] = result.get("voter_ids", [])

            graph.add_artwork_node(artwork_id, svg_path)
            graph.link_artwork(artwork_id, voter_ids)
            if len(voter_ids) > 1:
                graph.coactivate(voter_ids)

            artworks_ingested += 1
            graph_dirty = True

        logger.info(
            "Consent: %d artwork(s) ingested from session %s",
            artworks_ingested,
            session.session_id,
        )

    # ── 2. Document consent ───────────────────────────────────────────────────

    if document_consent and session.uploads:
        for chunk in session.uploads:
            if chunk_store is not None:
                chunk_store.add(chunk)
            graph.add_source_node(chunk)
            documents_added += 1
            graph_dirty = True

        if chunk_store is not None:
            chunk_store.commit()

        if corpus_ingest_fn is not None:
            corpus_ingest_fn(list(session.uploads))

        logger.info(
            "Consent: %d document chunk(s) added to shared corpus from session %s",
            documents_added,
            session.session_id,
        )

    # ── 3. Persist graph if modified ──────────────────────────────────────────
    # In-memory graphs (path=None, used in tests) are never saved to disk.

    if graph_dirty and graph._path is not None:
        graph.save()

    return ConsentResult(
        artworks_ingested=artworks_ingested,
        documents_added=documents_added,
    )
