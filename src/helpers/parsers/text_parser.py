"""
Plaintext parser: reads .txt and .md files.

Tries UTF-8 first, then falls back to common legacy encodings.
Normalizes all line endings to Unix-style \n.
Returns empty string (never raises) on failure.
"""
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Encodings attempted in order — UTF-8 covers almost everything modern
_ENCODINGS = ("utf-8", "latin-1", "cp1252")


def parse_text(path: Path) -> str:
    """
    Read a .txt or .md file and return its contents as a normalized string.

    Returns an empty string if the file cannot be read with any supported
    encoding. Logs a warning instead of raising.
    """
    path = Path(path)

    if not path.exists():
        logger.warning("Text file not found: %s", path)
        return ""

    for encoding in _ENCODINGS:
        try:
            raw = path.read_text(encoding=encoding)
            # Normalize Windows and old Mac line endings to \n
            return raw.replace("\r\n", "\n").replace("\r", "\n")
        except UnicodeDecodeError:
            continue
        except Exception as exc:
            logger.warning("Failed to read %s: %s", path, exc)
            return ""

    logger.warning("Could not decode %s with any supported encoding", path)
    return ""
