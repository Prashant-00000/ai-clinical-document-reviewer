"""
Hallucination-guard: evidence validation.

For every extracted item that carries an ``evidence`` quote, we check that the
quote actually appears in the original source text (normalised, with fuzzy
matching via rapidfuzz).  Items whose evidence cannot be found in the source
get their confidence lowered to ``"low"`` and are added to ``requires_review``.
"""
from __future__ import annotations

import logging
import re

from rapidfuzz import fuzz

from app.schemas.analysis import AnalysisReport, EvidenceItem, MedicationItem

logger = logging.getLogger(__name__)

# Fuzzy-match threshold (0–100).  75 is lenient enough for minor OCR / LLM
# paraphrasing while still catching fabricated quotes.
_THRESHOLD = 75.0


# ---------------------------------------------------------------------------
# Text normalisation
# ---------------------------------------------------------------------------

def _normalise(text: str) -> str:
    """Lower-case, collapse whitespace, strip non-alphanumeric (except spaces)."""
    t = text.lower().strip()
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"[^\w\s]", "", t)
    return t


# ---------------------------------------------------------------------------
# Core check
# ---------------------------------------------------------------------------

def _evidence_found(evidence: str, source: str) -> bool:
    """Return True if *evidence* appears in *source* (normalised, fuzzy)."""
    if not evidence or evidence.lower() in (
        "not documented", "n/a", "none", "not found", "",
    ):
        return True  # nothing to verify

    ev = _normalise(evidence)
    if not ev:
        return True

    src = _normalise(source)

    # 1) Exact substring
    if ev in src:
        return True

    # 2) Fuzzy partial match
    return fuzz.partial_ratio(ev, src) >= _THRESHOLD


# ---------------------------------------------------------------------------
# Bulk validation helpers
# ---------------------------------------------------------------------------

def _check_items(
    items: list[EvidenceItem],
    source: str,
    review_list: list[EvidenceItem],
    label: str,
) -> None:
    for item in items:
        if not _evidence_found(item.evidence, source):
            logger.info("Evidence not found for %s item: %s", label, item.text)
            item.confidence = "low"
            review_list.append(
                EvidenceItem(
                    text=f"[{label}] Evidence not verified: {item.text}",
                    evidence=item.evidence,
                    confidence="low",
                    source="evidence-check",
                )
            )


def _check_medications(
    meds: list[MedicationItem],
    source: str,
    review_list: list[EvidenceItem],
) -> None:
    for med in meds:
        if not _evidence_found(med.evidence, source):
            logger.info("Evidence not found for medication: %s", med.text)
            med.confidence = "low"
            review_list.append(
                EvidenceItem(
                    text=f"[medications] Evidence not verified: {med.text}",
                    evidence=med.evidence,
                    confidence="low",
                    source="evidence-check",
                )
            )


def _check_vitals(
    report: AnalysisReport,
    source: str,
    review_list: list[EvidenceItem],
) -> None:
    if not report.vitals:
        return
    for field_name in ("bp", "hr", "temp", "rr", "spo2"):
        item: EvidenceItem | None = getattr(report.vitals, field_name, None)
        if item and not _evidence_found(item.evidence, source):
            logger.info("Evidence not found for vital %s: %s", field_name, item.text)
            item.confidence = "low"
            review_list.append(
                EvidenceItem(
                    text=f"[vitals.{field_name}] Evidence not verified: {item.text}",
                    evidence=item.evidence,
                    confidence="low",
                    source="evidence-check",
                )
            )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate_evidence(report: AnalysisReport, source_text: str) -> AnalysisReport:
    """Check every evidence quote against *source_text*.

    Items that fail verification:
      • have their ``confidence`` lowered to ``"low"``
      • are appended to ``report.requires_review``

    Operates **in-place** and returns the same object for convenience.
    """
    review: list[EvidenceItem] = []

    _check_items(report.symptoms, source_text, review, "symptoms")
    _check_items(report.diagnoses, source_text, review, "diagnoses")
    _check_items(report.allergies, source_text, review, "allergies")
    _check_items(report.clinical_observations, source_text, review, "observations")
    _check_items(report.clinical_concerns, source_text, review, "concerns")

    _check_medications(report.medications, source_text, review)
    _check_vitals(report, source_text, review)

    report.requires_review.extend(review)
    return report
