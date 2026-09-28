"""
POST /api/analyze  — submit clinical documentation for analysis.
"""
from __future__ import annotations

import logging
import time
from collections import deque
from threading import Lock

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.report import ErrorResponse, ErrorDetail, ReportDetail
from app.services.analyzer import run_analysis
from app.services.document_processor import (
    FileTooLargeError,
    InvalidFileError,
    TextTooLongError,
    UnsupportedFileTypeError,
)
from app.services.llm_client import LLMClient, LLMError, get_llm_client
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

_rate_limit_lock = Lock()
_request_times: dict[str, deque[float]] = {}
_RATE_LIMIT_WINDOW_SECONDS = 60 * 60


def _client_ip(request: Request) -> str:
    """Use the first forwarded address when behind a proxy."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",", 1)[0].strip() or "unknown"
    return request.client.host if request.client else "unknown"


def _rate_limit_exceeded(ip: str) -> bool:
    now = time.monotonic()
    cutoff = now - _RATE_LIMIT_WINDOW_SECONDS
    with _rate_limit_lock:
        timestamps = _request_times.setdefault(ip, deque())
        while timestamps and timestamps[0] <= cutoff:
            timestamps.popleft()
        if len(timestamps) >= settings.RATE_LIMIT_PER_HOUR:
            return True
        timestamps.append(now)
        return False


def _clear_rate_limit_state() -> None:
    """Clear in-memory state for deterministic tests."""
    with _rate_limit_lock:
        _request_times.clear()


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
        429: {"model": ErrorResponse},
        415: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
    },
)
async def analyze_document(
    request: Request,
    text: str | None = Form(None),
    file: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    llm_client: LLMClient = Depends(get_llm_client),
):
    """Submit clinical documentation (text, image, or PDF) for analysis."""

    if _rate_limit_exceeded(_client_ip(request)):
        return JSONResponse(
            status_code=429,
            content=ErrorResponse(
                error=ErrorDetail(
                    code="RATE_LIMITED",
                    message="Analysis rate limit exceeded. Try again later.",
                )
            ).model_dump(),
        )

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

    if has_text and len(text) > settings.MAX_TEXT_CHARS:
        return JSONResponse(
            status_code=413,
            content=ErrorResponse(
                error=ErrorDetail(
                    code="TEXT_TOO_LONG",
                    message=(
                        f"Text input ({len(text):,} characters) exceeds the "
                        f"{settings.MAX_TEXT_CHARS:,} character limit."
                    ),
                )
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
