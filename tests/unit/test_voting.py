"""
Unit tests for the parameter voting engine — PRD 1.5

All tests are purely in-memory: no database, no filesystem, no graph required.
Inputs are (chunk_id, weight) pairs; output is an ArtParameters instance.
"""
import pytest

from src.config.settings import (
    COLOR_PALETTE,
    MAX_SHAPES,
    MIN_SHAPES,
    SHAPE_TYPES,
    STROKE_WIDTHS,
)
from src.models.art_params import ArtParameters, ShapeParams
from src.models.voting import (
    _hash_choice,
    _hash_float,
    _weighted_average,
    _weighted_plurality,
    vote_on_parameters,
)

_COLOR_VALUES = list(COLOR_PALETTE.values())
_STROKE_VALUES = sorted(STROKE_WIDTHS.values())


# ── _hash_float ───────────────────────────────────────────────────────────────

def test_hash_float_is_in_unit_range():
    """_hash_float always returns a value in [0.0, 1.0)."""
    for chunk_id in ["abc", "xyz", "0" * 64, "a" * 64]:
        for key in ["x", "y", "shape_count", "background_color"]:
            v = _hash_float(chunk_id, key)
            assert 0.0 <= v < 1.0, f"Out of range for chunk_id={chunk_id!r}, key={key!r}"


def test_hash_float_is_deterministic():
    """Same inputs always yield the same float."""
    assert _hash_float("chunk_abc", "fill") == _hash_float("chunk_abc", "fill")


def test_hash_float_varies_by_key():
    """Different keys produce different values for the same chunk_id."""
    a = _hash_float("chunk_abc", "key_a")
    b = _hash_float("chunk_abc", "key_b")
    assert a != b


def test_hash_float_varies_by_chunk_id():
    """Different chunk_ids produce different values for the same key."""
    a = _hash_float("chunk_001", "x")
    b = _hash_float("chunk_002", "x")
    assert a != b


# ── _hash_choice ──────────────────────────────────────────────────────────────

def test_hash_choice_returns_element_from_options():
    """_hash_choice always returns one of the provided options."""
    for _ in range(20):
        result = _hash_choice("some_id", "type", SHAPE_TYPES)
        assert result in SHAPE_TYPES


def test_hash_choice_is_deterministic():
    """Same chunk_id and key always pick the same element."""
    assert (
        _hash_choice("chunk_abc", "fill", _COLOR_VALUES)
        == _hash_choice("chunk_abc", "fill", _COLOR_VALUES)
    )


def test_hash_choice_covers_options():
    """Given enough distinct chunk_ids, all options are eventually selected."""
    seen = set()
    for i in range(200):
        seen.add(_hash_choice(f"chunk_{i:04d}", "fill", _COLOR_VALUES))
    assert seen == set(_COLOR_VALUES)


# ── _weighted_average ─────────────────────────────────────────────────────────

def test_weighted_average_equal_weights():
    """Equal-weight proposals return the arithmetic mean."""
    result = _weighted_average([(0.2, 0.5), (0.8, 0.5)])
    assert result == pytest.approx(0.5)


def test_weighted_average_skewed_weights():
    """Higher weight pulls the average toward that voter's proposal."""
    # 0.9 weight on 1.0, 0.1 weight on 0.0
    result = _weighted_average([(1.0, 0.9), (0.0, 0.1)])
    assert result == pytest.approx(0.9)


def test_weighted_average_single_voter():
    """Single voter returns its own value unchanged."""
    assert _weighted_average([(0.37, 1.0)]) == pytest.approx(0.37)


# ── _weighted_plurality ───────────────────────────────────────────────────────

def test_weighted_plurality_returns_highest_weight_option():
    """The option with the most total weight wins."""
    proposals = [("red", 0.6), ("blue", 0.3), ("red", 0.1)]
    assert _weighted_plurality(proposals) == "red"


def test_weighted_plurality_single_voter():
    """A single voter's choice is always selected."""
    assert _weighted_plurality([("circle", 1.0)]) == "circle"


def test_weighted_plurality_all_different():
    """When all options differ, the highest individual weight wins."""
    proposals = [("circle", 0.5), ("square", 0.3), ("triangle", 0.2)]
    assert _weighted_plurality(proposals) == "circle"


# ── vote_on_parameters — basic contract ───────────────────────────────────────

def test_vote_raises_for_empty_voters():
    """Passing an empty voter list raises ValueError."""
    with pytest.raises(ValueError):
        vote_on_parameters([])


def test_vote_returns_art_parameters():
    """vote_on_parameters always returns an ArtParameters instance."""
    result = vote_on_parameters([("chunk_abc", 1.0)])
    assert isinstance(result, ArtParameters)


