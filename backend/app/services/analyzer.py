"""
Analyzer — orchestrates the full analysis pipeline.

Pipeline:
  1. Process document (extract text / transcribe images).
  2. Send extracted text to the LLM with a strict extraction prompt.
  3. Validate the LLM JSON against the Pydantic schema (retry once on failure).
  4. Run the hallucination-guard evidence check.
  5. Run rule-based consistency checks.
  6. Generate the report summary.
  7. Determine final status.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.models.report import Report
from app.schemas.analysis import AnalysisReport
from app.services.consistency_rules import run_consistency_checks
from app.services.document_processor import ProcessedDocument, process_document
from app.services.llm_client import LLMClient, LLMError
from app.services.validators import validate_evidence

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# System prompt for clinical extraction
# ---------------------------------------------------------------------------

_ANALYSIS_SCHEMA_JSON = json.dumps(AnalysisReport.model_json_schema(), indent=2)

SYSTEM_PROMPT = f"""\
You are a clinical document analyser.  Extract structured medical information
from the provided clinical document text.

═══ STRICT RULES ═══
1. Extract ONLY information that is EXPLICITLY stated in the document.
2. NEVER invent, assume, guess, or hallucinate any clinical information.
3. For any missing information use null or "not documented" — do NOT fabricate.
4. For EVERY extracted item include:
   • "text"       — a clear, concise description of the item.
   • "evidence"   — the EXACT quote from the source document supporting it.
   • "confidence" — "high" (clearly stated), "medium" (somewhat ambiguous),
                     or "low" (unclear / partially illegible / inferred).
5. If parts of the input are marked [illegible], note them in
   document_quality.notes and set confidence to "low" for derived items.
6. For medications, fill name / dose / route / frequency when available;
   use null for any component NOT explicitly stated.
7. For vitals, include the value text (e.g. "120/80 mmHg", "72 bpm", "38.8 C").
8. Symptoms vs Vitals: If fever/chills is mentioned (e.g. "fever 38.8 C"), extract "Fever" in symptoms AND the numerical temperature in vitals.temp. Both must be documented.
9. List anything missing from the document in missing_information.
10. Leave report_summary as an empty string — it will be generated separately.
11. Non-clinical documents: If the provided text is NOT a clinical or medical document (e.g. a cooking recipe, food preparation instructions, news article, shopping list, or general text), do NOT invent or extract any patient information, diagnoses, symptoms, vitals, medications, or allergies. Return all clinical lists as empty [], set patient_information fields to null, set document_quality.notes to "No clinical content detected (non-medical document / recipe).", and leave missing_information and potential_inconsistencies empty.

═══ OUTPUT ═══
Return a single JSON object conforming to this schema:

{_ANALYSIS_SCHEMA_JSON}
"""

USER_PROMPT_TEMPLATE = """\
Analyse the following clinical document and return structured JSON.

