"""
Unit tests for the SVG renderer and artwork save controller — PRD 1.6

All rendering tests parse the SVG output with stdlib xml.etree.ElementTree
to assert structural correctness without brittle string matching.
"""
import xml.etree.ElementTree as ET

import pytest

from src.models.art_params import ArtParameters, ShapeParams
from src.controllers.generate import save_artwork
from src.views.svg_renderer import render_svg, _equilateral_points, _star_points

SVG_NS = "http://www.w3.org/2000/svg"


# ── Fixtures and helpers ──────────────────────────────────────────────────────

def make_shape(**overrides) -> ShapeParams:
    defaults = dict(
        shape_type="circle",
        fill_color="#FF0000",
        stroke_color="#000000",
        stroke_width=1,
        x=0.5, y=0.5, size=0.2, opacity=1.0,
    )
    defaults.update(overrides)
    return ShapeParams(**defaults)


def make_params(shapes=None, **overrides) -> ArtParameters:
    if shapes is None:
        shapes = [make_shape()]
    defaults = dict(background_color="#FFFFFF", shapes=shapes)
    defaults.update(overrides)
    return ArtParameters(**defaults)


def parse_svg(svg_str: str) -> ET.Element:
    """Parse an SVG string and return the root element."""
    return ET.fromstring(svg_str)


def svg_elements(root: ET.Element, tag: str) -> list[ET.Element]:
    """Find all direct children of root with the given unqualified tag."""
    return root.findall(f"{{{SVG_NS}}}{tag}") + root.findall(tag)


# ── render_svg — document structure ──────────────────────────────────────────

def test_render_svg_returns_string():
    assert isinstance(render_svg(make_params()), str)


def test_render_svg_is_valid_xml():
    """The output must be parseable XML — no malformed elements."""
    svg = render_svg(make_params())
    root = parse_svg(svg)   # raises ParseError if invalid
    assert root is not None


def test_render_svg_root_has_correct_dimensions():
    """SVG root element carries the canvas width and height."""
    params = make_params()
    root = parse_svg(render_svg(params))
    assert root.get("width")  == str(params.canvas_width)
    assert root.get("height") == str(params.canvas_height)


def test_render_svg_background_rect_present():
    """First child is a full-canvas rect with the background color."""
    params = make_params()
    root = parse_svg(render_svg(params))
    rects = svg_elements(root, "rect")
    assert len(rects) >= 1
    bg = rects[0]
    assert bg.get("fill") == params.background_color
    assert bg.get("width")  == str(params.canvas_width)
    assert bg.get("height") == str(params.canvas_height)


def test_render_svg_shape_count_matches_params():
    """Total drawn elements (excluding background rect) equals len(params.shapes)."""
    shapes = [make_shape(shape_type="circle") for _ in range(5)]
    params = make_params(shapes=shapes)
    root = parse_svg(render_svg(params))
    circles = svg_elements(root, "circle")
    assert len(circles) == 5


# ── render_svg — per shape type ───────────────────────────────────────────────

def test_render_circle_produces_circle_element():
    params = make_params(shapes=[make_shape(shape_type="circle")])
    root = parse_svg(render_svg(params))
    circles = svg_elements(root, "circle")
    assert len(circles) == 1
    c = circles[0]
    assert c.get("cx") is not None
    assert c.get("cy") is not None
    assert c.get("r")  is not None
    assert c.get("fill") == "#FF0000"


def test_render_square_produces_rect_element():
    params = make_params(shapes=[make_shape(shape_type="square")])
    root = parse_svg(render_svg(params))
    # background rect + square rect
    rects = svg_elements(root, "rect")
    assert len(rects) == 2
    square = rects[1]
    # width and height must be equal for a square
    assert square.get("width") == square.get("height")


def test_render_rectangle_produces_rect_element():
    params = make_params(shapes=[make_shape(shape_type="rectangle", size=0.2)])
    root = parse_svg(render_svg(params))
    rects = svg_elements(root, "rect")
    rect_shape = rects[1]
    width  = float(rect_shape.get("width"))
    height = float(rect_shape.get("height"))
    # rectangle is wider than tall (3:2 aspect ratio)
    assert width > height


def test_render_triangle_produces_polygon_element():
    params = make_params(shapes=[make_shape(shape_type="triangle")])
    root = parse_svg(render_svg(params))
    polys = svg_elements(root, "polygon")
    assert len(polys) == 1
    pts = polys[0].get("points").split()
    assert len(pts) == 3   # equilateral triangle has 3 vertices


