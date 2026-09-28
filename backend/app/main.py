"""
FastAPI application entry point.

Startup:
  • Configures CORS from env.
  • Creates DB tables (safe for both SQLite and PostgreSQL).
  • Mounts all API routers.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import analyze, health, reports
from app.core.config import settings
from app.db.session import Base, engine

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=settings.LOG_LEVEL.upper(),
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Creating database tables (if they don't exist) …")
    Base.metadata.create_all(bind=engine)
    logger.info("Startup complete.")
    yield

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="AI Clinical Document Reviewer",
    version="1.0.0",
    description="Submit clinical documentation for AI-powered analysis and structured reporting.",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(health.router, tags=["Health"])
app.include_router(analyze.router, tags=["Analyze"])
app.include_router(reports.router, tags=["Reports"])
