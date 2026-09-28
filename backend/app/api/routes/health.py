"""
GET /api/health — lightweight health check.
"""
from __future__ import annotations

from fastapi import APIRouter

from app.schemas.report import HealthResponse

router = APIRouter()


@router.get("/api/health", response_model=HealthResponse)
def health_check():
    return HealthResponse()
