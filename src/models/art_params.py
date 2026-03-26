"""
Art parameter dataclasses — PRD 1.4.

ArtParameters is the complete specification for one generated artwork.
ShapeParams describes a single shape within that artwork.

Both classes validate all inputs on construction and support JSON-compatible
round-trip serialisation via to_dict() / from_dict().

Public API:
  ShapeParams                           — one shape's visual parameters
  ArtParameters                         — full artwork specification
  ShapeParams.to_dict()   → dict
  ShapeParams.from_dict(d) → ShapeParams
  ArtParameters.to_dict()  → dict
  ArtParameters.from_dict(d) → ArtParameters
"""
import uuid
from dataclasses import dataclass, field

from src.config.settings import (
    CANVAS_HEIGHT,
    CANVAS_WIDTH,
    MAX_SHAPES,
    MIN_SHAPES,
)
from src.helpers.param_validators import (
    validate_hex_color,
    validate_shape_type,
    validate_stroke_width,
    validate_unit_float,
)


@dataclass
class ShapeParams:
    """
    Visual parameters for a single shape in the artwork.

    Coordinates and size are normalised to [0, 1] so they remain
    canvas-size-agnostic. The SVG generator multiplies by canvas dimensions.
    """
    shape_type:   str    # one of SHAPE_TYPES
    fill_color:   str    # #RRGGBB
    stroke_color: str    # #RRGGBB
    stroke_width: int    # pixel value — one of STROKE_WIDTHS.values()
    x:            float  # horizontal centre, normalised [0, 1]
    y:            float  # vertical centre, normalised [0, 1]
    size:         float  # bounding radius / half-side, normalised [0, 1]
    opacity:      float  # [0.0, 1.0]

    def __post_init__(self) -> None:
        self.shape_type   = validate_shape_type(self.shape_type)
        self.fill_color   = validate_hex_color(self.fill_color)
        self.stroke_color = validate_hex_color(self.stroke_color)
        self.stroke_width = validate_stroke_width(self.stroke_width)
        self.x            = validate_unit_float(self.x, "x")
        self.y            = validate_unit_float(self.y, "y")
        self.size         = validate_unit_float(self.size, "size")
        self.opacity      = validate_unit_float(self.opacity, "opacity")

    def to_dict(self) -> dict:
        """Return a JSON-serialisable dict representing this shape."""
        return {
            "shape_type":   self.shape_type,
            "fill_color":   self.fill_color,
            "stroke_color": self.stroke_color,
            "stroke_width": self.stroke_width,
            "x":            self.x,
            "y":            self.y,
            "size":         self.size,
            "opacity":      self.opacity,
        }

    @staticmethod
    def from_dict(data: dict) -> "ShapeParams":
        """Reconstruct a ShapeParams from a dict produced by to_dict()."""
        return ShapeParams(
            shape_type=data["shape_type"],
            fill_color=data["fill_color"],
            stroke_color=data["stroke_color"],
            stroke_width=data["stroke_width"],
            x=data["x"],
            y=data["y"],
            size=data["size"],
            opacity=data["opacity"],
        )


@dataclass
class ArtParameters:
    """
    Complete parameter set for one generated artwork.

    artwork_id is auto-generated as a UUID if not supplied, making each
    ArtParameters instance uniquely addressable in the graph and on disk.
    """
    background_color: str
    shapes:           list[ShapeParams]
    artwork_id:       str = field(default_factory=lambda: str(uuid.uuid4()))
    canvas_width:     int = CANVAS_WIDTH
    canvas_height:    int = CANVAS_HEIGHT

    def __post_init__(self) -> None:
        self.background_color = validate_hex_color(self.background_color)
        if not (MIN_SHAPES <= len(self.shapes) <= MAX_SHAPES):
            raise ValueError(
                f"shapes count {len(self.shapes)} is outside the allowed range "
                f"[{MIN_SHAPES}, {MAX_SHAPES}]"
            )

    def to_dict(self) -> dict:
        """Return a JSON-serialisable dict representing the full artwork specification."""
        return {
            "artwork_id":       self.artwork_id,
            "background_color": self.background_color,
            "canvas_width":     self.canvas_width,
            "canvas_height":    self.canvas_height,
            "shapes":           [s.to_dict() for s in self.shapes],
        }

    @staticmethod
    def from_dict(data: dict) -> "ArtParameters":
        """Reconstruct an ArtParameters from a dict produced by to_dict()."""
        return ArtParameters(
            artwork_id=data["artwork_id"],
            background_color=data["background_color"],
            canvas_width=data.get("canvas_width", CANVAS_WIDTH),
            canvas_height=data.get("canvas_height", CANVAS_HEIGHT),
            shapes=[ShapeParams.from_dict(s) for s in data["shapes"]],
        )
