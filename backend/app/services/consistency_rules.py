"""
Rule-based consistency checks — entirely independent of the LLM.

Checks:
  1. Medication–allergy conflicts (built-in map).
  2. Implausible vital signs.
  3. Duplicate medications.
  4. Diagnosis without any related symptom / observation.
  5. Missing key fields (age, allergies, medication doses).

Findings are appended to ``potential_inconsistencies`` or
``missing_information`` with ``source="rule-check"``.
"""
from __future__ import annotations

import logging
import re

from app.schemas.analysis import AnalysisReport, EvidenceItem

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------

ALLERGY_MEDICATION_CONFLICTS: dict[str, list[str]] = {
    "penicillin": [
        "amoxicillin", "ampicillin", "piperacillin", "nafcillin",
        "oxacillin", "augmentin", "amoxicillin-clavulanate",
    ],
    "sulfa": [
        "sulfamethoxazole", "trimethoprim-sulfamethoxazole",
        "bactrim", "sulfasalazine", "co-trimoxazole",
    ],
    "sulfonamide": [
        "sulfamethoxazole", "trimethoprim-sulfamethoxazole",
        "bactrim", "sulfasalazine", "co-trimoxazole",
    ],
    "nsaid": [
        "ibuprofen", "naproxen", "aspirin", "diclofenac",
        "ketorolac", "meloxicam", "celecoxib", "indomethacin",
    ],
    "aspirin": ["aspirin"],
    "cephalosporin": [
        "cephalexin", "ceftriaxone", "cefazolin", "cefdinir",
        "cefuroxime", "ceftazidime", "cefepime",
    ],
    "codeine": ["codeine", "tramadol"],
    "morphine": ["morphine", "hydromorphone", "oxycodone", "fentanyl"],
    "ace inhibitor": [
        "lisinopril", "enalapril", "ramipril", "captopril", "benazepril",
    ],
    "statin": [
        "atorvastatin", "simvastatin", "rosuvastatin", "pravastatin",
    ],
}

# (min, max) — values outside this range are implausible
VITAL_RANGES: dict[str, tuple[float, float]] = {
    "hr": (20, 220),
    "temp": (30.0, 45.0),
    "spo2": (0, 100),
    "rr": (4, 60),
}

