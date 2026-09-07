# SakshamAI – Skill Intelligence Platform for Official Statistics

A responsive web application prototype for India's Official Statistical System. Built as an SIH demonstration prototype showcasing an AI-enabled learning platform for government officials.

## Quick Start

### Backend (FastAPI + SQLite) — optional but recommended

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env      # set GROQ_API_KEY to enable the LLM features
python -m uvicorn main:app --port 8000 --reload
```

The API runs at **http://localhost:8000**. Docs at `http://localhost:8000/docs`.

> **LLM (optional):** the quiz generator, AI Virtual Assistant and the iGOT
> Karmayogi learning plan use the Groq API **only when `GROQ_API_KEY` is set**
> in `backend/.env`. Without it, every feature transparently falls back to the
> deterministic logic. The key is never exposed to the browser.

> The frontend works even without the backend — it falls back to in-memory mock
> services automatically (state resets on refresh in that mode).

### Frontend (React + Vite)

```bash
npm install        # first time only
npm run dev
```

Open **http://localhost:3000** in your browser.

## Demo Credentials

| Role | Login Method |
|------|-------------|
| **Learner** | Click "Login as Learner" on the login page |
| **Administrator** | Click "Login as Administrator" on the login page |

Preloaded learner: **Ananya Sharma** (Statistical Investigator, NSSO, career goal: Senior Statistical Officer)

## Architecture Overview

```
saksham-ai/
├── backend/                    # FastAPI + SQLite API
│   ├── main.py                 # App entry, CORS, router registration
│   ├── database.py             # SQLite schema + seed data
│   ├── models.py               # Pydantic request/response models
│   ├── llm.py                  # Groq LLM client (env-driven, fail-safe)
│   ├── .env.example            # Sample env vars (GROQ_API_KEY, model)
│   ├── requirements.txt
│   └── routers/
│       ├── auth.py             # Simulated login
│       ├── users.py            # Profile + competencies CRUD
│       ├── competency.py       # Framework, roles, gap analysis
│       ├── courses.py          # Catalogue, enroll, modules, competency auto-update
│       ├── quiz.py             # Generate (LLM + real file parsing), submit, history
│       ├── assistant.py        # AI Virtual Assistant (LLM, Q&A, plans, mentors)
│       ├── igot.py             # Personalized iGOT Karmayogi learning plan
│       ├── labs.py             # Virtual Labs data + sandboxed Python runner
│       └── admin.py            # Org-wide analytics + predictive forecast
└── src/                        # React frontend
    ├── types/index.ts          # TypeScript type definitions
    ├── data/mockData.ts        # Offline fallback data
    ├── services/
    │   ├── api.ts              # Backend API client (graceful fallback)
    │   └── appService.ts       # Local business logic (fallback)
    ├── store/AppContext.tsx    # React Context state
    ├── components/             # Layout & reusable UI
    └── pages/                  # Route components
```

## API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/auth/login` | Simulated login (`{"role": "learner" \| "admin"}`) |
| GET | `/api/competencies` | Competency framework |
| GET | `/api/roles` | Role list |
| GET | `/api/roles/{role}/requirements` | Required levels for a role |
| POST | `/api/assessment/gaps` | Skill-gap analysis + course recommendations |
| GET | `/api/courses?user_id=` | Course catalogue with enrollment status |
| GET | `/api/courses/{course_id}` | Course detail incl. modules + module completion status |
| POST | `/api/courses/enroll` | Enroll in a course |
| POST | `/api/courses/module-complete` | Mark module done → auto competency bump (+1, max 5) |
| GET | `/api/igot/courses` | Mock iGOT Karmayogi API response |
| POST | `/api/igot/plan` | Personalized iGOT Karmayogi learning plan (`{user_id, weeks, language}`) |
| POST | `/api/quiz/generate` | MCQ generation from text — LLM when key configured, else mock |
| POST | `/api/quiz/generate/file` | Real text extraction from PDF/DOCX/PPTX/TXT/SRT/VTT + LLM MCQs |
| POST | `/api/quiz/submit` | Score and store a quiz attempt |
| GET | `/api/quiz/history/{user_id}` | Quiz history |
| POST | `/api/assistant/chat` | AI Virtual Assistant (LLM when key set, gaps, plans, interview, stats, mentors) |
| GET | `/api/labs` | Interactive Virtual Labs data |
| POST | `/api/labs/run` | Sandboxed CPython execution (`{"code": "..."}`) — real compile + runtime errors, 5s timeout, CPU/memory limits |
| GET | `/api/admin/overview` | Org-level statistics |
| GET | `/api/admin/learners` | Learner directory |
| GET | `/api/admin/charts` | Chart data (gaps, depts, trends) |
| GET | `/api/admin/forecast` | Predictive forecast (linear regression) |

## Core Features

### 1. Learner Profile & Competency Assessment
- Editable profile (name, employee ID, designation, department, role, education, experience, career goal)
- Self-assessment across **32 competencies in 4 categories** (Statistical ×10, Technical ×11, Digital Governance ×5, Behavioural ×6)
- 1–5 scale: Beginner → Basic → Intermediate → Advanced → Expert

### 2. Automated Skill-Gap Analysis
- `Skill Gap = Required − Current` (floored at 0)
- Priorities: High (3+), Medium (2), Low (1), No Gap (0)
- 9 target roles (Statistical Investigator, Data Analyst, Senior Statistical Officer, Economic Statistician, Price Statistics Officer, Labour Statistics Officer, Agricultural Statistics Officer, District Statistical Officer, IT & Systems Officer)
- Category-level radar (current vs required), bar chart, color-coded gap table, top-3 gaps