def test_render_star_produces_polygon_element():
    params = make_params(shapes=[make_shape(shape_type="star")])
    root = parse_svg(render_svg(params))
    polys = svg_elements(root, "polygon")
    assert len(polys) == 1
    pts = polys[0].get("points").split()
    assert len(pts) == 10   # 5-pointed star has 10 vertices


def test_render_line_produces_line_element():
    params = make_params(shapes=[make_shape(shape_type="line")])
    root = parse_svg(render_svg(params))
    lines = svg_elements(root, "line")
    assert len(lines) == 1
    el = lines[0]
    assert el.get("x1") is not None
    assert el.get("x2") is not None
    assert el.get("y1") == el.get("y2")   # horizontal line


def test_render_line_uses_stroke_not_fill():
    """Lines have fill='none' — the stroke_color carries the visual."""
    params = make_params(shapes=[make_shape(shape_type="line", stroke_color="#0000FF")])
    root = parse_svg(render_svg(params))
    el = svg_elements(root, "line")[0]
    assert el.get("fill") == "none"
    assert el.get("stroke") == "#0000FF"


# ── render_svg — attribute correctness ───────────────────────────────────────

def test_render_opacity_is_present():
    """opacity attribute is written for all filled shapes."""
    for shape_type in ("circle", "square", "rectangle", "triangle", "star"):
        params = make_params(shapes=[make_shape(shape_type=shape_type, opacity=0.75)])
        root = parse_svg(render_svg(params))
        svg_str = render_svg(params)
        assert "opacity" in svg_str


def test_render_stroke_width_is_present():
    """stroke-width attribute matches the ShapeParams value."""
    params = make_params(shapes=[make_shape(stroke_width=3)])
    svg_str = render_svg(params)
    assert 'stroke-width="3"' in svg_str


def test_render_multiple_shape_types_in_one_artwork():
    """A mix of all six shape types renders without error and produces valid XML."""
    from src.config.settings import SHAPE_TYPES
    shapes = [make_shape(shape_type=st) for st in SHAPE_TYPES]
    params = make_params(shapes=shapes)
    root = parse_svg(render_svg(params))
    assert root is not None


# ── Geometry helpers ──────────────────────────────────────────────────────────

def test_equilateral_points_returns_three_vertices():
    pts = _equilateral_points(400, 400, 100)
    assert len(pts) == 3


def test_equilateral_points_are_equidistant():
    """All three sides of the triangle are equal length."""
    import math
    pts = _equilateral_points(0, 0, 100)
    dist = lambda a, b: math.hypot(a[0]-b[0], a[1]-b[1])
    d01 = dist(pts[0], pts[1])
    d12 = dist(pts[1], pts[2])
    d20 = dist(pts[2], pts[0])
    assert d01 == pytest.approx(d12, rel=1e-5)
    assert d12 == pytest.approx(d20, rel=1e-5)


def test_star_points_returns_ten_vertices():
    pts = _star_points(400, 400, outer_r=100, inner_r=40)
    assert len(pts) == 10


def test_star_outer_radius_is_larger_than_inner():
    """Even-indexed points (outer) are farther from centre than odd-indexed (inner)."""
    import math
    cx, cy = 0, 0
    pts = _star_points(cx, cy, outer_r=100, inner_r=40)
    for i, (px, py) in enumerate(pts):
        dist = math.hypot(px - cx, py - cy)
        if i % 2 == 0:
            assert dist == pytest.approx(100, rel=1e-5)
        else:
            assert dist == pytest.approx(40, rel=1e-5)


# ── save_artwork ──────────────────────────────────────────────────────────────

def test_save_artwork_creates_svg_file(tmp_path):
    """save_artwork writes an SVG file to the specified directory."""
    params = make_params()
    path = save_artwork(params, output_dir=tmp_path)
    assert path.exists()
    assert path.suffix == ".svg"


def test_save_artwork_filename_matches_artwork_id(tmp_path):
    """The filename is {artwork_id}.svg."""
    params = make_params()
    path = save_artwork(params, output_dir=tmp_path)
    assert path.stem == params.artwork_id


def test_save_artwork_creates_output_dir(tmp_path):
    """save_artwork creates output_dir if it does not yet exist."""
    nested = tmp_path / "a" / "b" / "c"
    params = make_params()
    save_artwork(params, output_dir=nested)
    assert nested.is_dir()


def test_save_artwork_content_is_valid_svg(tmp_path):
    """The written file contains parseable SVG."""
    params = make_params()
    path = save_artwork(params, output_dir=tmp_path)
    root = ET.parse(str(path)).getroot()
    assert root is not None


def test_save_artwork_returns_path_object(tmp_path):
    params = make_params()
    result = save_artwork(params, output_dir=tmp_path)
    assert isinstance(result, type(tmp_path))
