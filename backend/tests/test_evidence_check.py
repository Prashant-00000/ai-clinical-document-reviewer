"""
Tests for the hallucination-guard evidence validator (validators.py).
"""
from __future__ import annotations

import pytest

from app.schemas.analysis import (
    AnalysisReport,
    DocumentQuality,
    EvidenceItem,
    MedicationItem,
    PatientInformation,
    VitalsReport,
)
from app.services.validators import validate_evidence


_SOURCE_TEXT = (
    "Patient John Doe, 45 years old, male. "
    "Chief complaint: patient reports chest pain and shortness of breath. "
    "Vitals: BP 120/80, HR 72, Temp 37.2 C, RR 18, SpO2 98%. "
    "Allergic to penicillin. "
    "Prescribed amoxicillin 500mg PO TID. "
    "Diagnosed with acute bronchitis. "
    "Lungs: bilateral wheezing noted on auscultation."
)


def _make_report(**overrides) -> AnalysisReport:
    defaults = dict(
        patient_information=PatientInformation(name="John Doe", age="45", sex="Male"),
        document_quality=DocumentQuality(readable=True, overall_confidence="high"),
    )
    defaults.update(overrides)
    return AnalysisReport(**defaults)


# ---------------------------------------------------------------------------
# Evidence found — should keep confidence unchanged
# ---------------------------------------------------------------------------

class TestEvidenceFound:
    def test_exact_match_keeps_confidence(self):
        report = _make_report(
            symptoms=[
                EvidenceItem(text="Chest pain", evidence="patient reports chest pain", confidence="high"),
            ],
        )
        validate_evidence(report, _SOURCE_TEXT)
        assert report.symptoms[0].confidence == "high"
        assert len(report.requires_review) == 0

    def test_partial_fuzzy_match_keeps_confidence(self):
        report = _make_report(
            symptoms=[
                EvidenceItem(text="Chest pain", evidence="chest pain", confidence="high"),
            ],
        )
        validate_evidence(report, _SOURCE_TEXT)
        assert report.symptoms[0].confidence == "high"

    def test_case_insensitive_match(self):
        report = _make_report(
            symptoms=[
                EvidenceItem(text="Chest pain", evidence="PATIENT REPORTS CHEST PAIN", confidence="high"),
            ],
        )
        validate_evidence(report, _SOURCE_TEXT)
        assert report.symptoms[0].confidence == "high"


# ---------------------------------------------------------------------------
# Evidence NOT found — should lower confidence and add to requires_review
# ---------------------------------------------------------------------------

class TestEvidenceNotFound:
    def test_fabricated_evidence_lowers_confidence(self):
        report = _make_report(
            symptoms=[
                EvidenceItem(
                    text="Headache",
                    evidence="patient complained of severe migraine headache",
                    confidence="high",
                ),
            ],
        )
        validate_evidence(report, _SOURCE_TEXT)
        assert report.symptoms[0].confidence == "low"

    def test_fabricated_evidence_added_to_requires_review(self):
        report = _make_report(
            symptoms=[
                EvidenceItem(
                    text="Nausea",
                    evidence="patient experienced nausea and vomiting",
                    confidence="high",
                ),
            ],
        )
        validate_evidence(report, _SOURCE_TEXT)
        assert len(report.requires_review) == 1
        assert "evidence not verified" in report.requires_review[0].text.lower()

    def test_medication_evidence_check(self):
        report = _make_report(
            medications=[
                MedicationItem(
                    text="Ibuprofen 400mg",
                    name="Ibuprofen",
                    dose="400mg",
                    evidence="prescribed ibuprofen 400mg for inflammation",
                    confidence="high",
                ),
            ],
        )
        validate_evidence(report, _SOURCE_TEXT)
        assert report.medications[0].confidence == "low"
        assert len(report.requires_review) >= 1

    def test_vitals_evidence_check(self):
        report = _make_report(
            vitals=VitalsReport(
                hr=EvidenceItem(text="110 bpm", evidence="HR 110 tachycardic", confidence="high"),
            ),
        )
        validate_evidence(report, _SOURCE_TEXT)
        assert report.vitals.hr.confidence == "low"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_evidence_is_not_flagged(self):
        """Items with empty evidence should pass (nothing to verify)."""
        report = _make_report(
            symptoms=[
                EvidenceItem(text="Cough", evidence="", confidence="high"),
            ],
        )
        validate_evidence(report, _SOURCE_TEXT)
        assert report.symptoms[0].confidence == "high"
        assert len(report.requires_review) == 0

    def test_not_documented_evidence_passes(self):
        report = _make_report(
            symptoms=[
                EvidenceItem(text="Cough", evidence="not documented", confidence="medium"),
            ],
        )
        validate_evidence(report, _SOURCE_TEXT)
        assert len(report.requires_review) == 0

    def test_multiple_items_independently_checked(self):
        report = _make_report(
            symptoms=[
                EvidenceItem(text="Chest pain", evidence="patient reports chest pain", confidence="high"),
                EvidenceItem(text="Nausea", evidence="patient vomited repeatedly", confidence="high"),
            ],
        )
        validate_evidence(report, _SOURCE_TEXT)
        # First should pass, second should fail
        assert report.symptoms[0].confidence == "high"
        assert report.symptoms[1].confidence == "low"
        assert len(report.requires_review) == 1