### 3. Personalized Course Recommendations
- Mock iGOT Karmayogi + NSSTA catalogue (**17 courses** with official course codes, e.g. `iGOT-MOD-301`, `NSSTA-TPAC-202`)
- Each course has a structured **module list**; completing a course auto-bumps the linked competencies (+1 level, max 5)
- Module micro-assessments recorded on the learner transcript
- Recommendations explain the gap behind each pick; filters, enrollment, progress bars
- 3-stage learning pathway: Foundation → Role-Specific → Advanced

### 4. AI-Powered Quiz Generator (Real Data Inputs)
- Paste text or upload PDF/DOCX/PPTX/TXT/SRT/VTT — **real file parsing** (pdfplumber / python-docx / python-pptx)
- Subtitle transcripts (SRT/VTT) are parsed with timestamps removed automatically
- Count (5/10/15) and difficulty (Easy/Medium/Hard)
- **LLM-generated MCQs** (grounded in the extracted content, marked `generatedBy: llm:…`) with automatic fallback to the deterministic generator when no API key / offline
- Review → edit → delete → regenerate → start → submit → instant score → review explanations

### 5. Virtual Labs (Interactive)
- **Python Sandbox** — real CPython execution via `POST /api/labs/run`: genuine `SyntaxError` reporting (line + caret), runtime tracebacks (`NameError`, `TypeError`, …), CPU/memory-limited subprocess and a 5s timeout — errors are displayed in-red, not swallowed
- **SQL Lab** — a real mini query engine over a district census dataset (SELECT/WHERE/ORDER BY/GROUP BY aggregates) with error messages for invalid queries
- **Data Visualization Builder** — live bar chart from your own labels/values; mismatched/empty input shows a validation error
- **AI/ML Playground** — linear regression with slope/intercept/R²/predictions (the math behind forecasting); insufficient or mismatched data points show an error
- **GIS Sandbox** — thematic (choropleth-style) mapping of district literacy
- **CodeRunner component** — the same runner UI also appears inline inside coding course modules (Python & SQL), so every course surfaces compile/runtime errors too

### 6. AI Virtual Assistant
- Floating chat widget on every page
- **LLM-powered** when `GROQ_API_KEY` is set — answers with live profile + skill-gap context and real course codes; replies in Hindi when you write in Hindi; chat messages carry an `AI`/`KB` badge
- Rule-based fallback: skill gaps, course recommendations, study plans, interview prep, statistics concepts (CPI/WPI, national accounts, sampling, SDGs) and finding mentors/leads
- EN/HI language toggle in the header (UI + assistant responses)

### 6b. iGOT Karmayogi AI Learning Plan
- On the Learning Path page, **Generate AI Plan** builds a week-by-week career plan (2/4/8 weeks) from your real skill gaps, mapped to the actual iGOT Karmayogi / NSSTA course catalogue (`course_code`s only)
- Focus-area badges, weekly courses with deep links into `/courses/:id` (module flow), practice/assessment/outcome, and a suggested certification path
- Tagged `AI` vs `Rule-based`; deterministic fallback when the LLM is unavailable

### 7. Predictive Analytics (Admin)
- Linear-regression extrapolation of learner engagement → 3-quarter forecast
- Workforce readiness trend (completions → competency levels)
- Model insights panel

### 8. Learner Dashboard
- Profile completion, overall competency score, courses in progress, learning hours, quiz average, streak
- Category radar, recent activity, enrolled-course progress
- Simulated skill-improvement notifications

### 9. Administrator Dashboard
- Org metrics (officials, active learners, completion rate, hours, gaps)
- Pie/bar/line charts, top-5 missing skills
- Searchable and filterable learner directory

### 10. Multilingual (EN/HI)
- Header toggle switches navigation and assistant messaging between English and हिन्दी
- `preferredLanguage` stored on the learner profile

## Tech Stack

- **Frontend**: React 19 + TypeScript, Tailwind CSS v4, Recharts, React Router, Lucide icons, Vite
- **Backend**: FastAPI (Python 3), Uvicorn, SQLite
- **Database**: SQLite (`backend/sakshamai.db`, auto-created & seeded on first run)

## Graceful Fallback (backend offline)

If the FastAPI backend is not running, the frontend transparently falls back to
in-memory mock data and functions. This means you can demo the UI standalone.
When the backend is running, data persists to SQLite (profile edits, enrollments,
quiz scores survive refresh).

## LLM Configuration & Security

| Env var (in `backend/.env`) | Default | Purpose |
|-----------------------------|---------|---------|
| `GROQ_API_KEY` | *(empty → mock)* | Enables LLM features (quiz, assistant, iGOT plan) |
| `GROQ_MODEL` | `openai/gpt-oss-120b` | Chat model (free-tier keys: `qwen/qwen3.8-27b`, `groq/compound`) |
| `GROQ_TEMPERATURE` | `0.4` | Sampling temperature |
| `GROQ_TIMEOUT` | `60` | Request timeout in seconds |

- The key lives **only** in `backend/.env` (gitignored) and is never sent to the browser — all LLM calls happen server-side.
- Every LLM call has a short timeout and falls back to deterministic logic on any failure/rate limit.
- AI output (quizzes, plans, assistant answers) is flagged for review by an authorized trainer before official use.
- If a key is shared, rotate it in the Groq console and update `.env`.

## Future Integration Placeholders

- Government SSO (Aadhaar/e-HRMS) — see `Settings` page
- iGOT Karmayogi live API (mock endpoint at `/api/igot/courses` today; the LLM plan already uses real `course_code`s from the catalogue)
- DPDP Act compliance
- Encrypted data exchange
- Audit logs
- Role-based access control
- Full multilingual coverage for all 10 scheduled languages (EN/HI toggle today)

## License

SIH 2025 Demonstration Prototype