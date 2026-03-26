"""
FastAPI application factory — PRD 2.7

create_app() builds the ASGI application.  Accepts an optional AppState
so tests can inject in-memory stubs without touching the database or disk.

Production startup:
  uvicorn src.api.app:app --host 0.0.0.0 --port 8000
"""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import router
from src.api.state import AppState, SSEBroadcaster
from src.controllers.session_manager import SessionManager
from src.models.graph import SemanticGraph
from src.models.trace_store import TraceStore

logger = logging.getLogger(__name__)


def create_app(state: AppState | None = None) -> FastAPI:
    """
    Build and return the FastAPI application.

    state: inject a pre-built AppState (tests).  When None, production
           defaults are used: graph loaded from disk, DB-backed stores.
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if state is not None:
            app_state = state
        else:
            app_state = AppState(
                graph=SemanticGraph(),
                session_manager=SessionManager(),
                trace_store=TraceStore(),
            )

        # Give the broadcaster a reference to the running event loop so the
        # generation timer thread can schedule queue writes on it.
        app_state.sse.set_loop(asyncio.get_running_loop())
        app.state.app_state = app_state
        logger.info("API startup complete")
        yield
        logger.info("API shutdown")

    app = FastAPI(
        title="HumanEvolutionAgent API",
        version="0.1.0",
        lifespan=lifespan,
    )
    # Allow the Vite dev server and any local origin to reach the API
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    return app


# Module-level app instance for uvicorn:
#   uvicorn src.api.app:app
app = create_app()
