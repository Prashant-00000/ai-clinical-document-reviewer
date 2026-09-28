"""
GET  /api/reports        — list all reports (history).
GET  /api/reports/{id}   — full report detail.
DELETE /api/reports/{id} — delete a report.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.report import Report
from app.schemas.report import (
    ErrorDetail,
    ErrorResponse,
    ReportDetail,
    ReportListItem,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# GET /api/reports
# ---------------------------------------------------------------------------

@router.get("/api/reports", response_model=list[ReportListItem])
def list_reports(db: Session = Depends(get_db)):
    """Return all reports ordered by most-recent first."""
    rows = db.query(Report).order_by(Report.created_at.desc()).all()
    items: list[dict] = []
    for r in rows:
        summary: str | None = None
        if r.report_json and isinstance(r.report_json, dict):
            summary = r.report_json.get("report_summary")
        items.append(
            ReportListItem(
                id=r.id,
                created_at=r.created_at,
                status=r.status,
                input_type=r.input_type,
                summary=summary,
            ).model_dump(mode="json")
        )
    return items


# ---------------------------------------------------------------------------
# GET /api/reports/{id}
# ---------------------------------------------------------------------------

@router.get(
    "/api/reports/{report_id}",
    response_model=ReportDetail,
    responses={404: {"model": ErrorResponse}},
)
def get_report(report_id: str, db: Session = Depends(get_db)):
    """Return the full report including analysis JSON."""
    row = db.query(Report).filter(Report.id == report_id).first()
    if not row:
        return JSONResponse(
            status_code=404,
            content=ErrorResponse(
                error=ErrorDetail(code="NOT_FOUND", message=f"Report '{report_id}' not found.")
            ).model_dump(),
        )
    return ReportDetail(
        id=row.id,
        created_at=row.created_at,
        status=row.status,
        input_type=row.input_type,
        original_filename=row.original_filename,
        extracted_text=row.extracted_text,
        report=row.report_json,
        error_message=row.error_message,
    ).model_dump(mode="json")


# ---------------------------------------------------------------------------
# DELETE /api/reports/{id}
# ---------------------------------------------------------------------------

@router.delete(
    "/api/reports/{report_id}",
    responses={404: {"model": ErrorResponse}},
)
def delete_report(report_id: str, db: Session = Depends(get_db)):
    """Delete a report by ID."""
    row = db.query(Report).filter(Report.id == report_id).first()
    if not row:
        return JSONResponse(
            status_code=404,
            content=ErrorResponse(
                error=ErrorDetail(code="NOT_FOUND", message=f"Report '{report_id}' not found.")
            ).model_dump(),
        )
    db.delete(row)
    db.commit()
    return {"message": f"Report '{report_id}' deleted."}
