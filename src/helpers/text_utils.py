"""
Pure text utility helpers — PRD 1.7

Stateless, deterministic functions with no side effects.
"""
import re

# Matches sentence-ending punctuation followed by whitespace
_SENTENCE_SPLIT_RE = re.compile(r'(?<=[.!?])\s+')


def extract_excerpt(text: str, n_sentences: int = 2) -> str:
    """
    Return the first n_sentences sentences from text.

    Splits on sentence-ending punctuation (.!?) followed by whitespace.
    If the text contains fewer than n_sentences sentences, returns all of it.
    Leading/trailing whitespace is stripped from the result.
    """
    text = text.strip()
    if not text:
        return ""
    sentences = _SENTENCE_SPLIT_RE.split(text)
    return " ".join(sentences[:n_sentences]).strip()
