# AI / ML Design

## Model Selection

| Component | Default | Configurable via |
|-----------|---------|-----------------|
| Primary LLM | `gemini-2.0-flash` | `MODEL_NAME` env var |
| Vision transcription | same model | same |

Gemini Flash is chosen for its:
- Native multimodal support (text + images in one call)
- Fast inference latency suitable for interactive web use
- Strong instruction-following for structured JSON output
- Cost efficiency for high-volume document processing

## LLM Client Interface

```python
class LLMClient(ABC):
    @abstractmethod
    def generate(self, prompt: str, system_prompt: str | None, ...) -> str: ...
    @abstractmethod
    def generate_json(self, prompt: str, system_prompt: str | None, ...) -> dict: ...
```

The abstract interface means any provider can be swapped in without touching the pipeline — OpenAI, Anthropic, local Ollama, etc. The `get_llm_client()` FastAPI dependency returns the concrete implementation.

## Extraction Prompt Design

The system prompt uses explicit rule numbering and ALL-CAPS emphasis to ensure the model:

1. **Does not hallucinate** — "Extract ONLY information that is EXPLICITLY stated"
2. **Traces every claim** — every item must include `evidence` (the exact source quote)
3. **Grades uncertainty** — `confidence: high | medium | low`
4. **Handles missing data cleanly** — null or "not documented", never fabricated
5. **Separates symptoms from vitals** — fever is both a symptom ("Fever") AND a vital (temperature value)
6. **Defers summary** — `report_summary` is always set to `""` in the prompt; we generate it post-validation

The schema is embedded directly in the prompt (`AnalysisReport.model_json_schema()`), so the model always has the exact target structure.

## Retry Strategy

```
First attempt → Pydantic validation
   │
   ├─ OK → continue pipeline
   │
   └─ ValidationError
         │
         └─ Retry: append error message to prompt
               │
               ├─ OK → continue pipeline
               │
               └─ ValidationError → status=failed, 502 response
```

One retry is sufficient in practice: Gemini usually fixes schema violations when shown the exact error. A second retry would add latency without proportionally improving quality.

## Hallucination Guard

`validate_evidence()` uses **rapidFuzz partial token ratio** (threshold ≥ 65) to verify that every item's `evidence` quote appears in the source text.

Items that fail:
- `confidence` → `"low"`
- Added to `requires_review` with explanation

This catches cases where the model invents a quote that doesn't exist in the document, without rejecting cases where OCR introduced minor character differences.

The guard skips:
- Empty evidence strings
- `"not documented"` / `"N/A"` (intentional absence markers)

## Rule-Based Consistency Engine

The rule engine is entirely independent of the LLM. Rules run after the LLM output is accepted, so they catch things the model might miss or get wrong.

| Rule | Detection | Output |
|------|-----------|--------|
| Allergy–drug conflict | Cross-references allergy list against built-in penicillin/sulfa/NSAID/etc. maps | `potential_inconsistencies` |
| Implausible vitals | HR 20–220, temp 30–45°C, SpO₂ 0–100, RR 4–60, BP ranges | `potential_inconsistencies` |
| Duplicate medications | Normalised name deduplication | `potential_inconsistencies` |
| Diagnosis without symptoms | Flags diagnoses with no supporting symptoms or observations | `potential_inconsistencies` |
| Missing patient age | Always checked | `missing_information` |
| Missing allergy documentation | Always checked | `missing_information` |
| Missing medication dose | Per medication | `missing_information` |
| Missing allergy reaction type | Per allergy | `missing_information` |
| Missing symptom duration | If symptoms present | `missing_information` |
| Missing RR | Always checked | `missing_information` |
| Missing SpO₂ | Always checked | `missing_information` |
| Fever in vitals → Fever in symptoms | Ensures fever symptom recorded when temp ≥ 37.8°C | Adds to `symptoms` |

## Summary Generation

The summary is generated **after** all validation and rule checks, so every number and item it mentions is guaranteed to exist in the report arrays.

Priority order (clinical importance):
1. **Critical flags** — allergy conflicts, implausible vitals first
2. **Patient + diagnosis** — who and what
3. **Symptoms + vitals** — key clinical data
4. **Medications** — what was prescribed
5. **Missing information** — top 3 gaps, `(+N more)` if applicable
6. **Review count** — summary of items requiring attention

The summary is **4–6 lines**, designed to be readable at a glance before the full report.
