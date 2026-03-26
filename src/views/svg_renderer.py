"""
SVG renderer — PRD 1.6

Converts an ArtParameters into a valid SVG string.  No I/O, no state — purely
a transformation from data to markup.

Supported shape types (from SHAPE_TYPES in settings):
  circle, square, rectangle, triangle, star, line

Coordinates and sizes in ArtParameters are normalised [0, 1].  The renderer
multiplies by canvas_width / canvas_height to produce pixel values.

Public API:
  render_svg(params: ArtParameters) → str
"""
import math

from src.models.art_params import ArtParameters, ShapeParams


def render_svg(params: ArtParameters) -> str:
    """
    Render the full artwork to an SVG string.

    The output is a self-contained SVG document with a background rectangle
    followed by one element per shape in params.shapes.
    """
    W = params.canvas_width
    H = params.canvas_height

    lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg"'
        f' width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
        f'  <rect width="{W}" height="{H}" fill="{params.background_color}"/>',
    ]

    for shape in params.shapes:
        lines.append(_render_shape(shape, W, H))

    lines.append("</svg>")
    return "\n".join(lines)


# ── Per-shape renderers ───────────────────────────────────────────────────────

def _render_shape(shape: ShapeParams, canvas_w: int, canvas_h: int) -> str:
    """Dispatch to the correct element renderer based on shape_type."""
    cx = round(shape.x * canvas_w, 2)
    cy = round(shape.y * canvas_h, 2)
    # r is the circumradius / half-side, scaled to canvas units
    r  = round(shape.size * min(canvas_w, canvas_h) / 2, 2)

    if shape.shape_type == "circle":
        return _circle(cx, cy, r, shape)

    if shape.shape_type == "square":
        return _square(cx, cy, r, shape)

    if shape.shape_type == "rectangle":
        return _rectangle(cx, cy, r, shape)

    if shape.shape_type == "triangle":
        return _triangle(cx, cy, r, shape)

    if shape.shape_type == "star":
        return _star(cx, cy, r, shape)

    if shape.shape_type == "line":
        half_len = round(shape.size * canvas_w / 2, 2)
        return _line(cx, cy, half_len, shape)

    raise ValueError(f"Unknown shape_type: {shape.shape_type!r}")


def _fill_attrs(shape: ShapeParams) -> str:
    """Common fill/stroke/opacity attribute string for filled shapes."""
    return (
        f'fill="{shape.fill_color}" '
        f'stroke="{shape.stroke_color}" '
        f'stroke-width="{shape.stroke_width}" '
        f'opacity="{shape.opacity:.4f}"'
    )


def _circle(cx: float, cy: float, r: float, shape: ShapeParams) -> str:
    return f'  <circle cx="{cx}" cy="{cy}" r="{r}" {_fill_attrs(shape)}/>'


def _square(cx: float, cy: float, r: float, shape: ShapeParams) -> str:
    x0   = round(cx - r, 2)
    y0   = round(cy - r, 2)
    side = round(r * 2, 2)
    return f'  <rect x="{x0}" y="{y0}" width="{side}" height="{side}" {_fill_attrs(shape)}/>'


def _rectangle(cx: float, cy: float, r: float, shape: ShapeParams) -> str:
    # 3:2 aspect ratio — wider than tall
    half_w = round(r * 1.5, 2)
    half_h = r
    x0     = round(cx - half_w, 2)
    y0     = round(cy - half_h, 2)
    return (
        f'  <rect x="{x0}" y="{y0}"'
        f' width="{round(half_w * 2, 2)}" height="{round(half_h * 2, 2)}"'
        f' {_fill_attrs(shape)}/>'
    )


def _triangle(cx: float, cy: float, r: float, shape: ShapeParams) -> str:
    """Equilateral triangle centred at (cx, cy) with circumradius r."""
    pts = _equilateral_points(cx, cy, r)
    pts_str = " ".join(f"{x:.2f},{y:.2f}" for x, y in pts)
    return f'  <polygon points="{pts_str}" {_fill_attrs(shape)}/>'


def _star(cx: float, cy: float, r: float, shape: ShapeParams) -> str:
    """5-pointed star centred at (cx, cy) with outer radius r."""
    pts = _star_points(cx, cy, outer_r=r, inner_r=r * 0.4)
    pts_str = " ".join(f"{x:.2f},{y:.2f}" for x, y in pts)
    return f'  <polygon points="{pts_str}" {_fill_attrs(shape)}/>'


def _line(cx: float, cy: float, half_len: float, shape: ShapeParams) -> str:
    """Horizontal line centred at (cx, cy) with total length 2*half_len."""
    x1 = round(cx - half_len, 2)
    x2 = round(cx + half_len, 2)
    return (
        f'  <line x1="{x1}" y1="{cy}" x2="{x2}" y2="{cy}"'
        f' fill="none"'
        f' stroke="{shape.stroke_color}"'
        f' stroke-width="{shape.stroke_width}"'
        f' opacity="{shape.opacity:.4f}"/>'
    )


# ── Geometry helpers ──────────────────────────────────────────────────────────

def _equilateral_points(cx: float, cy: float, r: float) -> list[tuple[float, float]]:
    """
    Three vertices of an equilateral triangle with circumradius r centred at
    (cx, cy), with the apex pointing up (−90° offset).
    """
    return [
        (cx + r * math.cos(math.radians(-90 + 120 * i)),
         cy + r * math.sin(math.radians(-90 + 120 * i)))
        for i in range(3)
    ]


def _star_points(
    cx: float, cy: float, outer_r: float, inner_r: float, points: int = 5
) -> list[tuple[float, float]]:
    """
    Vertices of a `points`-pointed star centred at (cx, cy).

    Alternates between outer_r and inner_r at equal angular spacing,
    starting with the apex pointing up (−90° offset).
    """
    result = []
    for i in range(points * 2):
        angle = math.radians(-90 + i * 180 / points)
        r = outer_r if i % 2 == 0 else inner_r
        result.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    return result
