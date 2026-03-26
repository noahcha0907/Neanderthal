"""
Bytes-based text extraction for user uploads — PRD 2.6

Mirrors the file-based parsers but operates on raw bytes received via HTTP.
Returns empty string on failure so the upload pipeline can raise UploadError
with a user-facing message instead of an internal exception leaking up.
"""
import io
import logging
from pathlib import Path

import pdfplumber

logger = logging.getLogger(__name__)

# Encodings tried in order for plaintext files
_ENCODINGS = ("utf-8", "latin-1", "cp1252")


def parse_bytes(filename: str, content: bytes) -> str:
    """
    Extract plain text from raw file bytes.

    filename is used only to detect the file type via its extension —
    it is never opened as a path.  Returns empty string if text cannot
    be extracted; never raises.
    """
    suffix = Path(filename).suffix.lower()

    if suffix == ".pdf":
        return _extract_pdf_bytes(content)

    if suffix in (".txt", ".md"):
        return _extract_text_bytes(content, filename)

    logger.warning("parse_bytes called with unsupported extension: %s", filename)
    return ""


def _extract_text_bytes(content: bytes, label: str) -> str:
    """Decode text bytes trying each encoding in _ENCODINGS in order."""
    for encoding in _ENCODINGS:
        try:
            return content.decode(encoding).replace("\r\n", "\n").replace("\r", "\n")
        except UnicodeDecodeError:
            continue

    logger.warning("Could not decode %s with any supported encoding", label)
    return ""


def _extract_pdf_bytes(content: bytes) -> str:
    """Extract all text from PDF bytes using pdfplumber."""
    try:
        pages: list[str] = []
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text and text.strip():
                    pages.append(text.strip())

        if not pages:
            logger.warning("PDF upload produced no extractable text")
            return ""

        return "\n\n".join(pages)

    except Exception as exc:
        logger.warning("Failed to parse PDF upload: %s", exc)
        return ""
