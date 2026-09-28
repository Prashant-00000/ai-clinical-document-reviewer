"""
Tests for input validation — empty input, unsupported file type, corrupted PDF.
"""
from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.api.routes.analyze import _clear_rate_limit_state


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


def test_text_over_configured_limit_returns_413(client: TestClient, monkeypatch):
    """Text over MAX_TEXT_CHARS is rejected before any LLM call."""
    monkeypatch.setattr(settings, "MAX_TEXT_CHARS", 10)
    resp = client.post("/api/analyze", data={"text": "01234567890"})
    assert resp.status_code == 413
    assert resp.json()["error"]["code"] == "TEXT_TOO_LONG"


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


def test_rate_limit_uses_forwarded_client_ip(client: TestClient, monkeypatch):
    """The configured per-IP hourly limit returns the standard 429 envelope."""
    monkeypatch.setattr(settings, "RATE_LIMIT_PER_HOUR", 2)
    _clear_rate_limit_state()
    headers = {"X-Forwarded-For": "203.0.113.10, 10.0.0.1"}

    first = client.post("/api/analyze", data={"text": "Patient Jane."}, headers=headers)
    second = client.post("/api/analyze", data={"text": "Patient Jane."}, headers=headers)
    limited = client.post("/api/analyze", data={"text": "Patient Jane."}, headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "RATE_LIMITED"