--- DOCUMENT START ---
{text}
--- DOCUMENT END ---
"""


# ---------------------------------------------------------------------------
# Summary generation (post-validation, post-consistency-checks)
# ---------------------------------------------------------------------------

def _generate_summary(report: AnalysisReport) -> str:
    """Build a concise 4-6 line clinical summary ordered by clinical priority:
    (a) critical flags first (allergy/medication conflicts, implausible vitals),
    (b) patient and primary concern/diagnosis,
    (c) key symptoms and vitals,
    (d) key medications,
    (e) the most important missing information,
    (f) a line saying how many items need review.
    """
    from app.services.consistency_rules import has_clinical_content

    if not has_clinical_content(report):
        return (
            "NO CLINICAL CONTENT: The provided document does not contain clinical or medical information "
            "(e.g., non-medical text or recipe). No patient data, diagnoses, symptoms, vitals, or medications were identified."
        )

    lines: list[str] = []

    # (a) Critical flags first
    if report.potential_inconsistencies:
        crit_details = [item.text.replace("Potential allergy conflict: ", "").rstrip(".") for item in report.potential_inconsistencies[:2]]
        lines.append(f"CRITICAL FLAGS: {'; '.join(crit_details)}.")
    else:
        lines.append("CRITICAL FLAGS: None identified.")

    # (b) Patient and primary concern/diagnosis
    pi = report.patient_information
    age_str: str | None = None
    if pi.age:
        digits = re.search(r"\d+", pi.age)
        if digits:
            age_str = f"age {digits.group()}"
        else:
            age_str = f"age {pi.age.replace('age', '').strip()}"
    id_bits = [b for b in [pi.name, age_str, pi.sex] if b]
    patient_str = f"Patient: {', '.join(id_bits)}" if id_bits else "Patient: Not specified"
    if report.diagnoses:
        dx_names = [d.text.rstrip(".") for d in report.diagnoses[:2]]
        lines.append(f"{patient_str} | Primary Concern/Diagnosis: {', '.join(dx_names)}.")
    else:
        lines.append(f"{patient_str} | Primary Concern/Diagnosis: Not documented.")

    # (c) Key symptoms and vitals
    sym_str = ", ".join([s.text.rstrip(".") for s in report.symptoms[:3]]) if report.symptoms else "None documented"
    vitals_bits: list[str] = []
    if report.vitals:
        for label, field in [("HR", "hr"), ("BP", "bp"), ("Temp", "temp"), ("SpO2", "spo2"), ("RR", "rr")]:
            v = getattr(report.vitals, field, None)
            if v and v.text:
                vitals_bits.append(f"{label} {v.text.rstrip('.')}")
    vitals_str = ", ".join(vitals_bits) if vitals_bits else "No vitals recorded"
    lines.append(f"Symptoms & Vitals: {sym_str} | {vitals_str}.")

    # (d) Key medications
    if report.medications:
        med_names = [(m.text or m.name or "").rstrip(".") for m in report.medications[:3]]
        lines.append(f"Medications: {', '.join(med_names)}.")
    else:
        lines.append("Medications: None documented.")

    # (e) The most important missing information (top 3 and +N more if >3)
    if report.missing_information:
        missing_texts = [m.text.rstrip(".") for m in report.missing_information[:3]]
        extra_count = len(report.missing_information) - 3
        extra_str = f" (+{extra_count} more)" if extra_count > 0 else ""
        lines.append(f"Missing Information: {'; '.join(missing_texts)}{extra_str}.")
    else:
        lines.append("Missing Information: None flagged.")

    # (f) Items needing review
    review_count = len(report.requires_review)
    inconsistency_count = len(report.potential_inconsistencies)
    lines.append(f"Review Required: {review_count} item(s) require clinical review ({inconsistency_count} inconsistency flagged).")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Status determination
# ---------------------------------------------------------------------------

def _determine_status(report: AnalysisReport) -> str:
    """Return the appropriate status string."""
    from app.services.consistency_rules import has_clinical_content

    if not has_clinical_content(report):
        return "no_clinical_content"
    if report.requires_review or report.potential_inconsistencies:
        return "completed_with_warnings"
    return "completed"


# ---------------------------------------------------------------------------
# LLM call with one retry
# ---------------------------------------------------------------------------

def _call_llm_with_retry(
    llm_client: LLMClient,
    text: str,
    images: list[bytes] | None = None,
    image_mime_types: list[str] | None = None,
) -> AnalysisReport:
    """Call the LLM, validate against Pydantic, retry once on failure."""
    user_prompt = USER_PROMPT_TEMPLATE.format(text=text)

    # First attempt
    raw: dict[str, Any] = llm_client.generate_json(
        prompt=user_prompt,
        system_prompt=SYSTEM_PROMPT,
        images=images,
        image_mime_types=image_mime_types,
    )

    try:
        return AnalysisReport.model_validate(raw)
    except ValidationError as first_err:
        first_err_msg = str(first_err)
        logger.warning("LLM output failed schema validation — retrying. Errors: %s", first_err_msg)

    # Second attempt — append the validation error so the model can fix it
    retry_prompt = (
        f"{user_prompt}\n\n"
        f"YOUR PREVIOUS RESPONSE FAILED VALIDATION:\n{first_err_msg}\n\n"
        "Please fix the errors and return valid JSON."
    )

    raw = llm_client.generate_json(
        prompt=retry_prompt,
        system_prompt=SYSTEM_PROMPT,
        images=images,
        image_mime_types=image_mime_types,
    )

    # If it still fails, let the ValidationError propagate
    return AnalysisReport.model_validate(raw)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_analysis(
    *,
    text: str | None,
    file_bytes: bytes | None,
    filename: str | None,
    db: Session,
    llm_client: LLMClient,
) -> Report:
    """Execute the full analysis pipeline and persist the result.

    Returns the saved ``Report`` ORM object.
    """
    # Determine input type for the DB row
    input_type = "text"
    if filename:
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext == "pdf":
            input_type = "pdf"
        elif ext in ("png", "jpg", "jpeg", "webp"):
            input_type = "image"

    # 1. Create a "processing" row
    report_row = Report(
        status="processing",
        input_type=input_type,
        original_filename=filename,
    )
    db.add(report_row)
    db.commit()
    db.refresh(report_row)

    try:
        # 2. Document processing
        doc: ProcessedDocument = process_document(
            text=text,
            file_bytes=file_bytes,
            filename=filename,
            llm_client=llm_client,
        )
        report_row.extracted_text = doc.text

        # 3. LLM analysis (with one retry on schema mismatch)
        analysis: AnalysisReport = _call_llm_with_retry(
            llm_client=llm_client,
            text=doc.text,
            images=doc.images,
            image_mime_types=doc.image_mime_types,
        )

        # Propagate document quality notes from processor
        if doc.quality_notes:
            existing = analysis.document_quality.notes or ""
            extra = "; ".join(doc.quality_notes)
            analysis.document_quality.notes = f"{existing}; {extra}".strip("; ") if existing else extra

        # 4. Hallucination guard — evidence validation
        validate_evidence(analysis, doc.text)

        # 5. Rule-based consistency checks
        run_consistency_checks(analysis)

        # 6. Generate summary
        analysis.report_summary = _generate_summary(analysis)

        # 7. Determine status & persist
        report_row.status = _determine_status(analysis)
        report_row.report_json = analysis.model_dump(mode="json")
        db.commit()
        db.refresh(report_row)

        logger.info("Analysis complete — report %s status=%s", report_row.id, report_row.status)
        return report_row

    except LLMError as exc:
        logger.error("LLM failure for report %s: %s", report_row.id, exc)
        report_row.status = "failed"
        report_row.error_message = f"LLM error: {exc}"
        db.commit()
        db.refresh(report_row)
        raise

    except ValidationError as exc:
        logger.error("Schema validation failed after retry for report %s: %s", report_row.id, exc)
        report_row.status = "failed"
        report_row.error_message = f"LLM output did not match expected schema after retry: {exc}"
        db.commit()
        db.refresh(report_row)
        raise

    except Exception as exc:
        logger.error("Pipeline failure for report %s: %s", report_row.id, exc, exc_info=True)
        report_row.status = "failed"
        report_row.error_message = str(exc)
        db.commit()
        db.refresh(report_row)
        raise
