"""
PDF parser: extracts raw plaintext from a PDF using pdfplumber.

Each page's text is extracted and joined with a blank line between pages
to preserve natural document structure for the chunker downstream.
Returns empty string (never raises) on failure — caller handles logging.
"""
import logging
from pathlib import Path

import pdfplumber

logger = logging.getLogger(__name__)


def parse_pdf(path: Path) -> str:
    """
    Extract all text from a PDF file.

    Returns an empty string if the file yields no text or cannot be opened.
    Logs a warning instead of raising so the ingestion pipeline can skip
    bad files without crashing.
    """
    try:
        pages: list[str] = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text and text.strip():
                    pages.append(text.strip())

        if not pages:
            logger.warning("PDF produced no extractable text: %s", path)
            return ""

        return "\n\n".join(pages)

    except Exception as exc:
        logger.warning("Failed to parse PDF %s: %s", path, exc)
        return ""