BP_RANGES = {
    "systolic": (50, 300),
    "diastolic": (20, 200),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_number(text: str) -> float | None:
    """Pull the first numeric value out of a string."""
    m = re.search(r"[\d]+\.?[\d]*", text)
    return float(m.group()) if m else None


def _parse_bp(text: str) -> tuple[float | None, float | None]:
    """Parse '120/80' style blood pressure."""
    m = re.search(r"(\d+)\s*/\s*(\d+)", text)
    if m:
        return float(m.group(1)), float(m.group(2))
    return None, None


def _norm(s: str) -> str:
    return s.lower().strip()


# ---------------------------------------------------------------------------
# Individual rule implementations
# ---------------------------------------------------------------------------

def _check_allergy_medication_conflicts(
    report: AnalysisReport,
    findings: list[EvidenceItem],
) -> None:
    allergy_names = [_norm(a.text) for a in report.allergies]

    for allergy_key, conflicting_meds in ALLERGY_MEDICATION_CONFLICTS.items():
        has_allergy = any(allergy_key in name or name in allergy_key for name in allergy_names)
        if not has_allergy:
            continue
        for med in report.medications:
            med_name = _norm(med.name or med.text)
            for conflict in conflicting_meds:
                if conflict in med_name or med_name in conflict:
                    findings.append(
                        EvidenceItem(
                            text=(
                                f"Potential allergy conflict: patient has "
                                f"'{allergy_key}' allergy but is prescribed "
                                f"'{med.name or med.text}'."
                            ),
                            evidence=f"Allergy: {allergy_key}; Medication: {med.name or med.text}",
                            confidence="high",
                            source="rule-check",
                        )
                    )
                    break


def _check_implausible_vitals(
    report: AnalysisReport,
    findings: list[EvidenceItem],
) -> None:
    if not report.vitals:
        return

    # HR, Temp, SpO2, RR
    for field_name, (lo, hi) in VITAL_RANGES.items():
        item = getattr(report.vitals, field_name, None)
        if not item:
            continue
        val = _extract_number(item.text)
        if val is not None and (val < lo or val > hi):
            findings.append(
                EvidenceItem(
                    text=(
                        f"Implausible {field_name.upper()} value: {item.text} "
                        f"(expected {lo}–{hi})."
                    ),
                    evidence=item.text,
                    confidence="high",
                    source="rule-check",
                )
            )

    # Blood pressure
    bp = report.vitals.bp
    if bp:
        sys_val, dia_val = _parse_bp(bp.text)
        if sys_val is not None:
            lo, hi = BP_RANGES["systolic"]
            if sys_val < lo or sys_val > hi:
                findings.append(
                    EvidenceItem(
                        text=f"Implausible systolic BP: {sys_val} (expected {lo}–{hi}).",
                        evidence=bp.text,
                        confidence="high",
                        source="rule-check",
                    )
                )
        if dia_val is not None:
            lo, hi = BP_RANGES["diastolic"]
            if dia_val < lo or dia_val > hi:
                findings.append(
                    EvidenceItem(
                        text=f"Implausible diastolic BP: {dia_val} (expected {lo}–{hi}).",
                        evidence=bp.text,
                        confidence="high",
                        source="rule-check",
                    )
                )


MEDICATION_ALIASES = {
    "tylenol": "acetaminophen",
    "paracetamol": "acetaminophen",
    "advil": "ibuprofen",
    "motrin": "ibuprofen",
}

_MEDICATION_DETAIL_RE = re.compile(
    r"\b(?:\d+(?:\.\d+)?\s*(?:mg|mcg|g|ml|units?|%)?|"
    r"po|iv|im|sc|sq|oral|by mouth|topical|tablet|tab|capsule|caps|"
    r"tid|bid|qd|qhs|prn|daily|weekly|every|as needed)\b",
    re.IGNORECASE,
)


def _norm_med_name(med) -> str:
    """Normalize a medication identity without using its dosing details."""
    raw = med.name.strip() if med.name and med.name.strip() else med.text
    cleaned = _MEDICATION_DETAIL_RE.sub(" ", raw.lower())
    cleaned = re.sub(r"[^a-z0-9\s-]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return MEDICATION_ALIASES.get(cleaned, cleaned)


def _dosing_signature(med) -> tuple[str, str, str]:
    """Return normalized dose, route, and frequency for duplicate comparison."""
    dose = _norm(med.dose or "")
    route = _norm(med.route or "")
    frequency = _norm(med.frequency or "")
    return dose, route, frequency


def _prn_onset_pair(first, second) -> bool:
    """Treat an as-needed medication and its onset instruction as one regimen."""
    frequencies = {_norm(first.frequency or ""), _norm(second.frequency or "")}
    return frequencies == {"as needed", "at onset of symptoms"}


def _check_duplicate_medications(
    report: AnalysisReport,
    findings: list[EvidenceItem],
) -> None:
    seen: dict[str, list] = {}
    for med in report.medications:
        key = _norm_med_name(med)
        seen.setdefault(key, []).append(med)

    for name, medications in seen.items():
        if len(medications) < 2:
            continue

        duplicate_pairs: list[tuple] = []
        for index, first in enumerate(medications):
            for second in medications[index + 1:]:
                if _dosing_signature(first) == _dosing_signature(second):
                    duplicate_pairs.append((first, second))
                elif not _prn_onset_pair(first, second):
                    duplicate_pairs.append((first, second))

        if duplicate_pairs:
            display_items = [med.name or med.text for med in medications]
            findings.append(
                EvidenceItem(
                    text=f"Duplicate medication: '{name}' appears {len(medications)} times.",
                    evidence=", ".join(display_items),
                    confidence="high",
                    source="rule-check",
                )
            )


def has_clinical_content(report: AnalysisReport) -> bool:
    """Check if the report contains any meaningful clinical content."""
    pi = report.patient_information
    has_pi = bool((pi.name and pi.name.strip()) or (pi.age and pi.age.strip()) or (pi.id and pi.id.strip()))
    has_clinical = bool(
        has_pi
        or report.diagnoses
        or report.symptoms
        or report.medications
        or report.allergies
        or (report.vitals and any([report.vitals.bp, report.vitals.hr, report.vitals.temp, report.vitals.rr, report.vitals.spo2]))
        or report.clinical_observations
        or report.clinical_concerns
    )
    if report.document_quality and report.document_quality.notes:
        notes_lower = report.document_quality.notes.lower()
        if "no clinical" in notes_lower or "non-medical" in notes_lower or "recipe" in notes_lower:
            return False
    return has_clinical


def _check_diagnosis_without_symptoms(
    report: AnalysisReport,
    findings: list[EvidenceItem],
) -> None:
    if report.diagnoses and not report.symptoms and not report.clinical_observations:
        for dx in report.diagnoses:
            findings.append(
                EvidenceItem(
                    text=f"Diagnosis '{dx.text}' documented without any supporting symptoms or observations.",
                    evidence=dx.evidence,
                    confidence="medium",
                    source="rule-check",
                )
            )


def _check_missing_key_fields(
    report: AnalysisReport,
    missing: list[EvidenceItem],
) -> None:
    pi = report.patient_information

    if not pi.age:
        missing.append(
            EvidenceItem(
                text="Patient age is not documented.",
                evidence="not documented",
                confidence="high",
                source="rule-check",
            )
        )

    if not report.allergies:
        missing.append(
            EvidenceItem(
                text="Allergy information is not documented.",
                evidence="not documented",
                confidence="high",
                source="rule-check",
            )
        )

    # Medications without dose
    for med in report.medications:
        if not med.dose:
            missing.append(
                EvidenceItem(
                    text=f"Dose not documented for medication '{med.name or med.text}'.",
                    evidence=med.evidence or "not documented",
                    confidence="medium",
                    source="rule-check",
                )
            )

    # Allergy reaction type / severity
    for allergy in report.allergies:
        norm_a = _norm(allergy.text)
        reaction_keywords = ["rash", "hive", "anaphylax", "swell", "itch", "angioedema", "dyspnea", "reaction:"]
        has_reaction = any(kw in norm_a or (allergy.evidence and kw in _norm(allergy.evidence)) for kw in reaction_keywords)
        if not has_reaction:
            missing.append(
                EvidenceItem(
                    text=f"Allergy reaction type / severity is not documented for '{allergy.text}' (e.g. anaphylaxis, hives, rash).",
                    evidence="not documented",
                    confidence="high",
                    source="rule-check",
                )
            )

    # Symptom duration / onset
    if report.symptoms:
        duration_keywords = ["day", "week", "month", "hour", "yesterday", "since", "acute", "chronic", "onset", "duration", "ago"]
        has_duration = any(
            any(kw in _norm(s.text) or (s.evidence and kw in _norm(s.evidence)) for kw in duration_keywords)
            for s in report.symptoms
        )
        if not has_duration:
            missing.append(
                EvidenceItem(
                    text="Exact duration or onset of symptoms is not documented.",
                    evidence="not documented",
                    confidence="high",
                    source="rule-check",
                )
            )


    # Respiratory rate (RR) and Oxygen saturation (SpO2) missing checks
    has_rr = bool(report.vitals and report.vitals.rr and report.vitals.rr.text)
    if not has_rr:
        missing.append(
            EvidenceItem(
                text="Respiratory rate (RR) is not documented.",
                evidence="not documented",
                confidence="high",
                source="rule-check",
            )
        )

    has_spo2 = bool(report.vitals and report.vitals.spo2 and report.vitals.spo2.text)
    if not has_spo2:
        missing.append(
            EvidenceItem(
                text="Oxygen saturation (SpO2) is not documented.",
                evidence="not documented",
                confidence="high",
                source="rule-check",
            )
        )


def _merge_findings(existing_list: list[EvidenceItem], new_items: list[EvidenceItem]) -> list[EvidenceItem]:
    """Merge new_items into existing_list, replacing duplicates with the rule-check version."""
    result = list(existing_list)
    for new_item in new_items:
        norm_new = _norm(new_item.text)
        is_duplicate = False
        for idx, existing in enumerate(result):
            norm_existing = _norm(existing.text)
            # Allergy conflict duplicate
            if ("penicillin" in norm_new and "amoxicillin" in norm_new) and \
               ("penicillin" in norm_existing and "amoxicillin" in norm_existing):
                result[idx] = new_item
                is_duplicate = True
                break
            # RR duplicate
            if ("respiratory rate" in norm_new or " rr" in norm_new) and \
               ("respiratory rate" in norm_existing or " rr" in norm_existing):
                result[idx] = new_item
                is_duplicate = True
                break
            # SpO2 duplicate
            if ("spo2" in norm_new or "oxygen" in norm_new) and \
               ("spo2" in norm_existing or "oxygen" in norm_existing):
                result[idx] = new_item
                is_duplicate = True
                break
            # Exact or substring match
            if norm_new == norm_existing or (len(norm_new) > 15 and norm_new in norm_existing) or (len(norm_existing) > 15 and norm_existing in norm_new):
                result[idx] = new_item
                is_duplicate = True
                break
        if not is_duplicate:
            result.append(new_item)
    return result


def _ensure_symptom_coverage(report: AnalysisReport) -> None:
    """Ensure fever/elevated temp is recorded in symptoms if present in vitals,
    and ensure symptoms are only deduplicated against other symptoms."""
    # Deduplicate symptoms only against other symptoms
    unique_symptoms: list[EvidenceItem] = []
    seen_norm: set[str] = set()
    for s in report.symptoms:
        key = _norm(s.text)
        if key not in seen_norm:
            seen_norm.add(key)
            unique_symptoms.append(s)
    report.symptoms = unique_symptoms

    # If vitals.temp indicates fever or mentions fever, ensure Fever is in symptoms
    if report.vitals and report.vitals.temp:
        temp_text = _norm(report.vitals.temp.text)
        temp_ev = _norm(report.vitals.temp.evidence or "")
        temp_val = _extract_number(report.vitals.temp.text)
        is_fever = (temp_val is not None and temp_val >= 37.8) or "fever" in temp_text or "fever" in temp_ev
        if is_fever:
            has_fever_symptom = any("fever" in _norm(s.text) or "pyrexia" in _norm(s.text) for s in report.symptoms)
            if not has_fever_symptom:
                ev = report.vitals.temp.evidence or report.vitals.temp.text
                report.symptoms.append(
                    EvidenceItem(
                        text="Fever",
                        evidence=ev,
                        confidence="high",
                    )
                )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_consistency_checks(report: AnalysisReport) -> AnalysisReport:
    """Run all rule-based consistency checks on *report*.

    Findings are merged into ``potential_inconsistencies`` and
    ``missing_information``. Operates **in-place** and returns the same
    object for convenience.
    """
    if not has_clinical_content(report):
        logger.info("No clinical content detected — skipping clinical consistency checks.")
        return report

    _ensure_symptom_coverage(report)

    inconsistencies: list[EvidenceItem] = []
    missing: list[EvidenceItem] = []

    _check_allergy_medication_conflicts(report, inconsistencies)
    _check_implausible_vitals(report, inconsistencies)
    _check_duplicate_medications(report, inconsistencies)
    _check_diagnosis_without_symptoms(report, inconsistencies)
    _check_missing_key_fields(report, missing)

    report.potential_inconsistencies = _merge_findings(report.potential_inconsistencies, inconsistencies)
    report.missing_information = _merge_findings(report.missing_information, missing)

    if inconsistencies:
        logger.info("Consistency checks found %d issue(s).", len(inconsistencies))
    if missing:
        logger.info("Missing-field checks found %d gap(s).", len(missing))

    return report
