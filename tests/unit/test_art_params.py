"""
Unit tests for the art parameter system — PRD 1.4

Covers ShapeParams, ArtParameters, and the pure validation helpers.
No database or filesystem access required.
"""
import uuid

import pytest

from src.config.settings import CANVAS_HEIGHT, CANVAS_WIDTH, MAX_SHAPES, MIN_SHAPES
from src.helpers.param_validators import (
    validate_hex_color,
    validate_shape_type,
    validate_stroke_width,
    validate_unit_float,
)
from src.models.art_params import ArtParameters, ShapeParams


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_shape(**overrides) -> ShapeParams:
    """Return a valid ShapeParams, optionally overriding specific fields."""
    defaults = dict(
        shape_type="circle",
        fill_color="#FF0000",
        stroke_color="#000000",
        stroke_width=1,
        x=0.5,
        y=0.5,
        size=0.2,
        opacity=1.0,
    )
    defaults.update(overrides)
    return ShapeParams(**defaults)


def make_params(**overrides) -> ArtParameters:
    """Return a valid ArtParameters with one default shape."""
    defaults = dict(
        background_color="#FFFFFF",
        shapes=[make_shape()],
    )
    defaults.update(overrides)
    return ArtParameters(**defaults)


# ── validate_hex_color ────────────────────────────────────────────────────────

@pytest.mark.parametrize("color", ["#FF0000", "#000000", "#aAbBcC", "#FFFFFF"])
def test_validate_hex_color_accepts_valid(color):
    assert validate_hex_color(color) == color


@pytest.mark.parametrize("color", [
    "FF0000",      # missing #
    "#FF00",       # too short
    "#FF000000",   # too long
    "#GGGGGG",     # invalid hex digits
    "",
    123,
])
def test_validate_hex_color_rejects_invalid(color):
    with pytest.raises(ValueError):
        validate_hex_color(color)


# ── validate_unit_float ───────────────────────────────────────────────────────

@pytest.mark.parametrize("v", [0.0, 0.5, 1.0])
def test_validate_unit_float_accepts_bounds(v):
    assert validate_unit_float(v) == v


@pytest.mark.parametrize("v", [-0.001, 1.001, -1.0, 2.0])
def test_validate_unit_float_rejects_out_of_range(v):
    with pytest.raises(ValueError):
        validate_unit_float(v, "test_field")


def test_validate_unit_float_includes_name_in_message():
    with pytest.raises(ValueError, match="my_field"):
        validate_unit_float(2.0, "my_field")


# ── validate_shape_type ───────────────────────────────────────────────────────

@pytest.mark.parametrize("shape", ["circle", "square", "rectangle", "triangle", "star", "line"])
def test_validate_shape_type_accepts_all_known_types(shape):
    assert validate_shape_type(shape) == shape


def test_validate_shape_type_rejects_unknown():
    with pytest.raises(ValueError):
        validate_shape_type("hexagon")


# ── validate_stroke_width ─────────────────────────────────────────────────────

@pytest.mark.parametrize("width", [1, 3, 6])
def test_validate_stroke_width_accepts_valid(width):
    assert validate_stroke_width(width) == width


@pytest.mark.parametrize("width", [0, 2, 5, 10])
def test_validate_stroke_width_rejects_invalid(width):
    with pytest.raises(ValueError):
        validate_stroke_width(width)


# ── ShapeParams construction ──────────────────────────────────────────────────

def test_shape_params_valid_construction():
    """A fully valid ShapeParams is constructed without error."""
    shape = make_shape()
    assert shape.shape_type == "circle"
    assert shape.fill_color == "#FF0000"
    assert shape.x == 0.5


def test_shape_params_rejects_invalid_shape_type():
    with pytest.raises(ValueError, match="shape_type"):
        make_shape(shape_type="oval")


def test_shape_params_rejects_invalid_fill_color():
    with pytest.raises(ValueError):
        make_shape(fill_color="red")


def test_shape_params_rejects_invalid_stroke_color():
    with pytest.raises(ValueError):
        make_shape(stroke_color="#ZZZZZZ")


def test_shape_params_rejects_invalid_stroke_width():
    with pytest.raises(ValueError):
        make_shape(stroke_width=2)


def test_shape_params_rejects_x_out_of_range():
    with pytest.raises(ValueError):
        make_shape(x=1.5)


def test_shape_params_rejects_y_out_of_range():
    with pytest.raises(ValueError):
        make_shape(y=-0.1)


def test_shape_params_rejects_size_out_of_range():
    with pytest.raises(ValueError):
        make_shape(size=1.01)


