"""
Tests for input validation — empty input, unsupported file type, corrupted PDF.
"""
from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Empty input
# ---------------------------------------------------------------------------

def test_empty_input_returns_400(client: TestClient):
    """Submitting with no text and no file should return 400."""
    resp = client.post("/api/analyze")
    assert resp.status_code == 400
    body = resp.json()
    assert body["error"]["code"] == "EMPTY_INPUT"


def test_blank_text_returns_400(client: TestClient):
    """Submitting only whitespace text should return 400."""
    resp = client.post("/api/analyze", data={"text": "   "})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "EMPTY_INPUT"


# ---------------------------------------------------------------------------
# Unsupported file type
# ---------------------------------------------------------------------------

def test_unsupported_file_type_returns_415(client: TestClient):
    """Uploading a .docx should return 415."""
    fake = io.BytesIO(b"PK\x03\x04 fake docx content here")
    resp = client.post(
        "/api/analyze",
        files={"file": ("notes.docx", fake, "application/vnd.openxmlformats")},
    )
    assert resp.status_code == 415
    body = resp.json()
    assert body["error"]["code"] == "UNSUPPORTED_FILE_TYPE"


def test_unsupported_extension_txt_not_rejected_as_type(client: TestClient):
    """A .txt extension is not in the allowed list — should get 415."""
    resp = client.post(
        "/api/analyze",
        files={"file": ("notes.txt", io.BytesIO(b"hello"), "text/plain")},
    )
    assert resp.status_code == 415


# ---------------------------------------------------------------------------
# Corrupted PDF
# ---------------------------------------------------------------------------

def test_corrupted_pdf_returns_422(client: TestClient):
    """A file named .pdf but with non-PDF bytes should fail magic-byte check."""
    fake_pdf = io.BytesIO(b"this is definitely not a PDF file at all")
    resp = client.post(
        "/api/analyze",
        files={"file": ("report.pdf", fake_pdf, "application/pdf")},
    )
    assert resp.status_code == 422
    body = resp.json()
    assert body["error"]["code"] == "INVALID_FILE"


def test_corrupted_png_returns_422(client: TestClient):
    """A file named .png but with random bytes should fail magic-byte check."""
    fake_png = io.BytesIO(b"not a png")
    resp = client.post(
        "/api/analyze",
        files={"file": ("scan.png", fake_png, "image/png")},
    )
    assert resp.status_code == 422
    body = resp.json()
    assert body["error"]["code"] == "INVALID_FILE"
