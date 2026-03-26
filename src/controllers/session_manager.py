"""
In-memory session manager — PRD 2.3

Maintains the active session registry for the server process lifetime.
Sessions are created when a browser tab opens and removed when it closes;
only generated artwork and talent data outlive them.

One SessionManager instance should be shared across the FastAPI app (PRD 2.7).

Public API:
  SessionManager.create()                              → Session
  SessionManager.get(session_id)                       → Session | None
  SessionManager.end(session_id)                       → Session | None
  SessionManager.record_artwork(session_id, result)    → None
  SessionManager.set_parameter_mode(session_id, mode, count) → None
  SessionManager.add_upload(session_id, chunk)         → None
  SessionManager.active_count()                        → int
"""
import logging
import uuid
from datetime import datetime, timezone

from src.config.settings import MAX_PARAMETERS, MIN_PARAMETERS
from src.models.corpus import CorpusChunk
from src.models.session import ParameterMode, Session

logger = logging.getLogger(__name__)


class SessionManager:
    """
    Registry of active sessions, keyed by session UUID.

    All state is in-memory; the manager has no persistence of its own.
    Artwork and talent data persist through the graph and trace store,
    not through this registry.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    # ── Session lifecycle ─────────────────────────────────────────────────────

    def create(self) -> Session:
        """
        Create a new anonymous session and add it to the active registry.

        Returns the new Session so the caller can hand the session_id to the
        client (the browser tab keeps it for subsequent API calls).
        """
        session = Session(
            session_id=str(uuid.uuid4()),
            started_at=datetime.now(timezone.utc),
        )
        self._sessions[session.session_id] = session
        logger.info("Session created: %s", session.session_id)
        return session

    def get(self, session_id: str) -> Session | None:
        """Return the active session, or None if it no longer exists."""
        return self._sessions.get(session_id)

    def end(self, session_id: str) -> Session | None:
        """
        Remove the session from the active registry and return it.

        The returned Session carries all artwork results and uploads so the
        caller can run the consent flow (PRD 2.5) before discarding the object.
        Returns None if the session was not found (already ended or never created).
        """
        session = self._sessions.pop(session_id, None)
        if session is not None:
            logger.info(
                "Session ended: %s — %d artworks, %d uploads",
                session_id,
                len(session.artworks),
                len(session.uploads),
            )
        return session

    # ── State mutations ───────────────────────────────────────────────────────

    def record_artwork(self, session_id: str, result: dict) -> None:
        """
        Append a generation result dict to the session's artwork list.

        No-ops silently when the session no longer exists — this can happen
        in a race between tab close and the final generation cycle completing.
        """
        session = self._sessions.get(session_id)
        if session is not None:
            session.artworks.append(result)

    def set_parameter_mode(
        self,
        session_id: str,
        mode: ParameterMode,
        count: int | None = None,
    ) -> None:
        """
        Update the session's parameter selection mode.

        mode="default":       count must be None — robot picks count randomly.
        mode="user_directed": count must be in [MIN_PARAMETERS, MAX_PARAMETERS].

        Raises ValueError for an unknown session_id or an invalid mode/count
        combination.
        """
        session = self._sessions.get(session_id)
        if session is None:
            raise ValueError(f"Session not found: {session_id!r}")

        if mode == "user_directed":
            if count is None or not (MIN_PARAMETERS <= count <= MAX_PARAMETERS):
                raise ValueError(
                    f"user_directed mode requires count in "
                    f"[{MIN_PARAMETERS}, {MAX_PARAMETERS}], got {count!r}"
                )
        else:  # "default"
            if count is not None:
                raise ValueError(
                    f"default mode does not accept a fixed count, got {count!r}"
                )
            count = None  # normalise — caller may have passed count=None explicitly

        session.parameter_mode = mode
        session.parameter_count = count

    def add_upload(self, session_id: str, chunk: CorpusChunk) -> None:
        """
        Append a user-uploaded CorpusChunk to the session's private upload list.

        Raises ValueError if the session is not active.
        """
        session = self._sessions.get(session_id)
        if session is None:
            raise ValueError(f"Session not found: {session_id!r}")
        session.uploads.append(chunk)

    # ── Introspection ─────────────────────────────────────────────────────────

    def active_count(self) -> int:
        """Return the number of currently active (not yet ended) sessions."""
        return len(self._sessions)
