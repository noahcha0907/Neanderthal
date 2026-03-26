"""
Unit tests for session model and session manager — PRD 2.3

Covers:
  - Session: default state, is_private logic
  - SessionManager: full lifecycle (create, get, end), state mutations,
    validation errors, multi-session independence, active_count
"""
import pytest

from src.config.settings import MAX_PARAMETERS, MIN_PARAMETERS
from src.controllers.session_manager import SessionManager
from src.models.corpus import CorpusChunk
from src.models.session import Session


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_chunk(chunk_id: str = "chunk_a") -> CorpusChunk:
    return CorpusChunk(
        chunk_id=chunk_id,
        source_path="data/test.txt",
        title="Test",
        author="Author",
        doc_type="literary",
        year=2024,
        chunk_index=0,
        text="Sample text.",
        chunk_strategy="paragraph",
    )


def make_result(artwork_id: str = "art_1") -> dict:
    return {
        "artwork_id": artwork_id,
        "svg_path": f"data/talent/{artwork_id}.svg",
        "trace_text": "trace",
        "voter_count": 2,
    }


# ── Session model ─────────────────────────────────────────────────────────────

def test_session_has_correct_id_and_time():
    from datetime import datetime, timezone
    t_before = datetime.now(timezone.utc)
    mgr = SessionManager()
    session = mgr.create()
    t_after = datetime.now(timezone.utc)
    assert session.session_id  # non-empty string
    assert t_before <= session.started_at <= t_after


def test_session_default_mode():
    mgr = SessionManager()
    session = mgr.create()
    assert session.parameter_mode == "default"
    assert session.parameter_count is None


def test_session_empty_artworks_and_uploads():
    mgr = SessionManager()
    session = mgr.create()
    assert session.artworks == []
    assert session.uploads == []


def test_session_is_not_private_by_default():
    mgr = SessionManager()
    session = mgr.create()
    assert not session.is_private


def test_session_is_private_with_uploads():
    mgr = SessionManager()
    session = mgr.create()
    session.uploads.append(make_chunk())
    assert session.is_private


def test_session_is_private_in_user_directed_mode():
    mgr = SessionManager()
    session = mgr.create()
    session.parameter_mode = "user_directed"
    session.parameter_count = MIN_PARAMETERS
    assert session.is_private


def test_session_is_private_with_both():
    mgr = SessionManager()
    session = mgr.create()
    session.parameter_mode = "user_directed"
    session.parameter_count = 3
    session.uploads.append(make_chunk())
    assert session.is_private


# ── SessionManager.create ─────────────────────────────────────────────────────

def test_create_returns_session():
    mgr = SessionManager()
    session = mgr.create()
    assert isinstance(session, Session)


def test_create_assigns_unique_ids():
    mgr = SessionManager()
    ids = {mgr.create().session_id for _ in range(10)}
    assert len(ids) == 10


def test_create_increments_active_count():
    mgr = SessionManager()
    assert mgr.active_count() == 0
    mgr.create()
    assert mgr.active_count() == 1
    mgr.create()
    assert mgr.active_count() == 2


# ── SessionManager.get ────────────────────────────────────────────────────────

def test_get_returns_created_session():
    mgr = SessionManager()
    session = mgr.create()
    assert mgr.get(session.session_id) is session


def test_get_unknown_returns_none():
    mgr = SessionManager()
    assert mgr.get("does-not-exist") is None


# ── SessionManager.end ────────────────────────────────────────────────────────

def test_end_returns_session():
    mgr = SessionManager()
    session = mgr.create()
    returned = mgr.end(session.session_id)
    assert returned is session


def test_end_removes_session_from_registry():
    mgr = SessionManager()
    session = mgr.create()
    mgr.end(session.session_id)
    assert mgr.get(session.session_id) is None


def test_end_decrements_active_count():
    mgr = SessionManager()
    session = mgr.create()
    mgr.end(session.session_id)
    assert mgr.active_count() == 0


def test_end_unknown_returns_none():
    mgr = SessionManager()
    assert mgr.end("no-such-session") is None


def test_end_returns_session_with_artworks():
    mgr = SessionManager()
    session = mgr.create()
    mgr.record_artwork(session.session_id, make_result("art_1"))
    ended = mgr.end(session.session_id)
    assert len(ended.artworks) == 1


# ── SessionManager.record_artwork ────────────────────────────────────────────

def test_record_artwork_appends():
    mgr = SessionManager()
    session = mgr.create()
    mgr.record_artwork(session.session_id, make_result("art_1"))
    assert len(session.artworks) == 1
    assert session.artworks[0]["artwork_id"] == "art_1"


