"""
Pytest fixtures shared across all test modules.

Key fixtures:
  • ``client``  — httpx test client backed by an in-memory SQLite DB.
  • ``mock_llm`` — a mock LLMClient injected via FastAPI dependency override.
  • ``db``      — raw DB session for direct assertions.
"""
from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, StaticPool
from sqlalchemy.orm import sessionmaker

from app.db.session import Base, get_db
from app.main import app
from app.services.llm_client import LLMClient, get_llm_client
from app.api.routes.analyze import _clear_rate_limit_state

# ---------------------------------------------------------------------------
# In-memory SQLite engine for tests
# ---------------------------------------------------------------------------

_TEST_ENGINE = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=_TEST_ENGINE)


def _override_get_db():
    db = TestSession()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Mock LLM client
# ---------------------------------------------------------------------------

_VALID_LLM_RESPONSE: dict[str, Any] = {
    "report_summary": "",
    "patient_information": {
        "name": "John Doe",
        "age": "45",
        "sex": "Male",
        "id": "P12345",
        "other": {},
    },
    "symptoms": [
        {"text": "Chest pain", "evidence": "patient reports chest pain", "confidence": "high"},
        {"text": "Shortness of breath", "evidence": "complains of shortness of breath", "confidence": "high"},
    ],
    "diagnoses": [
        {"text": "Acute bronchitis", "evidence": "diagnosed with acute bronchitis", "confidence": "high"},
    ],
    "medications": [
        {
            "text": "Amoxicillin 500mg PO TID",
            "name": "Amoxicillin",
            "dose": "500mg",
            "route": "PO",
            "frequency": "TID",
            "evidence": "prescribed amoxicillin 500mg",
            "confidence": "high",
        }
    ],
    "vitals": {
        "bp": {"text": "120/80 mmHg", "evidence": "BP 120/80", "confidence": "high"},
        "hr": {"text": "72 bpm", "evidence": "HR 72", "confidence": "high"},
        "temp": {"text": "37.2 C", "evidence": "Temp 37.2", "confidence": "high"},
        "rr": {"text": "18", "evidence": "RR 18", "confidence": "high"},
        "spo2": {"text": "98%", "evidence": "SpO2 98%", "confidence": "high"},
        "other": [],
    },
    "allergies": [
        {"text": "Penicillin", "evidence": "allergic to penicillin", "confidence": "high"},
    ],
    "clinical_observations": [
        {"text": "Lungs: bilateral wheezing", "evidence": "bilateral wheezing noted", "confidence": "high"},
    ],
    "clinical_concerns": [],
    "missing_information": [],
    "potential_inconsistencies": [],
    "requires_review": [],
    "document_quality": {
        "readable": True,
        "notes": None,
        "overall_confidence": "high",
    },
}


class MockLLMClient(LLMClient):
    """Deterministic LLM stub for tests."""

    def __init__(self, json_response: dict[str, Any] | None = None, text_response: str = "") -> None:
        self._json_response = json_response or _VALID_LLM_RESPONSE
        self._text_response = text_response
        self.calls: list[dict] = []

    def generate(self, prompt, system_prompt, images=None, image_mime_types=None) -> str:
        self.calls.append({
            "method": "generate",
            "prompt": prompt,
            "image_count": len(images or []),
            "image_mime_types": image_mime_types or [],
        })
        return self._text_response

    def generate_json(self, prompt, system_prompt, images=None, image_mime_types=None) -> dict[str, Any]:
        self.calls.append({"method": "generate_json", "prompt": prompt})
        return self._json_response


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _create_tables():
    """Ensure tables exist before each test and drop after."""
    _clear_rate_limit_state()
    Base.metadata.create_all(bind=_TEST_ENGINE)
    yield
    _clear_rate_limit_state()
    Base.metadata.drop_all(bind=_TEST_ENGINE)


@pytest.fixture()
def mock_llm():
    return MockLLMClient()


@pytest.fixture()
def client(mock_llm: MockLLMClient):
    """httpx test client with DB and LLM overrides."""
    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_llm_client] = lambda: mock_llm
    with TestClient(app) as tc:
        yield tc
    app.dependency_overrides.clear()


@pytest.fixture()
def db():
    """Raw DB session for direct queries in tests."""
    session = TestSession()
    try:
        yield session
    finally:
        session.close()
