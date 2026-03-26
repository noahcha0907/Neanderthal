"""
Shared application state — PRD 2.7

AppState carries all long-lived objects that route handlers need.
SSEBroadcaster bridges the synchronous generation-timer thread with
async SSE subscribers running in the FastAPI event loop.
"""
import asyncio
import json
import logging
from dataclasses import dataclass, field

from src.controllers.session_manager import SessionManager
from src.models.graph import SemanticGraph
from src.models.trace_store import TraceStore

logger = logging.getLogger(__name__)


class SSEBroadcaster:
    """
    Thread-safe broadcast of server-sent events to async subscribers.

    The generation timer runs in a daemon thread; SSE consumers are
    async coroutines in the event loop.  call_soon_threadsafe bridges
    the two worlds so artwork-ready notifications reach all live clients.
    """

    def __init__(self) -> None:
        self._subscribers: list[asyncio.Queue] = []
        self._loop: asyncio.AbstractEventLoop | None = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Capture the running event loop so broadcast() can schedule work on it."""
        self._loop = loop

    def subscribe(self) -> asyncio.Queue:
        """Register a new subscriber queue; returned to the SSE endpoint."""
        q: asyncio.Queue = asyncio.Queue()
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        """Remove a subscriber queue when its client disconnects."""
        try:
            self._subscribers.remove(q)
        except ValueError:
            pass

    def broadcast(self, event_type: str, payload: dict) -> None:
        """
        Push an SSE-formatted message to every subscriber.

        Safe to call from any thread — uses call_soon_threadsafe to
        schedule the queue writes on the event loop.
        """
        if self._loop is None or not self._loop.is_running():
            logger.warning(
                "broadcast(%s): loop not running (loop=%s)", event_type, self._loop
            )
            return
        message = "data: " + json.dumps({"type": event_type, **payload}) + "\n\n"
        for q in list(self._subscribers):
            self._loop.call_soon_threadsafe(q.put_nowait, message)


@dataclass
class AppState:
    """
    Container for all shared server-side state.

    One instance lives for the duration of the FastAPI process; route
    handlers receive it via the get_state dependency.
    """
    graph: SemanticGraph
    session_manager: SessionManager
    trace_store: TraceStore
    sse: SSEBroadcaster = field(default_factory=SSEBroadcaster)
