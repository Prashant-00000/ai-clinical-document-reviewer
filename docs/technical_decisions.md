# Technical Decisions

## React, Vite, and TypeScript

The frontend is a small React 19 application built with Vite 8 and TypeScript. Vite provides a quick development server and production build, while TypeScript keeps the frontend API shapes explicit. The current UI uses local page state for the analysis and history views rather than a router. `frontend/vercel.json` rewrites paths to `index.html` for SPA refresh behavior. Tailwind CSS v4 is installed through the Vite plugin, with additional component styles in `src/index.css`.

**Trade-off:** this is simpler than introducing a larger routing/state layer, but deep links and navigation state are intentionally limited to the current history/analyze workflow.

## FastAPI

FastAPI was chosen for Pydantic integration, generated OpenAPI documentation, clear multipart upload handling, and dependency overrides in tests. The API is logically split into analyze, reports, and health routes. It accepts one text field or one file per analysis request and processes the request synchronously.

**Trade-off:** the interface is straightforward to deploy, but long Gemini and vision calls occupy the request lifecycle and can be affected by Render cold starts or external service latency.

## SQLite Locally, PostgreSQL/Neon in Deployment

`DATABASE_URL` controls SQLAlchemy's database engine. SQLite is the default for local development because it needs no service or credentials. PostgreSQL is the production option, with Neon documented as the hosted provider choice. The same SQLAlchemy model and session code support both.

**Trade-offs:** SQLite is convenient for a single local process, while hosted PostgreSQL is better for concurrent deployment. This repository has no Alembic or other migration system; startup calls `Base.metadata.create_all()`, which is adequate for this small project but not a complete production schema lifecycle.

## Gemini and the Multimodal Approach

Gemini `gemini-3.5-flash-lite` is used through `google-genai` for both vision transcription and structured extraction. The model accepts text and image parts in the same abstraction, so the application can reuse one client and one analysis prompt for typed text, images, and rendered scanned-PDF pages.

**Trade-off:** using one multimodal service avoids a separate OCR stack and keeps the code small, but transcription quality, latency, availability, and cost depend on the external Gemini service. A dedicated OCR service could offer more predictable text extraction for handwriting, but would add another model, dependency, and integration boundary.

## Hybrid LLM and Rule Architecture

The LLM is useful for flexible extraction from varied documents, but it is not trusted to make every safety judgment. The pipeline combines:

1. Gemini structured extraction with evidence and confidence.
2. Pydantic schema validation.
3. Rapidfuzz evidence verification against source text.
4. Independent deterministic consistency rules.
5. Local summary generation from the final report.

**Trade-off:** an LLM-only design would require less code but would make vital, allergy, duplicate, and missing-field behavior harder to test consistently. The hybrid design is more explainable and testable, but its rule maps and thresholds are incomplete and can produce false positives or false negatives.

## Synchronous Processing Instead of a Job Queue

The current API creates a processing row, performs extraction and analysis in one request, saves the result, and returns it. This makes local use and the frontend workflow easy to understand.

**Trade-off:** users wait for every Gemini request, especially for scanned PDFs that require vision transcription followed by structured analysis. A queue and worker would improve resilience and user experience, but would require job state transitions, polling or WebSockets, worker deployment, and retry policy.

## Evidence and Confidence Instead of Silent Filtering

The system keeps extracted items visible, attaches the model's confidence, and lowers confidence plus adds `requires_review` when evidence cannot be matched. This preserves an audit trail for synthetic evaluation instead of silently discarding uncertain output.

**Trade-off:** rapidfuzz partial matching tolerates OCR and transcription variation, but a threshold of 75 is heuristic. It is not a formal grounding guarantee.

## File Safety and PDF Handling

Uploads are checked by extension, size, and magic bytes. PDFs are handled with PyMuPDF for both text extraction and page rendering, so the Render deployment does not depend on system Poppler. Pillow verifies image readability.

**Trade-off:** magic-byte checks catch mislabeled files but do not replace full content security scanning. The implementation also limits pages and upload size rather than providing a complete document security service.

## Known Weaknesses

- Duplicate medication detection uses heuristics and a small brand/generic alias map; unusual phrasing may be missed or over-suppressed.
- Allergy/drug conflict detection uses a limited built-in medication map, not a comprehensive drug database.
- Gemini vision can omit or misread handwritten details; the sample evaluation omitted photophobia/phonophobia from the scanned-note summary.
- Processing is synchronous and external calls can be slow.
- Render free-tier cold starts may increase latency.
- There is no authentication, authorization, audit log, or human review queue.
- The application has no PHI handling, retention, encryption, or compliance workflow; all repository samples are synthetic.
- Database schema creation is startup-based and there are no migrations.

## Improvements Next

The next practical improvements would be:

1. Move analysis to a background worker with durable job status and polling.
2. Add authentication, authorization, and a human review workflow.
3. Replace small rule maps with a maintained medication/allergy knowledge base.
4. Add migrations, operational metrics, and structured audit logging.
5. Evaluate against a larger, carefully labeled synthetic document set covering more layouts, handwriting, OCR noise, and medication phrasing.
6. Add stronger document security controls before considering any non-synthetic data.
