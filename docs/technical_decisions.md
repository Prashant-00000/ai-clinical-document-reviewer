# Technical Decisions

## Why FastAPI over Flask / Django?

- **Pydantic v2 integration** — schemas are the source of truth for both validation and JSON Schema generation (embedded in the LLM prompt)
- **Async-ready** — non-blocking I/O is important when LLM calls can take 5–15 s
- **Dependency injection** — `get_llm_client()` and `get_db()` make testing trivial (override with mocks)
- **Auto-generated OpenAPI docs** at `/docs`

## Why SQLite for local dev, PostgreSQL for production?

`DATABASE_URL` controls both. SQLite requires zero setup (`sqlite:///./dev.db`) and works out of the box on any machine. Neon PostgreSQL is used in production because:
- Serverless, zero cold-start penalty
- Connection pooling built in
- Free tier sufficient for assessment workloads

SQLAlchemy abstracts the difference — no code changes needed between environments.

## Why pdfplumber + PyMuPDF (not just one)?

| Tool | Strength | Weakness |
|------|----------|---------|
| pdfplumber | High-quality text from typed PDFs | Returns empty for scanned/image PDFs |
| PyMuPDF | Fast page-to-image conversion for any PDF | Not useful for text extraction of typed PDFs |

The processor tries pdfplumber first. If the extracted text is empty or very short (< 30 chars), it falls back to PyMuPDF's page rendering, then sends the images to the vision model for transcription. This handles typed, scanned, and mixed PDFs without separate code paths.

## Why rapidFuzz for evidence validation?

- **Speed** — written in C++, much faster than pure Python difflib
- **Partial token ratio** — handles cases where the model paraphrases slightly or OCR introduces minor errors
- **Threshold 65** — empirically chosen to allow legitimate minor variation while catching clearly fabricated quotes

## Why one retry (not zero, not three)?

- **Zero retries** — too brittle; Gemini occasionally returns valid JSON that doesn't match the schema on first attempt
- **One retry** — catches >95% of cases empirically; appending the validation error gives the model what it needs
- **Three+ retries** — excessive latency for the user (each retry adds 3–8 s)

## Why generate the summary last?

The first iteration generated the summary in the same LLM call. This caused inconsistencies: the model would write "2 inconsistencies" in the summary but the rule engine (which runs after the LLM) might add or remove items. Generating the summary last, strictly from `potential_inconsistencies`, `missing_information`, etc., guarantees every count and item is accurate.

## Why Tailwind CSS v4?

Vite 8 ships with the `@tailwindcss/vite` plugin which uses Tailwind v4's new CSS-first approach (`@import "tailwindcss"`). Since Tailwind v4 breaks `@apply` for custom classes, all custom component styles are plain CSS classes in `index.css`. This is intentional — it keeps the CSS bundle small and avoids runtime class resolution issues.

## Status lifecycle

```
processing → completed
           → completed_with_warnings  (requires_review or potential_inconsistencies non-empty)
           → failed                   (LLM error, schema error, doc processing error)
```

Failed reports are still persisted so the user can see what went wrong. The `error_message` field stores the human-readable cause.

## CORS configuration

Allowed origins are read from `CORS_ORIGINS` (comma-separated). Default is `http://localhost:5173` for local dev. In production, set this to the Vercel domain. The backend never hard-codes origins.

## Magic-byte file verification

Files are verified by reading the first bytes, not by file extension. This prevents users from renaming an arbitrary binary to `.pdf` and triggering an exploit in pdfplumber. The processor checks:
- PDF: `%PDF` at byte 0
- PNG: `\x89PNG\r\n\x1a\n`
- JPEG: `\xff\xd8\xff`
- WebP: `RIFF....WEBP`
