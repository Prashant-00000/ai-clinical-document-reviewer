"""
Pydantic v2 schemas for API request / response serialisation.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.analysis import AnalysisReport


# ---------------------------------------------------------------------------
# Standard error envelope  {"error": {"code": "...", "message": "..."}}
# ---------------------------------------------------------------------------

class ErrorDetail(BaseModel):
    code: str
    message: str
    report_id: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


# ---------------------------------------------------------------------------
# Report responses
# ---------------------------------------------------------------------------

class ReportListItem(BaseModel):
    """Lightweight representation for the history table."""
    id: str
    created_at: datetime
    status: str
    input_type: str
    summary: str | None = None


class ReportDetail(BaseModel):
    """Full report returned by GET /api/reports/{id} and POST /api/analyze."""
    id: str
    created_at: datetime
    status: str
    input_type: str
    original_filename: str | None = None
    extracted_text: str | None = None
    report: AnalysisReport | None = None
    error_message: str | None = None


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "1.0.0"
