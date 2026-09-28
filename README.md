# AI Clinical Document Reviewer

> **All clinical data in this project is entirely synthetic and is not representative of any real patient.**

A full-stack web application that accepts clinical documentation (plain text, PDF, or image) and produces a structured AI-generated clinical report with hallucination guards and safety alerts.

---

## Features

- **Multi-modal input** — plain text, typed PDF, scanned PDF, handwritten images
- **Structured extraction** — diagnoses, symptoms, medications, allergies, vitals, observations
- **Evidence tracing** — every extracted item includes the exact quote from the source document
- **Hallucination guard** — fuzzy-matches evidence quotes; flags unverifiable claims
- **Safety rules** — detects allergy–drug conflicts, implausible vitals, duplicate medications
- **Priority summary** — 4–6 line clinical summary ordered by clinical importance (critical flags first)
- **Report history** — all analyses saved, viewable, and deletable

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 19 + Vite + TypeScript + Tailwind CSS v4 |
| Backend | Python 3.12 + FastAPI + Pydantic v2 + SQLAlchemy |
| Database | PostgreSQL (Neon) / SQLite for local dev |
| AI | Google Gemini Flash (`google-genai` SDK) |
| Deployment | Vercel (frontend) + Render (backend) |

---

## Quick Start (Local)

### Prerequisites
- Python ≥ 3.10
- Node.js ≥ 18
- A [Google Gemini API key](https://aistudio.google.com/app/apikey)

### 1. Backend

```bash
cd backend

# Create and activate virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env — set GEMINI_API_KEY (DATABASE_URL defaults to SQLite)

# Start the server
uvicorn app.main:app --reload
```

The API is now at `http://127.0.0.1:8000`. OpenAPI docs at `http://127.0.0.1:8000/docs`.

### 2. Frontend

```bash
cd frontend
npm install

# Copy env file (no changes needed for local dev — proxy handles /api routing)
cp .env.example .env

npm run dev
```

Frontend is now at `http://localhost:5173`.

### 3. Test with curl (PowerShell)

```powershell
# Text input
curl.exe -X POST http://127.0.0.1:8000/api/analyze -F "text=Patient Jane Smith, 52 yo female. Chief complaint: productive cough, fever 38.8 C, HR 98, BP 130/85. History of penicillin allergy. Prescribed Amoxicillin 500mg TID. Impression: Community-acquired pneumonia."

# File upload
curl.exe -X POST http://127.0.0.1:8000/api/analyze -F "file=@samples/sample_clinical_note.txt"

# List reports
curl.exe http://127.0.0.1:8000/api/reports

# Health check
curl.exe http://127.0.0.1:8000/api/health
```

---

## Running Tests

```bash
cd backend
python -m pytest tests/ -v
```

43 tests covering:
- Endpoint success/failure scenarios
- Mocked LLM output validation
- Evidence hallucination detection
- Consistency rules (allergy conflicts, implausible vitals, duplicates)
- Input validation (empty, bad type, corrupted files)
- Summary consistency with report arrays

---

## Project Structure

```
├── backend/
│   ├── app/
│   │   ├── api/routes/      # analyze.py, reports.py, health.py
│   │   ├── core/config.py   # pydantic-settings
│   │   ├── db/session.py    # SQLAlchemy engine + session
│   │   ├── models/report.py # ORM model
│   │   ├── schemas/         # Pydantic schemas (analysis.py, report.py)
│   │   ├── services/
│   │   │   ├── analyzer.py          # Pipeline orchestrator
│   │   │   ├── document_processor.py
│   │   │   ├── llm_client.py        # Abstract + Gemini implementation
│   │   │   ├── validators.py        # Evidence fuzzy-match guard
│   │   │   └── consistency_rules.py # Rule engine
│   │   └── main.py
│   ├── tests/
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── AnalyzeForm.tsx
│   │   │   ├── ReportView.tsx
│   │   │   ├── HistoryPage.tsx
│   │   │   └── Navbar.tsx
│   │   ├── api.ts
│   │   ├── types.ts
│   │   └── App.tsx
│   ├── index.html
│   └── vite.config.ts
├── docs/
│   ├── architecture.md
│   ├── ai_ml_design.md
│   └── technical_decisions.md
├── samples/
│   ├── sample_clinical_note.txt
│   └── sample_discharge_summary.txt
└── README.md
```

---

## Environment Variables

### Backend (`backend/.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///./dev.db` | DB connection string |
| `GEMINI_API_KEY` | — | Google AI Studio key |
| `MODEL_NAME` | `gemini-2.0-flash` | Gemini model ID |
| `CORS_ORIGINS` | `http://localhost:5173` | Allowed CORS origins (comma-separated) |
| `MAX_UPLOAD_MB` | `10` | Max file upload size |
| `MAX_PDF_PAGES` | `10` | Max pages per PDF |
| `LOG_LEVEL` | `info` | Python logging level |

### Frontend (`frontend/.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_API_URL` | `""` (uses dev proxy) | Backend root URL for production |

---

## Deployment

### Backend → Render

1. Create a new **Web Service** from the `backend/` directory
2. Build command: `pip install -r requirements.txt`
3. Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. Add environment variables: `DATABASE_URL`, `GEMINI_API_KEY`, `MODEL_NAME`, `CORS_ORIGINS`

### Frontend → Vercel

1. Import the `frontend/` directory
2. Framework preset: **Vite**
3. Add environment variable: `VITE_API_URL=https://your-render-app.onrender.com`

---

## Security Notes

- **Never commit `.env` files** — `.gitignore` excludes them
- Rotate credentials immediately if accidentally exposed
- All clinical data in `samples/` and tests is entirely synthetic
- The system is not intended for use with real patient data

---

## Documentation

- [`docs/architecture.md`](docs/architecture.md) — system design with Mermaid diagrams
- [`docs/ai_ml_design.md`](docs/ai_ml_design.md) — model selection, prompt design, retry strategy, hallucination guard
- [`docs/technical_decisions.md`](docs/technical_decisions.md) — key engineering decisions with rationale
