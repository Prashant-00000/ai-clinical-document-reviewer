"""
Pydantic v2 schemas for the structured clinical analysis report.

Every clinical list item carries {text, evidence, confidence} so the UI can
show provenance and the hallucination guard can verify evidence.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# Atomic building blocks
# ---------------------------------------------------------------------------

class EvidenceItem(BaseModel):
    """A single extracted clinical item with its provenance."""
    text: str = Field(..., description="Concise description of the item")
    evidence: str = Field("", description="Exact quote from the source document")
    confidence: Literal["high", "medium", "low"] = Field(
        "medium", description="Confidence level of the extraction"
    )
    source: str | None = Field(
        None, description="Origin label, e.g. 'rule-check' for consistency rules"
    )


class MedicationItem(BaseModel):
    """A medication with structured subfields plus evidence."""
    text: str = Field(..., description="Full medication description")
    name: str | None = Field(None, description="Drug name")
    dose: str | None = Field(None, description="Dosage")
    route: str | None = Field(None, description="Route of administration")
    frequency: str | None = Field(None, description="Dosing frequency")
    evidence: str = Field("", description="Exact quote from the source document")
    confidence: Literal["high", "medium", "low"] = Field("medium")
    source: str | None = None


# ---------------------------------------------------------------------------
# Composite sections
# ---------------------------------------------------------------------------

class PatientInformation(BaseModel):
    name: str | None = None
    age: str | None = None
    sex: str | None = None
    id: str | None = None
    other: dict[str, str] = Field(default_factory=dict)


class VitalsReport(BaseModel):
    bp: EvidenceItem | None = None
    hr: EvidenceItem | None = None
    temp: EvidenceItem | None = None
    rr: EvidenceItem | None = None
    spo2: EvidenceItem | None = None
    other: list[EvidenceItem] = Field(default_factory=list)


class DocumentQuality(BaseModel):
    readable: bool = True
    notes: str | None = None
    overall_confidence: Literal["high", "medium", "low"] = "medium"


# ---------------------------------------------------------------------------
# Top-level analysis report
# ---------------------------------------------------------------------------

class AnalysisReport(BaseModel):
    """The full structured clinical analysis produced by the pipeline."""
    report_summary: str = Field("", description="Concise 4-6 line report summary")

    patient_information: PatientInformation = Field(default_factory=PatientInformation)

    symptoms: list[EvidenceItem] = Field(default_factory=list)
    diagnoses: list[EvidenceItem] = Field(default_factory=list)
    medications: list[MedicationItem] = Field(default_factory=list)
    vitals: VitalsReport | None = Field(default_factory=VitalsReport)
    allergies: list[EvidenceItem] = Field(default_factory=list)

    clinical_observations: list[EvidenceItem] = Field(default_factory=list)
    clinical_concerns: list[EvidenceItem] = Field(default_factory=list)

    missing_information: list[EvidenceItem] = Field(default_factory=list)
    potential_inconsistencies: list[EvidenceItem] = Field(default_factory=list)
    requires_review: list[EvidenceItem] = Field(default_factory=list)

    document_quality: DocumentQuality = Field(default_factory=DocumentQuality)

    @model_validator(mode="before")
    @classmethod
    def check_clinical_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            known_keys = {
                "patient_information", "symptoms", "diagnoses", "medications",
                "vitals", "allergies", "clinical_observations", "clinical_concerns",
                "missing_information", "potential_inconsistencies", "requires_review",
                "document_quality", "report_summary"
            }
            if not known_keys.intersection(data.keys()):
                raise ValueError("Response missing expected clinical schema fields")
        return data
