"""
Pure validation helpers for art parameter values — PRD 1.4.

Each function accepts a candidate value, returns it unchanged if valid,
and raises ValueError with a descriptive message if invalid.

These are stateless, deterministic functions with no side effects.
"""
import re

from src.config.settings import SHAPE_TYPES, STROKE_WIDTHS

_HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")

# Resolved pixel values that stroke_width is allowed to take
_VALID_STROKE_WIDTHS: frozenset[int] = frozenset(STROKE_WIDTHS.values())


def validate_hex_color(value: str) -> str:
    """Return value if it is a valid #RRGGBB hex string, else raise ValueError."""
    if not isinstance(value, str) or not _HEX_RE.match(value):
        raise ValueError(f"Invalid hex color {value!r} — expected #RRGGBB (e.g. '#FF0000')")
    return value


def validate_unit_float(value: float, name: str = "value") -> float:
    """Return float(value) if it is in [0.0, 1.0], else raise ValueError."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be a float, got {value!r}")
    if not (0.0 <= v <= 1.0):
        raise ValueError(f"{name} must be in [0.0, 1.0], got {v}")
    return v


def validate_shape_type(value: str) -> str:
    """Return value if it is a recognised shape type, else raise ValueError."""
    if value not in SHAPE_TYPES:
        raise ValueError(f"shape_type {value!r} is not one of {SHAPE_TYPES}")
    return value


def validate_stroke_width(value: int) -> int:
    """Return value if it is a recognised stroke-width pixel value, else raise ValueError."""
    if value not in _VALID_STROKE_WIDTHS:
        raise ValueError(
            f"stroke_width {value!r} is not one of {sorted(_VALID_STROKE_WIDTHS)} "
            f"(use STROKE_WIDTHS from settings)"
        )
    return value
