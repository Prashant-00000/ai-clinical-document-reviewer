"""
Integration tests for the /api/analyze endpoint.

Covers: successful text analysis, file upload, malformed LLM output (mocked),
and the report lifecycle (processing → completed | failed).
"""
from __future__ import annotations

import io
import json
from typing import Any
from copy import deepcopy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app
from app.services.llm_client import LLMClient, LLMError, get_llm_client
from tests.conftest import MockLLMClient, TestSession, _override_get_db, _VALID_LLM_RESPONSE


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _client_with_llm(mock: LLMClient) -> TestClient:
    """Build a TestClient wired to the given mock LLM."""
    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_llm_client] = lambda: mock
    return TestClient(app)


# ---------------------------------------------------------------------------
# Successful text analysis
# ---------------------------------------------------------------------------

class TestTextAnalysis:
    def test_text_analysis_returns_200(self, client: TestClient):
        clinical_text = (
            "Patient John Doe, 45 years old, male. "
            "Chief complaint: patient reports chest pain and shortness of breath. "
            "Vitals: BP 120/80, HR 72, Temp 37.2 C, RR 18, SpO2 98%. "
            "Allergic to penicillin. Prescribed amoxicillin 500mg PO TID. "
            "Diagnosed with acute bronchitis. Bilateral wheezing noted."
        )
        resp = client.post("/api/analyze", data={"text": clinical_text})
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] in ("completed", "completed_with_warnings")
        assert body["input_type"] == "text"
        assert body["report"] is not None

    def test_report_has_summary(self, client: TestClient):
        resp = client.post("/api/analyze", data={"text": "Patient Jane, age 30."})
        body = resp.json()
        assert body["report"]["report_summary"]

    def test_report_saved_to_history(self, client: TestClient):
        client.post("/api/analyze", data={"text": "Patient data here."})
        resp = client.get("/api/reports")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_summary_consistency_with_report_arrays(self, client: TestClient):
        """Assert every count and item mentioned in report_summary exists in the report arrays."""
        resp = client.post("/api/analyze", data={"text": "Patient John Doe, 45, male. Chest pain. BP 120/80."})
        assert resp.status_code == 200
        report = resp.json()["report"]
        summary = report["report_summary"]
        lines = [line.strip() for line in summary.splitlines() if line.strip()]

        # Must be 4 to 6 lines
        assert 4 <= len(lines) <= 6

        # Line 1: Must be critical flags
        assert lines[0].startswith("CRITICAL FLAGS:")

        # Review count in summary must match len(requires_review)
        expected_review_count = len(report["requires_review"])
        expected_inconsistency_count = len(report["potential_inconsistencies"])
        assert f"{expected_review_count} item(s) require clinical review" in summary
        assert f"{expected_inconsistency_count} inconsistency flagged" in summary or f"{expected_inconsistency_count} inconsistencies flagged" in summary

        # Missing information items mentioned in summary must exist in missing_information array
        missing_line = [l for l in lines if l.startswith("Missing Information:")][0]
        if "None flagged" not in missing_line:
            actual_missing_texts = {m["text"] for m in report["missing_information"]}
            items_str = missing_line.replace("Missing Information:", "").rstrip(".")
            for item in items_str.split(";"):
                item_clean = item.strip()
                if item_clean:
                    assert any(item_clean in actual or actual in item_clean for actual in actual_missing_texts)


