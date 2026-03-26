"""
Anonymous session model — PRD 2.3

A Session captures the ephemeral state of one browser tab's interaction with
the robot. Sessions live only in memory; once ended, only the artwork and
talent data they produced survive.

Public API:
  ParameterMode  — Literal["default", "user_directed"]
  Session        — dataclass
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from src.models.corpus import CorpusChunk

ParameterMode = Literal["default", "user_directed"]


@dataclass
class Session:
    """
    Ephemeral state for one anonymous browser session.

    session_id:      UUID4 string assigned at creation.
    started_at:      UTC datetime of session creation.
    parameter_mode:  "default"       → robot picks count randomly each cycle.
                     "user_directed" → user has fixed the count; parameter_count
                                       holds the chosen value (1–MAX_PARAMETERS).
    parameter_count: None in default mode; 1–MAX_PARAMETERS in user_directed mode.
    artworks:        Result dicts emitted by run_generation_cycle during this
                     session, in generation order.
    uploads:         CorpusChunks produced from user-uploaded documents.
                     Private until consent — never touches the shared graph or
                     corpus until the user agrees at session end (PRD 2.5).
    """

    session_id: str
    started_at: datetime
    parameter_mode: ParameterMode = "default"
    parameter_count: int | None = None
    artworks: list[dict] = field(default_factory=list)
    uploads: list[CorpusChunk] = field(default_factory=list)

    @property
    def is_private(self) -> bool:
        """
        True when the session has deviated from the public default experience.

        A session is private if the user has uploaded documents (which carry
        elevated weight in parameter selection) or has manually fixed the
        parameter count. Private sessions gate artwork into a holding state
        until consent is given at session end (PRD 2.4, 2.5).
        """
        return bool(self.uploads) or self.parameter_mode == "user_directed"