def test_record_artwork_multiple():
    mgr = SessionManager()
    session = mgr.create()
    for i in range(3):
        mgr.record_artwork(session.session_id, make_result(f"art_{i}"))
    assert len(session.artworks) == 3


def test_record_artwork_unknown_session_is_noop():
    mgr = SessionManager()
    # Must not raise
    mgr.record_artwork("ghost-session", make_result())


# ── SessionManager.set_parameter_mode ────────────────────────────────────────

def test_set_parameter_mode_default():
    mgr = SessionManager()
    session = mgr.create()
    # Switch to user_directed first, then back to default
    mgr.set_parameter_mode(session.session_id, "user_directed", MIN_PARAMETERS)
    mgr.set_parameter_mode(session.session_id, "default")
    assert session.parameter_mode == "default"
    assert session.parameter_count is None


def test_set_parameter_mode_user_directed():
    mgr = SessionManager()
    session = mgr.create()
    mgr.set_parameter_mode(session.session_id, "user_directed", 3)
    assert session.parameter_mode == "user_directed"
    assert session.parameter_count == 3


def test_set_parameter_mode_user_directed_min_boundary():
    mgr = SessionManager()
    session = mgr.create()
    mgr.set_parameter_mode(session.session_id, "user_directed", MIN_PARAMETERS)
    assert session.parameter_count == MIN_PARAMETERS


def test_set_parameter_mode_user_directed_max_boundary():
    mgr = SessionManager()
    session = mgr.create()
    mgr.set_parameter_mode(session.session_id, "user_directed", MAX_PARAMETERS)
    assert session.parameter_count == MAX_PARAMETERS


def test_set_parameter_mode_user_directed_no_count_raises():
    mgr = SessionManager()
    session = mgr.create()
    with pytest.raises(ValueError):
        mgr.set_parameter_mode(session.session_id, "user_directed")


def test_set_parameter_mode_user_directed_out_of_range_raises():
    mgr = SessionManager()
    session = mgr.create()
    with pytest.raises(ValueError):
        mgr.set_parameter_mode(session.session_id, "user_directed", MAX_PARAMETERS + 1)
    with pytest.raises(ValueError):
        mgr.set_parameter_mode(session.session_id, "user_directed", MIN_PARAMETERS - 1)


def test_set_parameter_mode_default_with_count_raises():
    mgr = SessionManager()
    session = mgr.create()
    with pytest.raises(ValueError):
        mgr.set_parameter_mode(session.session_id, "default", count=3)


def test_set_parameter_mode_unknown_session_raises():
    mgr = SessionManager()
    with pytest.raises(ValueError):
        mgr.set_parameter_mode("ghost", "default")


# ── SessionManager.add_upload ─────────────────────────────────────────────────

def test_add_upload_appends():
    mgr = SessionManager()
    session = mgr.create()
    chunk = make_chunk("upload_1")
    mgr.add_upload(session.session_id, chunk)
    assert len(session.uploads) == 1
    assert session.uploads[0].chunk_id == "upload_1"


def test_add_upload_multiple():
    mgr = SessionManager()
    session = mgr.create()
    for i in range(4):
        mgr.add_upload(session.session_id, make_chunk(f"upload_{i}"))
    assert len(session.uploads) == 4


def test_add_upload_unknown_session_raises():
    mgr = SessionManager()
    with pytest.raises(ValueError):
        mgr.add_upload("ghost", make_chunk())


def test_add_upload_makes_session_private():
    mgr = SessionManager()
    session = mgr.create()
    assert not session.is_private
    mgr.add_upload(session.session_id, make_chunk())
    assert session.is_private


# ── Multi-session independence ────────────────────────────────────────────────

def test_multiple_sessions_independent():
    mgr = SessionManager()
    s1 = mgr.create()
    s2 = mgr.create()
    mgr.record_artwork(s1.session_id, make_result("art_for_s1"))
    mgr.add_upload(s2.session_id, make_chunk("upload_for_s2"))
    assert len(s1.artworks) == 1 and len(s2.artworks) == 0
    assert len(s2.uploads) == 1 and len(s1.uploads) == 0


def test_ending_one_session_leaves_others_intact():
    mgr = SessionManager()
    s1 = mgr.create()
    s2 = mgr.create()
    mgr.end(s1.session_id)
    assert mgr.get(s2.session_id) is s2
    assert mgr.active_count() == 1
