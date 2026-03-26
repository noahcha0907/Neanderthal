"""
Unit tests for format parsers — PRD 1.1
"""
import pytest
from pathlib import Path

from src.helpers.parsers.text_parser import parse_text
from src.helpers.parsers import parse_document


def test_parse_txt_returns_content(tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("Hello world.\n\nSecond paragraph.", encoding="utf-8")
    result = parse_text(f)
    assert "Hello world." in result
    assert "Second paragraph." in result


def test_parse_txt_normalizes_crlf(tmp_path):
    f = tmp_path / "test.txt"
    f.write_bytes(b"Line one\r\nLine two\r\nLine three")
    result = parse_text(f)
    assert "\r" not in result


def test_parse_txt_normalizes_cr(tmp_path):
    f = tmp_path / "test.txt"
    f.write_bytes(b"Line one\rLine two\rLine three")
    result = parse_text(f)
    assert "\r" not in result


def test_parse_txt_missing_file_returns_empty(tmp_path):
    result = parse_text(tmp_path / "nonexistent.txt")
    assert result == ""


def test_parse_md_returns_content(tmp_path):
    f = tmp_path / "test.md"
    f.write_text("# Heading\n\nSome content here.", encoding="utf-8")
    result = parse_document(f)
    assert "Some content here." in result


def test_parse_unsupported_format_returns_empty(tmp_path):
    f = tmp_path / "test.docx"
    f.write_bytes(b"fake docx content")
    result = parse_document(f)
    assert result == ""


def test_parse_latin1_encoded_file(tmp_path):
    f = tmp_path / "latin.txt"
    f.write_bytes("Caf\xe9 au lait".encode("latin-1"))
    result = parse_text(f)
    assert result != ""