def test_vote_single_voter_produces_valid_output():
    """A single voter produces a fully valid ArtParameters."""
    result = vote_on_parameters([("chunk_single", 1.0)])
    assert MIN_SHAPES <= len(result.shapes) <= MAX_SHAPES
    assert result.background_color.startswith("#")
    for shape in result.shapes:
        assert isinstance(shape, ShapeParams)


def test_vote_shapes_have_valid_parameters():
    """Every shape in the output passes all ShapeParams constraints."""
    result = vote_on_parameters([("chunk_a", 0.7), ("chunk_b", 0.3)])
    for shape in result.shapes:
        assert shape.shape_type in SHAPE_TYPES
        assert shape.fill_color in _COLOR_VALUES
        assert shape.stroke_color in _COLOR_VALUES
        assert shape.stroke_width in _STROKE_VALUES
        assert 0.0 <= shape.x <= 1.0
        assert 0.0 <= shape.y <= 1.0
        assert 0.0 <= shape.size <= 1.0
        assert 0.0 <= shape.opacity <= 1.0


def test_vote_shape_count_always_in_bounds():
    """Shape count is always within [MIN_SHAPES, MAX_SHAPES]."""
    for seed in range(30):
        result = vote_on_parameters([(f"chunk_{seed:04d}", 1.0)])
        assert MIN_SHAPES <= len(result.shapes) <= MAX_SHAPES


# ── vote_on_parameters — determinism ─────────────────────────────────────────

def test_vote_is_deterministic():
    """Same voter list always produces an identical ArtParameters."""
    voters = [("chunk_x", 0.6), ("chunk_y", 0.4)]
    r1 = vote_on_parameters(voters)
    r2 = vote_on_parameters(voters)

    assert r1.background_color == r2.background_color
    assert len(r1.shapes) == len(r2.shapes)
    for s1, s2 in zip(r1.shapes, r2.shapes):
        assert s1 == s2


def test_vote_weight_normalisation_does_not_change_result():
    """Scaling all weights by a constant does not change the outcome."""
    voters_unit = [("chunk_a", 0.7), ("chunk_b", 0.3)]
    voters_scaled = [("chunk_a", 7.0), ("chunk_b", 3.0)]

    r1 = vote_on_parameters(voters_unit)
    r2 = vote_on_parameters(voters_scaled)

    assert r1.background_color == r2.background_color
    assert len(r1.shapes) == len(r2.shapes)
    for s1, s2 in zip(r1.shapes, r2.shapes):
        assert s1 == s2


def test_different_voters_produce_different_results():
    """Distinct voter sets (very likely) produce distinct artwork."""
    r1 = vote_on_parameters([("aaaa_chunk", 1.0)])
    r2 = vote_on_parameters([("zzzz_chunk", 1.0)])
    # Not guaranteed to differ on every field, but the full parameter sets
    # should differ since the hash seeds are completely different.
    dicts_differ = r1.to_dict() != r2.to_dict()
    assert dicts_differ, "Expected distinct chunks to produce distinct parameters"


# ── vote_on_parameters — weight influence ─────────────────────────────────────

def test_dominant_voter_steers_result():
    """A voter with 99% weight should dominate the outcome."""
    dominant_id = "dominant_chunk"
    minority_id = "minority_chunk"

    # Run with dominant voter at full weight
    solo = vote_on_parameters([(dominant_id, 1.0)])
    # Run with the same dominant voter plus a tiny minority weight
    combined = vote_on_parameters([(dominant_id, 0.99), (minority_id, 0.01)])

    # Discrete fields use weighted plurality — the dominant voter wins
    assert solo.background_color == combined.background_color
    assert len(solo.shapes) == len(combined.shapes)
    for s1, s2 in zip(solo.shapes, combined.shapes):
        assert s1.shape_type   == s2.shape_type
        assert s1.fill_color   == s2.fill_color
        assert s1.stroke_color == s2.stroke_color
        assert s1.stroke_width == s2.stroke_width

    # Continuous fields use weighted average — the 1% minority shifts values
    # slightly, so we only assert they are very close (within 2%)
    for s1, s2 in zip(solo.shapes, combined.shapes):
        assert s1.x       == pytest.approx(s2.x,       abs=0.02)
        assert s1.y       == pytest.approx(s2.y,       abs=0.02)
        assert s1.size    == pytest.approx(s2.size,    abs=0.02)
        assert s1.opacity == pytest.approx(s2.opacity, abs=0.02)


# ── round-trip through ArtParameters serialisation ────────────────────────────

def test_vote_output_survives_serialisation_roundtrip():
    """ArtParameters produced by voting can be serialised and restored intact."""
    result = vote_on_parameters([("chunk_rt", 0.5), ("chunk_rt2", 0.5)])
    restored = ArtParameters.from_dict(result.to_dict())

    assert restored.artwork_id       == result.artwork_id
    assert restored.background_color == result.background_color
    assert len(restored.shapes)      == len(result.shapes)
    for s1, s2 in zip(result.shapes, restored.shapes):
        assert s1 == s2
