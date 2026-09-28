"""
Tests for rule-based consistency checks (consistency_rules.py).
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
from app.services.consistency_rules import run_consistency_checks


def _make_report(**overrides) -> AnalysisReport:
    """Helper to build an AnalysisReport with sensible defaults."""
    defaults = dict(
        patient_information=PatientInformation(name="Jane Doe", age="30", sex="Female"),
        symptoms=[EvidenceItem(text="Cough", evidence="cough noted", confidence="high")],
        diagnoses=[EvidenceItem(text="Bronchitis", evidence="diagnosed bronchitis", confidence="high")],
        medications=[],
        vitals=VitalsReport(),
        allergies=[],
        document_quality=DocumentQuality(readable=True, overall_confidence="high"),
    )
    defaults.update(overrides)
    return AnalysisReport(**defaults)


# ---------------------------------------------------------------------------
# Medication–allergy conflicts
# ---------------------------------------------------------------------------

class TestAllergyConflicts:
    def test_penicillin_allergy_with_amoxicillin(self):
        report = _make_report(
            allergies=[EvidenceItem(text="penicillin", evidence="allergic to penicillin", confidence="high")],
            medications=[
                MedicationItem(
                    text="Amoxicillin 500mg",
                    name="amoxicillin",
                    dose="500mg",
                    evidence="prescribed amoxicillin",
                    confidence="high",
                )
            ],
        )
        run_consistency_checks(report)
        texts = [i.text for i in report.potential_inconsistencies]
        assert any("allergy conflict" in t.lower() for t in texts)

    def test_no_conflict_when_no_matching_allergy(self):
        report = _make_report(
            allergies=[EvidenceItem(text="sulfa", evidence="sulfa allergy", confidence="high")],
            medications=[
                MedicationItem(
                    text="Amoxicillin 500mg",
                    name="amoxicillin",
                    dose="500mg",
                    evidence="prescribed amoxicillin",
                    confidence="high",
                )
            ],
        )
        run_consistency_checks(report)
        conflict_texts = [i.text.lower() for i in report.potential_inconsistencies]
        assert not any("allergy conflict" in t for t in conflict_texts)


# ---------------------------------------------------------------------------
# Implausible vitals
# ---------------------------------------------------------------------------

class TestImplausibleVitals:
    def test_hr_too_high(self):
        report = _make_report(
            vitals=VitalsReport(
                hr=EvidenceItem(text="250 bpm", evidence="HR 250", confidence="high")
            ),
        )
        run_consistency_checks(report)
        texts = [i.text.lower() for i in report.potential_inconsistencies]
        assert any("hr" in t and "implausible" in t for t in texts)

    def test_hr_too_low(self):
        report = _make_report(
            vitals=VitalsReport(
                hr=EvidenceItem(text="10 bpm", evidence="HR 10", confidence="high")
            ),
        )
        run_consistency_checks(report)
        texts = [i.text.lower() for i in report.potential_inconsistencies]
        assert any("hr" in t and "implausible" in t for t in texts)

    def test_normal_hr_no_flag(self):
        report = _make_report(
            vitals=VitalsReport(
                hr=EvidenceItem(text="72 bpm", evidence="HR 72", confidence="high")
            ),
        )
        run_consistency_checks(report)
        hr_issues = [i for i in report.potential_inconsistencies if "hr" in i.text.lower()]
        assert len(hr_issues) == 0

    def test_temp_too_high(self):
        report = _make_report(
            vitals=VitalsReport(
                temp=EvidenceItem(text="46.5 C", evidence="Temp 46.5", confidence="high")
            ),
        )
        run_consistency_checks(report)
        texts = [i.text.lower() for i in report.potential_inconsistencies]
        assert any("temp" in t and "implausible" in t for t in texts)

    def test_spo2_over_100(self):
        report = _make_report(
            vitals=VitalsReport(
                spo2=EvidenceItem(text="105%", evidence="SpO2 105%", confidence="high")
            ),
        )
        run_consistency_checks(report)
        texts = [i.text.lower() for i in report.potential_inconsistencies]
        assert any("spo2" in t and "implausible" in t for t in texts)

    def test_implausible_bp(self):
        report = _make_report(
            vitals=VitalsReport(
                bp=EvidenceItem(text="320/210 mmHg", evidence="BP 320/210", confidence="high")
            ),
        )
        run_consistency_checks(report)
        texts = [i.text.lower() for i in report.potential_inconsistencies]
        assert any("bp" in t and "implausible" in t for t in texts)


# ---------------------------------------------------------------------------
# Duplicate medications
# ---------------------------------------------------------------------------

class TestDuplicateMedications:
    def test_duplicate_detected(self):
        med = MedicationItem(
            text="Metformin 500mg", name="Metformin", dose="500mg",
            evidence="metformin prescribed", confidence="high",
        )
        report = _make_report(medications=[med, med.model_copy()])
        run_consistency_checks(report)
        texts = [i.text.lower() for i in report.potential_inconsistencies]
        assert any("duplicate" in t for t in texts)

    def test_plan_repetition_is_not_duplicate(self):
        report = _make_report(
            medications=[
                MedicationItem(
                    text="Sumatriptan 50mg PO as needed",
                    name="Sumatriptan",
                    dose="50mg",
                    route="PO",
                    frequency="as needed",
                    evidence="Current Meds: Sumatriptan 50mg PO as needed",
                    confidence="high",
                ),
                MedicationItem(
                    text="Sumatriptan 50mg PO at onset of symptoms",
                    name="Sumatriptan",
                    dose="50mg",
                    route="PO",
                    frequency="at onset of symptoms",
                    evidence="1. Sumatriptan 50mg PO at onset of symptoms",
                    confidence="high",
                ),
            ],
        )
        run_consistency_checks(report)
        texts = [i.text.lower() for i in report.potential_inconsistencies]
        assert not any("duplicate medication" in t for t in texts)

    def test_brand_and_generic_duplicate_detected(self):
        report = _make_report(
            medications=[
                MedicationItem(
                    text="Tylenol 500mg oral daily",
                    name="Tylenol",
                    dose="500mg",
                    route="oral",
                    frequency="daily",
                    evidence="Tylenol 500mg oral daily",
                    confidence="high",
                ),
                MedicationItem(
                    text="Acetaminophen 500mg oral daily",
                    name="Acetaminophen",
                    dose="500mg",
                    route="oral",
                    frequency="daily",
                    evidence="Acetaminophen 500mg oral daily",
                    confidence="high",
                ),
            ],
        )
        run_consistency_checks(report)
        texts = [i.text.lower() for i in report.potential_inconsistencies]
        assert any("duplicate medication" in t for t in texts)


# ---------------------------------------------------------------------------
# Diagnosis without symptoms
# ---------------------------------------------------------------------------

class TestDiagnosisWithoutSymptoms:
    def test_flagged_when_no_symptoms_or_observations(self):
        report = _make_report(
            symptoms=[],
            clinical_observations=[],
            diagnoses=[EvidenceItem(text="Diabetes", evidence="diabetes noted", confidence="high")],
        )
        run_consistency_checks(report)
        texts = [i.text.lower() for i in report.potential_inconsistencies]
        assert any("without" in t and "symptom" in t for t in texts)

    def test_not_flagged_when_symptoms_present(self):
        report = _make_report(
            symptoms=[EvidenceItem(text="Polyuria", evidence="polyuria", confidence="high")],
            diagnoses=[EvidenceItem(text="Diabetes", evidence="diabetes noted", confidence="high")],
        )
        run_consistency_checks(report)
        texts = [i.text.lower() for i in report.potential_inconsistencies]
        assert not any("without" in t and "symptom" in t for t in texts)


# ---------------------------------------------------------------------------
# Missing key fields
# ---------------------------------------------------------------------------

class TestMissingFields:
    def test_missing_age(self):
        report = _make_report(
            patient_information=PatientInformation(name="Jane Doe", age=None),
        )
        run_consistency_checks(report)
        texts = [i.text.lower() for i in report.missing_information]
        assert any("age" in t for t in texts)

    def test_missing_allergy_info(self):
        report = _make_report(allergies=[])
        run_consistency_checks(report)
        texts = [i.text.lower() for i in report.missing_information]
        assert any("allergy" in t for t in texts)

    def test_medication_without_dose(self):
        report = _make_report(
            medications=[
                MedicationItem(
                    text="Aspirin", name="Aspirin", dose=None,
                    evidence="aspirin prescribed", confidence="high",
                )
            ],
        )
        run_consistency_checks(report)
        texts = [i.text.lower() for i in report.missing_information]
        assert any("dose" in t for t in texts)

    def test_all_rule_check_items_labelled(self):
        """Every item added by consistency rules must have source='rule-check'."""
        report = _make_report(
            patient_information=PatientInformation(name="X", age=None),
            allergies=[],
        )
        run_consistency_checks(report)
        for item in report.potential_inconsistencies + report.missing_information:
            assert item.source == "rule-check", f"Item missing 'rule-check' label: {item.text}"

    def test_jane_smith_penicillin_and_missing_info(self):
        """Test the exact Jane Smith case: penicillin conflict, missing reaction, missing duration."""
        report = _make_report(
            patient_information=PatientInformation(name="Jane Smith", age="52", sex="female"),
            symptoms=[
                EvidenceItem(text="productive cough", evidence="Chief complaint: productive cough", confidence="high"),
                EvidenceItem(text="fever", evidence="fever 38.8 C", confidence="high"),
            ],
            diagnoses=[
                EvidenceItem(text="Community-acquired pneumonia", evidence="Impression: Community-acquired pneumonia", confidence="high"),
            ],
            medications=[
                MedicationItem(
                    text="Amoxicillin 500mg TID",
                    name="Amoxicillin",
                    dose="500mg",
                    frequency="TID",
                    evidence="Prescribed Amoxicillin 500mg TID",
                    confidence="high",
                ),
            ],
            vitals=VitalsReport(
                temp=EvidenceItem(text="38.8 C", evidence="fever 38.8 C", confidence="high"),
                hr=EvidenceItem(text="98", evidence="HR 98", confidence="high"),
                bp=EvidenceItem(text="130/85", evidence="BP 130/85", confidence="high"),
            ),
            allergies=[
                EvidenceItem(text="History of penicillin allergy", evidence="History of penicillin allergy", confidence="high"),
            ],
        )
        run_consistency_checks(report)

        # 1. Penicillin/Amoxicillin conflict flagged with rule-check
        conflicts = [
            i for i in report.potential_inconsistencies
            if "allergy conflict" in i.text.lower() and i.source == "rule-check"
        ]
        assert len(conflicts) >= 1
        assert "penicillin" in conflicts[0].text.lower()
        assert "amoxicillin" in conflicts[0].text.lower()

        # 2. Missing allergy reaction type flagged with rule-check
        missing_reaction = [
            i for i in report.missing_information
            if "reaction" in i.text.lower() and i.source == "rule-check"
        ]
        assert len(missing_reaction) >= 1

        # 3. Missing symptom duration flagged with rule-check
        missing_duration = [
            i for i in report.missing_information
            if "duration" in i.text.lower() and i.source == "rule-check"
        ]
        assert len(missing_duration) >= 1

