# AI/ML Design

## Models and Services

The configured model is `gemini-3.5-flash-lite`, read from `MODEL_NAME` and used through Google's `google-genai` SDK. The same Gemini model handles both vision transcription and structured clinical extraction. This keeps the multimodal path simple and lets the model see the original page image when a PDF has no usable text layer.

Supporting services are local Python components:

- `document_processor.py` uses PyMuPDF and Pillow for file validation, selectable-PDF extraction, page rendering, and image checks.
- `llm_client.py` provides an abstract `LLMClient` plus the Gemini client.
- `validators.py` uses rapidfuzz evidence matching.
- `consistency_rules.py` applies deterministic clinical checks.
- `analyzer.py` orchestrates and persists the result.

## Input Processing

### Plain text

The endpoint accepts a `text` multipart form field. The analyzer trims it and sends it as the source document to the structured extraction call.

### Standalone image

PNG, JPEG, and WebP files must pass extension, size, magic-byte, and Pillow validation. The image is sent to Gemini with a transcription prompt. The resulting text is then used for structured extraction, with the image also available to the extraction call.

### Text PDF

PyMuPDF opens the PDF and extracts text from up to `MAX_PDF_PAGES` pages. If the combined text is at least 50 characters, the extracted text is used directly. There is no system Poppler dependency and no `pdfplumber` dependency.

### Scanned PDF

If PyMuPDF extracts fewer than 50 characters, the processor labels the file as scanned, renders each allowed page to a PNG at 2x scale, and sends those images to Gemini vision. The quality note records: `PDF appears to be scanned; used vision model for text extraction.`

## Structured Extraction Prompt

The analyzer embeds `AnalysisReport.model_json_schema()` in the system prompt. The prompt requires Gemini to:

1. Extract only explicitly stated information.
2. Never guess or invent missing clinical information.
3. Use `null` or `not documented` for missing fields.
4. Return an exact evidence quote and `high`, `medium`, or `low` confidence for each extracted item.
5. Preserve low confidence for partially illegible or uncertain content.
6. Include medication name, dose, route, and frequency only when documented.
7. Record both fever as a symptom and the numeric temperature when applicable.
8. Put missing fields in `missing_information`.
9. Leave `report_summary` empty because the application generates it later.
10. Return empty clinical arrays and a no-clinical-content note for recipes and other non-medical documents.

The Pydantic schema contains evidence-bearing items for symptoms, diagnoses, medications, allergies, observations, vitals, missing information, concerns, and consistency findings.

## Validation and Retry

The first JSON response is parsed into `AnalysisReport` with Pydantic v2. If it fails schema validation, the analyzer makes one more `generate_json` call with the original prompt plus the exact `ValidationError`. If the second response also fails, the report is persisted as `failed` and the API returns a schema error response. LLM transport or SDK failures are handled similarly as LLM failures.

## Evidence Verification

After schema validation, `validate_evidence()` checks item evidence against the source text. It lowercases, normalizes whitespace and punctuation, first checks an exact substring, and then uses rapidfuzz `partial_ratio` with a threshold of 75. Empty evidence and intentional markers such as `not documented` are not treated as fabricated claims.

When evidence cannot be verified, the item's confidence becomes `low` and a separate `requires_review` item is added. This reduces the impact of generated quotes that are not present in the document, while allowing minor OCR or transcription variation.

## Independent Consistency Rules

The rule engine runs after evidence validation and does not ask Gemini to make the safety decision. It currently checks:

- Allergy/drug conflicts using a small built-in map for penicillin, sulfa, NSAIDs, cephalosporins, opioids, ACE inhibitors, and statins.
- Implausible HR, temperature, SpO2, respiratory rate, and blood-pressure values.
- Diagnoses without symptoms or clinical observations.
- Duplicate medication entries using normalized names, common aliases, and dose/route/frequency comparisons. The current-medication plus “at onset” plan phrase is treated as one regimen to avoid the observed Sumatriptan false positive.
- Missing patient age, allergy information, medication doses, allergy reaction details, symptom duration, respiratory rate, and SpO2.
- Fever symptom coverage when a temperature indicates fever.

Because these checks are deterministic and independent, they can catch issues that the LLM omits or incorrectly describes. Findings are merged into `potential_inconsistencies` and `missing_information` with `source="rule-check"`.

## Summary Generation

`_generate_summary()` runs after evidence validation and consistency rules. It does not make another LLM request. It reads the final report arrays and builds up to six lines in this order:

1. Critical inconsistency flags.
2. Patient and primary diagnosis.
3. Symptoms and vitals.
4. Medications.
5. The first missing-information items.
6. Review and inconsistency counts.

For a report with no meaningful clinical fields, it returns a dedicated `NO CLINICAL CONTENT` message. The analyzer then chooses the final status.

## Handling Missing and Uncertain Information

Missing values remain null or are represented by explicit missing-information items; the system does not infer age, dose, allergy severity, or other absent facts. Low-confidence model output can be retained for transparency, while failed evidence checks add review items. Image and scanned-PDF processing adds quality notes so the frontend can show the extraction path.

## Observed Sample Results

The seven synthetic documents in `samples/EVALUATION.md` were submitted to the live local `/api/analyze` endpoint:

- Clean text and searchable PDF completed successfully.
- The incomplete note completed while reporting missing fields.
- The inconsistent note completed with warnings for penicillin/amoxicillin, HR 300, temperature 20 C, unsupported acute cystitis, and duplicate Lisinopril.
- The scanned PNG and scanned PDF completed with no remaining consistency flags. The PDF explicitly used the vision fallback.
- The recipe returned `no_clinical_content` without fabricated clinical data.

The scanned samples still omitted photophobia/phonophobia details from the returned summary. The earlier Sumatriptan duplicate was a false positive and was fixed with the current medication/“at onset” heuristic. These results are evaluation observations, not a clinical accuracy guarantee.

## Known Failure Modes

- Vision transcription may omit or misread handwritten details.
- Fuzzy evidence matching can accept an unusual paraphrase or reject a valid OCR variation.
- The medication alias map and allergy conflict map are intentionally small.
- Duplicate heuristics can miss or over-suppress unusual medication phrasing.
- Synchronous external calls can be slow; scanned-PDF analysis may require multiple Gemini requests.
