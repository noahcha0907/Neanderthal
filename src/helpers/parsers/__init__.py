"""
Dispatcher: routes a file to the correct format parser based on extension.
"""
from pathlib import Path

from src.helpers.parsers.bytes_parser import parse_bytes  # noqa: F401  (re-exported)
from src.helpers.parsers.pdf_parser import parse_pdf
from src.helpers.parsers.text_parser import parse_text


def parse_document(path: Path) -> str:
    """
    Dispatch to the correct parser based on file extension.
    Returns empty string for unsupported formats — never raises.
    """
    suffix = Path(path).suffix.lower()
    if suffix == ".pdf":
        return parse_pdf(path)
    if suffix in (".txt", ".md"):
        return parse_text(path)
    return ""
