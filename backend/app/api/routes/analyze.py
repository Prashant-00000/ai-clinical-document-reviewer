"""
POST /api/analyze  — submit clinical documentation for analysis.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.report import ErrorResponse, ErrorDetail, ReportDetail
from app.services.analyzer import run_analysis
from app.services.document_processor import (
    FileTooLargeError,
    InvalidFileError,
    UnsupportedFileTypeError,
)
from app.services.llm_client import LLMClient, LLMError, get_llm_client

logger = logging.getLogger(__name__)

router = APIRouter()


def _report_row_to_detail(row) -> dict:
    """Convert a Report ORM row to a ReportDetail-compatible dict."""
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


@router.post(
    "/api/analyze",
    response_model=ReportDetail,
    responses={
        400: {"model": ErrorResponse},
        413: {"model": ErrorResponse},
        415: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
    },
)
async def analyze_document(
    text: str | None = Form(None),
    file: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    llm_client: LLMClient = Depends(get_llm_client),
):
    """Submit clinical documentation (text, image, or PDF) for analysis."""

    # ── Pre-validation (no DB row yet) ───────────────────────────────────
    has_text = bool(text and text.strip())
    has_file = file is not None and file.filename

    if not has_text and not has_file:
        return JSONResponse(
            status_code=400,
            content=ErrorResponse(
                error=ErrorDetail(code="EMPTY_INPUT", message="Provide either text or a file.")
            ).model_dump(),
        )

    file_bytes: bytes | None = None
    filename: str | None = None

    if has_file:
        file_bytes = await file.read()
        filename = file.filename

    # ── Run the pipeline ─────────────────────────────────────────────────
    try:
        report_row = run_analysis(
            text=text if has_text else None,
            file_bytes=file_bytes,
            filename=filename,
            db=db,
            llm_client=llm_client,
        )
        return JSONResponse(status_code=200, content=_report_row_to_detail(report_row))

    except FileTooLargeError as exc:
        return JSONResponse(
            status_code=413,
            content=ErrorResponse(
                error=ErrorDetail(code="FILE_TOO_LARGE", message=str(exc))
            ).model_dump(),
        )

    except UnsupportedFileTypeError as exc:
        return JSONResponse(
            status_code=415,
            content=ErrorResponse(
                error=ErrorDetail(code="UNSUPPORTED_FILE_TYPE", message=str(exc))
            ).model_dump(),
        )

    except InvalidFileError as exc:
        return JSONResponse(
            status_code=422,
            content=ErrorResponse(
                error=ErrorDetail(code="INVALID_FILE", message=str(exc))
            ).model_dump(),
        )

    except LLMError as exc:
        return JSONResponse(
            status_code=502,
            content=ErrorResponse(
                error=ErrorDetail(code="LLM_FAILURE", message=str(exc))
            ).model_dump(),
        )

    except ValidationError as exc:
        return JSONResponse(
            status_code=502,
            content=ErrorResponse(
                error=ErrorDetail(
                    code="LLM_SCHEMA_ERROR",
                    message=f"LLM output did not match expected schema: {exc}",
                )
            ).model_dump(),
        )

    except Exception as exc:
        logger.exception("Unexpected error during analysis")
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error=ErrorDetail(code="INTERNAL_ERROR", message=str(exc))
            ).model_dump(),
        )
