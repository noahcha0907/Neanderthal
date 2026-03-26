"""
Autonomous generation timer — PRD 2.2

GenerationTimer runs the artwork generation cycle on a continuous interval
inside a daemon thread. It starts when a session goes active and stops when
the session ends.

Cycle timing behaviour:
  - If a cycle completes in less than the interval, the timer waits out the
    remainder before starting the next cycle.
  - If a cycle takes longer than the interval, the next cycle starts
    immediately — no overlapping cycles, no skipped work.
  - Stopping the timer is responsive: it interrupts the inter-cycle wait
    rather than waiting for the full interval to expire.

Public API:
  GenerationTimer(graph, chunk_store, trace_store, output_dir, interval)
  GenerationTimer.start(on_artwork_ready, seed)  → None
  GenerationTimer.stop(timeout)                  → None
  GenerationTimer.is_running                     → bool
"""
import logging
import random
import threading
import time
from pathlib import Path
from typing import Callable

from src.config.settings import GENERATION_INTERVAL_SECONDS, TALENT_DIR
from src.controllers.generation_cycle import run_generation_cycle
from src.models.corpus import ChunkStore
from src.models.graph import SemanticGraph
from src.models.trace_store import TraceStore

logger = logging.getLogger(__name__)


class GenerationTimer:
    """
    Drives autonomous artwork generation at a configurable interval.

    Pass an on_artwork_ready callback to receive each completed result dict;
    this is the hook point for SSE emission in PRD 2.7.
    """

    def __init__(
        self,
        graph: SemanticGraph,
        chunk_store: ChunkStore,
        trace_store: TraceStore,
        output_dir: Path = TALENT_DIR,
        interval: float = GENERATION_INTERVAL_SECONDS,
    ) -> None:
        self._graph = graph
        self._chunk_store = chunk_store
        self._trace_store = trace_store
        self._output_dir = Path(output_dir)
        self._interval = interval
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    # ── Public API ────────────────────────────────────────────────────────────

    @property
    def is_running(self) -> bool:
        """True while the generation loop thread is alive."""
        return self._thread is not None and self._thread.is_alive()

    def start(
        self,
        on_artwork_ready: Callable[[dict], None] | None = None,
        seed: int | None = None,
    ) -> None:
        """
        Launch the generation loop in a background daemon thread.

        on_artwork_ready: called after each successful cycle with the result
                          dict {artwork_id, svg_path, trace_text, voter_count}.
        seed: optional RNG seed for reproducible generation sequences — useful
              in integration tests and demo scenarios.

        Raises RuntimeError if the timer is already running.
        """
        if self.is_running:
            raise RuntimeError("GenerationTimer is already running")
        self._stop_event.clear()
        rng = random.Random(seed)
        self._thread = threading.Thread(
            target=self._loop,
            args=(on_artwork_ready, rng),
            daemon=True,
            name="generation-timer",
        )
        self._thread.start()
        logger.info(
            "GenerationTimer started: interval=%.1fs, seed=%s",
            self._interval, seed,
        )

    def stop(self, timeout: float = 10.0) -> None:
        """
        Signal the loop to stop and wait for it to finish.

        Interrupts the inter-cycle sleep immediately; the current cycle (if
        running) completes before the thread exits.
        """
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            self._thread = None
        logger.info("GenerationTimer stopped")

    # ── Internal loop ─────────────────────────────────────────────────────────

    def _loop(
        self,
        on_artwork_ready: Callable[[dict], None] | None,
        rng: random.Random,
    ) -> None:
        while not self._stop_event.is_set():
            t_start = time.monotonic()

            try:
                # Load fresh corpus snapshot each cycle — picks up any new
                # user uploads added during the session (PRD 2.6)
                chunks = {c.chunk_id: c for c in self._chunk_store.all_chunks()}
                run_generation_cycle(
                    graph=self._graph,
                    chunks=chunks,
                    trace_store=self._trace_store,
                    output_dir=self._output_dir,
                    on_artwork_ready=on_artwork_ready,
                    rng=rng,
                )
            except Exception:
                logger.exception("Generation cycle failed — continuing")

            elapsed = time.monotonic() - t_start
            remaining = max(0.0, self._interval - elapsed)
            # wait() is interruptible: returns True immediately when stop() is called
            self._stop_event.wait(timeout=remaining)
