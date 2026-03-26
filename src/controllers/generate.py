"""
Artwork generation controller — PRD 1.6

Orchestrates the render-and-save pipeline:
  ArtParameters → SVG string → file on disk

Public API:
  save_artwork(params, output_dir) → Path
"""
import logging
from pathlib import Path

from src.config.settings import TALENT_DIR
from src.models.art_params import ArtParameters
from src.views.svg_renderer import render_svg

logger = logging.getLogger(__name__)


def save_artwork(params: ArtParameters, output_dir: Path = TALENT_DIR) -> Path:
    """
    Render params to SVG and write the file to output_dir/{artwork_id}.svg.

    Creates output_dir if it does not exist.
    Returns the absolute path of the written file.
    """
    svg_str = render_svg(params)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{params.artwork_id}.svg"
    path.write_text(svg_str, encoding="utf-8")
    logger.info("Artwork saved: %s (%d shapes)", path, len(params.shapes))
    return path
