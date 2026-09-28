"""
SQLAlchemy ORM model for the reports table.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, String, Text
from sqlalchemy.types import JSON

from app.db.session import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return str(uuid.uuid4())


class Report(Base):
    """Persists every analysis run — including failed ones."""

    __tablename__ = "reports"

    id: str = Column(String, primary_key=True, default=_new_id)
    created_at: datetime = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: datetime = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False)

    # processing | completed | completed_with_warnings | failed
    status: str = Column(String(32), default="processing", nullable=False)

    # text | image | pdf
    input_type: str = Column(String(16), nullable=False)
    original_filename: str | None = Column(String(512), nullable=True)

    # Raw text extracted from the document (or user-supplied text)
    extracted_text: str | None = Column(Text, nullable=True)

    # Full structured analysis result (AnalysisReport dict)
    report_json: dict | None = Column(JSON, nullable=True)

    # Human-readable error message when status == "failed"
    error_message: str | None = Column(Text, nullable=True)