def test_shape_params_rejects_opacity_out_of_range():
    with pytest.raises(ValueError):
        make_shape(opacity=1.5)


# ── ShapeParams serialisation ─────────────────────────────────────────────────

def test_shape_params_to_dict_contains_all_fields():
    shape = make_shape()
    d = shape.to_dict()
    for key in ("shape_type", "fill_color", "stroke_color", "stroke_width",
                "x", "y", "size", "opacity"):
        assert key in d


def test_shape_params_roundtrip():
    """to_dict → from_dict reconstructs an equal ShapeParams."""
    original = make_shape(shape_type="square", fill_color="#0000FF", x=0.3, opacity=0.7)
    restored = ShapeParams.from_dict(original.to_dict())
    assert restored == original


# ── ArtParameters construction ────────────────────────────────────────────────

def test_art_parameters_valid_construction():
    params = make_params()
    assert params.background_color == "#FFFFFF"
    assert len(params.shapes) == 1
    assert params.canvas_width == CANVAS_WIDTH
    assert params.canvas_height == CANVAS_HEIGHT


def test_art_parameters_artwork_id_auto_generated():
    """artwork_id is a valid UUID string when not explicitly provided."""
    params = make_params()
    parsed = uuid.UUID(params.artwork_id)  # raises if not a valid UUID
    assert str(parsed) == params.artwork_id


def test_art_parameters_artwork_id_unique_each_time():
    p1 = make_params()
    p2 = make_params()
    assert p1.artwork_id != p2.artwork_id


def test_art_parameters_accepts_explicit_artwork_id():
    params = make_params()
    params2 = ArtParameters(
        artwork_id="fixed-id",
        background_color="#000000",
        shapes=[make_shape()],
    )
    assert params2.artwork_id == "fixed-id"


def test_art_parameters_rejects_invalid_background_color():
    with pytest.raises(ValueError):
        make_params(background_color="white")


def test_art_parameters_rejects_too_few_shapes():
    with pytest.raises(ValueError, match=str(MIN_SHAPES)):
        ArtParameters(background_color="#FFFFFF", shapes=[])


def test_art_parameters_rejects_too_many_shapes():
    with pytest.raises(ValueError, match=str(MAX_SHAPES)):
        ArtParameters(
            background_color="#FFFFFF",
            shapes=[make_shape() for _ in range(MAX_SHAPES + 1)],
        )


def test_art_parameters_accepts_max_shapes():
    """Exactly MAX_SHAPES shapes is valid."""
    params = ArtParameters(
        background_color="#FFFFFF",
        shapes=[make_shape() for _ in range(MAX_SHAPES)],
    )
    assert len(params.shapes) == MAX_SHAPES


# ── ArtParameters serialisation ───────────────────────────────────────────────

def test_art_parameters_to_dict_contains_all_keys():
    params = make_params()
    d = params.to_dict()
    for key in ("artwork_id", "background_color", "canvas_width", "canvas_height", "shapes"):
        assert key in d


def test_art_parameters_to_dict_shapes_is_list_of_dicts():
    params = make_params(shapes=[make_shape(), make_shape(shape_type="square")])
    d = params.to_dict()
    assert isinstance(d["shapes"], list)
    assert len(d["shapes"]) == 2
    assert isinstance(d["shapes"][0], dict)


def test_art_parameters_roundtrip():
    """to_dict → from_dict reconstructs an equal ArtParameters."""
    original = ArtParameters(
        artwork_id="test-id",
        background_color="#000080",
        canvas_width=400,
        canvas_height=400,
        shapes=[
            make_shape(shape_type="triangle", x=0.2, y=0.8),
            make_shape(shape_type="line", size=0.9, opacity=0.5),
        ],
    )
    restored = ArtParameters.from_dict(original.to_dict())

    assert restored.artwork_id       == original.artwork_id
    assert restored.background_color == original.background_color
    assert restored.canvas_width     == original.canvas_width
    assert restored.canvas_height    == original.canvas_height
    assert len(restored.shapes)      == len(original.shapes)
    assert restored.shapes[0]        == original.shapes[0]
    assert restored.shapes[1]        == original.shapes[1]


def test_art_parameters_from_dict_uses_default_canvas_when_absent():
    """from_dict falls back to settings defaults if canvas dimensions are missing."""
    d = {
        "artwork_id":       "test-id",
        "background_color": "#FFFFFF",
        "shapes":           [make_shape().to_dict()],
    }
    params = ArtParameters.from_dict(d)
    assert params.canvas_width  == CANVAS_WIDTH
    assert params.canvas_height == CANVAS_HEIGHT