class TestSyntheticSamples:
    def test_recipe_returns_no_clinical_content(self):
        recipe_response = deepcopy(_VALID_LLM_RESPONSE)
        recipe_response.update({
            "patient_information": {"name": None, "age": None, "sex": None, "id": None, "other": {}},
            "symptoms": [],
            "diagnoses": [],
            "medications": [],
            "vitals": {"other": []},
            "allergies": [],
            "clinical_observations": [],
            "clinical_concerns": [],
            "missing_information": [],
            "potential_inconsistencies": [],
            "requires_review": [],
            "document_quality": {
                "readable": True,
                "notes": "No clinical content detected (non-medical document / recipe).",
                "overall_confidence": "high",
            },
        })
        tc = _client_with_llm(MockLLMClient(json_response=recipe_response))
        try:
            recipe = Path(__file__).resolve().parents[2] / "samples" / "irrelevant_text.txt"
            response = tc.post("/api/analyze", data={"text": recipe.read_text(encoding="utf-8")})
            assert response.status_code == 200
            report = response.json()["report"]
            assert response.json()["status"] == "no_clinical_content"
            assert report["symptoms"] == []
            assert report["medications"] == []
            assert report["diagnoses"] == []
            assert report["potential_inconsistencies"] == []
            assert report["report_summary"].startswith("NO CLINICAL CONTENT:")
        finally:
            app.dependency_overrides.clear()

    def test_scanned_pdf_uses_vision_fallback(self):
        mock = MockLLMClient(text_response="Patient Arthur Dent, age 64.")
        tc = _client_with_llm(mock)
        try:
            pdf = Path(__file__).resolve().parents[2] / "samples" / "scanned_note.pdf"
            response = tc.post(
                "/api/analyze",
                files={"file": (pdf.name, pdf.read_bytes(), "application/pdf")},
            )
            assert response.status_code == 200
            quality_notes = response.json()["report"]["document_quality"]["notes"]
            assert "scanned" in quality_notes.lower()
            vision_calls = [call for call in mock.calls if call["method"] == "generate"]
            assert vision_calls and vision_calls[0]["image_count"] == 1
            assert vision_calls[0]["image_mime_types"] == ["image/png"]
        finally:
            app.dependency_overrides.clear()

    def test_inconsistent_note_returns_rule_check_warnings(self):
        inconsistent_response = deepcopy(_VALID_LLM_RESPONSE)
        inconsistent_response.update({
            "patient_information": {
                "name": "Arthur Dent", "age": "64", "sex": "Male", "id": "SYN-49201", "other": {},
            },
            "symptoms": [],
            "diagnoses": [{
                "text": "Acute cystitis",
                "evidence": "Acute cystitis (no symptoms, dysuria, or physical findings documented).",
                "confidence": "high",
            }],
            "medications": [
                {"text": "Amoxicillin 500mg PO TID", "name": "Amoxicillin", "dose": "500mg", "route": "PO", "frequency": "TID", "evidence": "Amoxicillin 500mg PO TID", "confidence": "high"},
                {"text": "Lisinopril 10mg PO daily", "name": "Lisinopril", "dose": "10mg", "route": "PO", "frequency": "daily", "evidence": "Lisinopril 10mg PO daily", "confidence": "high"},
                {"text": "Lisinopril 20mg PO daily", "name": "Lisinopril", "dose": "20mg", "route": "PO", "frequency": "daily", "evidence": "Lisinopril 20mg PO daily", "confidence": "high"},
            ],
            "vitals": {
                "bp": {"text": "125/80 mmHg", "evidence": "125/80", "confidence": "high"},
                "hr": {"text": "300 bpm", "evidence": "HR: 300 bpm", "confidence": "high"},
                "temp": {"text": "20.0 C", "evidence": "Temperature: 20.0 C", "confidence": "high"},
                "rr": {"text": "16 breaths/min", "evidence": "Respiratory Rate: 16 breaths/min", "confidence": "high"},
                "spo2": {"text": "98%", "evidence": "SpO2: 98%", "confidence": "high"},
                "other": [],
            },
            "allergies": [{
                "text": "Severe penicillin allergy",
                "evidence": "Severe penicillin allergy (reported previous hives and throat swelling)",
                "confidence": "high",
            }],
            "clinical_observations": [],
            "clinical_concerns": [],
            "missing_information": [],
            "potential_inconsistencies": [],
            "requires_review": [],
        })
        tc = _client_with_llm(MockLLMClient(json_response=inconsistent_response))
        try:
            note = Path(__file__).resolve().parents[2] / "samples" / "inconsistent_note.txt"
            response = tc.post("/api/analyze", data={"text": note.read_text(encoding="utf-8")})
            assert response.status_code == 200
            body = response.json()
            assert body["status"] == "completed_with_warnings"
            flags = " ".join(item["text"] for item in body["report"]["potential_inconsistencies"])
            assert "allergy conflict" in flags
            assert "HR" in flags and "TEMP" in flags
            assert "Duplicate medication" in flags
            assert "without any supporting symptoms" in flags
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Malformed LLM output — mock returns garbage
# ---------------------------------------------------------------------------

class TestMalformedLLMOutput:
    def test_invalid_json_structure_returns_502(self):
        """LLM returns JSON that doesn't match the schema (even after retry)."""
        bad_response = {"garbage": True, "not_a_valid_report": 123}
        mock = MockLLMClient(json_response=bad_response)
        tc = _client_with_llm(mock)
        try:
            resp = tc.post("/api/analyze", data={"text": "Test clinical note."})
            # The ValidationError will be caught and returned as 502
            assert resp.status_code == 502
            body = resp.json()
            assert body["error"]["code"] in ("LLM_SCHEMA_ERROR", "LLM_FAILURE")
        finally:
            app.dependency_overrides.clear()

    def test_llm_network_error_returns_502(self):
        """Simulate a network / API failure."""

        class FailingLLM(LLMClient):
            def generate(self, *a, **kw):
                raise LLMError("Connection refused")

            def generate_json(self, *a, **kw):
                raise LLMError("Connection refused")

        tc = _client_with_llm(FailingLLM())
        try:
            resp = tc.post("/api/analyze", data={"text": "Some clinical text."})
            assert resp.status_code == 502
            assert resp.json()["error"]["code"] == "LLM_FAILURE"
        finally:
            app.dependency_overrides.clear()

    def test_failed_report_saved_in_history(self):
        """Even failed analyses should appear in GET /api/reports."""

        class FailingLLM(LLMClient):
            def generate(self, *a, **kw):
                raise LLMError("timeout")

            def generate_json(self, *a, **kw):
                raise LLMError("timeout")

        tc = _client_with_llm(FailingLLM())
        try:
            tc.post("/api/analyze", data={"text": "Clinical note."})
            reports = tc.get("/api/reports").json()
            failed = [r for r in reports if r["status"] == "failed"]
            assert len(failed) >= 1
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Report CRUD
# ---------------------------------------------------------------------------

class TestReportCRUD:
    def test_get_report_by_id(self, client: TestClient):
        resp = client.post("/api/analyze", data={"text": "Patient data."})
        report_id = resp.json()["id"]
        detail = client.get(f"/api/reports/{report_id}")
        assert detail.status_code == 200
        assert detail.json()["id"] == report_id

    def test_get_nonexistent_report_returns_404(self, client: TestClient):
        resp = client.get("/api/reports/does-not-exist")
        assert resp.status_code == 404

    def test_delete_report(self, client: TestClient):
        resp = client.post("/api/analyze", data={"text": "Patient data."})
        report_id = resp.json()["id"]
        del_resp = client.delete(f"/api/reports/{report_id}")
        assert del_resp.status_code == 200
        # Should be gone now
        assert client.get(f"/api/reports/{report_id}").status_code == 404


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

class TestHealth:
    def test_health_endpoint(self, client: TestClient):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
