# SakshamAI – Skill Intelligence Platform for Official Statistics

A responsive web application prototype for India's Official Statistical System. Built as an SIH demonstration prototype showcasing an AI-enabled learning platform for government officials.

## Demo Logins

The login page lists two fixed demo accounts, both sharing the password
`Demo@1234`:

| Role          | Email                        |
| ------------- | ---------------------------- |
| Learner       | `learner-1@sakshamai.demo`   |
| Administrator | `admin-1@sakshamai.demo`     |

These are the addresses seeded by `supabase/migrations/003_seed.sql`, and the
password matches `DEMO_USER_PASSWORD` in `.env.example`, so the same two
credentials keep working once a real backend is connected — at which point
Supabase Auth verifies them and the client-side table in
`src/services/appService.ts` (`DEMO_LOGINS`) stops being consulted.

Until then, the credentials are checked in the browser by that table, and only
when the backend is unreachable. That is a placeholder for a missing server,
not authentication:

- A backend that is running always wins. If it answers 401/403/422, that error
  is shown and nothing is bypassed, so these logins cannot be used to reach an
  account whose password you don't know.
- Nothing is persisted. Profile edits, enrolments, quiz scores and chat live in
  React state and are lost on refresh.
- The admin aggregates are not demonstrated. `/api/admin/overview` and
  `/api/admin/learners` are real queries against a real database, so offline
  they fall back to mock shapes. `/api/admin/forecast` and
  `/api/admin/charts` are hardcoded sample data regardless.

Set `DEMO_USER_PASSWORD` to something else if you expose a real deployment; the
shared demo password is published in this repository and in the public
`/api/auth/demo-users` endpoint.

## Quick Start

### 1. Supabase project

Create a project at [supabase.com](https://supabase.com). You need three
values from it (all in **Project Settings → API** / **Connect**):

| Variable | Where to find it |
|---|---|
| `DATABASE_URL` | Connect → Connection string (use the Session pooler) |
| `SUPABASE_URL` | Project Settings → API → Project URL |
| `SUPABASE_ANON_KEY` | Project Settings → API Keys → anon/publishable key |

You also need `SUPABASE_SERVICE_ROLE_KEY` for the one-off auth seeding step
below, and any `DEMO_USER_PASSWORD` you like for the demo accounts.

```bash
cp .env.example backend/.env     # then edit backend/.env
```

### 2. Backend (FastAPI + PostgreSQL)

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# Applies supabase/migrations/*.sql in order and seeds reference data.
# Safe to re-run; applied migrations are recorded in the seed_meta table.
.venv/bin/python -c "from database import init_db; init_db()"

# Creates the 11 demo Auth accounts and links them to the users table.
# Needs SUPABASE_SERVICE_ROLE_KEY. Also safe to re-run.
.venv/bin/python ../scripts/seed_auth_users.py

.venv/bin/python -m uvicorn main:app --port 8000 --reload
```

The API runs at **http://localhost:8000**. Docs at `http://localhost:8000/docs`.

Check it is really working — `/api/health` does a live database round trip and
returns **503** if the database is unreachable, instead of reporting a hardcoded
`ok`:

```bash
curl -s http://localhost:8000/api/health
```

> **LLM (optional):** the quiz generator, AI Virtual Assistant and the iGOT
> Karmayogi learning plan use the Groq API **only when `GROQ_API_KEY` is set**
> in `backend/.env`. Without it, every feature transparently falls back to the
> deterministic logic. The key is never exposed to the browser.

> The frontend falls back to in-memory mock services when the API is
> unreachable, so the UI still renders. It does **not** fall back for a 401 —
> an expired session asks you to sign in again rather than quietly serving
> fabricated data.

### 3. Frontend (React + Vite)

```bash
npm install        # first time only
npm run dev
```

Open **http://localhost:3000** in your browser.

## Demo Credentials

Sign-in is a real credential check against Supabase Auth. The login page lists
the seeded accounts; picking one fills in the email and the shared demo
password, and you still press **Sign In**.

| Account | Email | Role |
|---|---|---|
| Ananya Sharma | `learner-1@sakshamai.demo` | learner |
| Dr. Rajesh Kumar | `admin-1@sakshamai.demo` | admin |
| …9 more learners | `learner-2` … `learner-10@sakshamai.demo` | learner |

Password: whatever you set in `DEMO_USER_PASSWORD`. All demo accounts share it,
so it is not a secret — rotate it freely between demos.

### The demo password is public — by design

`Demo@1234` is a **string literal in client source**
(`src/services/appService.ts`, the `DEMO_LOGINS` table). It is compiled into the
shipped JavaScript bundle and is readable by anyone who opens the site. Moving
it to a `VITE_*` variable would not help: Vite inlines those into the same
bundle.

It exists for one narrow purpose — signing in when no backend is running, so the
UI can be explored before Supabase is wired up. It is **not authentication** and
grants nothing: a real backend is always consulted first, and only an
unreachable one falls back to it.

`/api/auth/demo-users` used to echo `DEMO_USER_PASSWORD` to any anonymous
caller whenever the variable was set — but that variable is set for *seeding*,
so "seeded" was quietly implying "safe to publish". It now requires a separate
`EXPOSE_DEMO_PASSWORD=true`, which defaults to off.

**Before any real deployment:** delete `DEMO_LOGINS`, set a real
`DEMO_USER_PASSWORD`, and remove the matching allowlist entry from
`.gitleaks.toml`.

## Secret Scanning

Three independent layers, and they are not redundant:

| Layer | Runs | Catches |
|---|---|---|
| `.githooks/pre-commit` | locally, on commit | a secret **before** it enters history |
| `.pre-commit-config.yaml` | locally, on commit | same, if you prefer pre-commit |
| `.github/workflows/secret-scan.yml` | on every push and PR | a secret that got committed anyway |

CI exists because both local layers are opt-in installs. Enable at least one:
```bash
# cheapest — needs only the gitleaks binary
git config core.hooksPath .githooks

# or the pre-commit framework
pipx install pre-commit && pre-commit install
```

`gitleaks` itself:

```bash
brew install gitleaks                                   # macOS
# https://github.com/gitleaks/gitleaks/releases         # any platform
```

The `.githooks` gate **fails closed**: if `gitleaks` is not on PATH the commit
is blocked, not waved through. A fresh clone is exactly where the binary is
least likely to be installed and a key most likely to get pasted, and a gate you
can walk through by uninstalling a tool is not a gate.

Scan by hand at any time:

```bash
gitleaks detect --config .gitleaks.toml --no-git            # working tree
gitleaks detect --config .gitleaks.toml --log-opts="--all"  # full history
```

The CI job uses the same `.gitleaks.toml` as the local hooks, so the rules and
the two exemptions below behave identically in all three places. It has
no `exclude_paths`: that would exempt a whole file regardless of what matched,
making CI strictly weaker than the hook it backs up.

### Why not the stock ruleset

`[extend] useDefault = true` was tried and abandoned: the bundled default ships
a global allowlist that silently suppressed newly added custom rules. The same
rule and regex matched when the config stood alone and stopped matching with
`useDefault` enabled. Measured against the defaults, gitleaks caught JWTs,
Stripe, Slack, SendGrid and GitHub tokens but **missed** the four shapes that
matter most here — postgres URIs with inline passwords, `sb_secret_` keys,
`gsk_` Groq keys, and AWS key ids. All thirteen patterns in the current config
are verified to fire.

### Allowlist

Exactly two exemptions, and nothing scans vendored dependencies
(`node_modules/`, `backend/.venv/`, `dist/`, `__pycache__/`) — without that,
pydantic's docstring examples and a PIL font bitmap produce 14 false positives.

| Exemption | Why | Remove when |
|---|---|---|
| `Demo@1234`, matched on value alone | known-public demo credential | you delete `DEMO_LOGINS` |
| `.env.example` | tracked placeholders (`PROJECT_REF`, `PASSWORD`) | never — it is a template |

The first is scoped to the **value**, not to a file, and that is deliberate.
gitleaks treats `paths` and `regexes` in a single allowlist entry as
alternatives rather than a conjunction, so the earlier `paths` + `regexes`
pairing exempted the whole of `src/services/appService.ts` — measured, not
assumed: pasting a different `password = …` literal into that file returned
`no leaks found`. That is the one file most likely to collect pasted
credentials, so it was a genuine blind spot. Matching on the value alone keeps
the guarantee that actually holds: the exact demo string is tolerated wherever
it appears, while any *other* credential literal in that file is still caught
by the `generic-credential-literal` rule. Both directions are tested.

## Secret Inventory

Every credential this application touches, and where each one actually lives.
No secret is a string literal anywhere in the tree — the only literal is
`Demo@1234`, which is public by design and listed as such.

| Secret | Env var | Read by | Exposed to browser? |
|---|---|---|---|
| Postgres connection string | `DATABASE_URL` | `backend/database.py` | no — server only, RLS owner |
| Supabase anon / publishable key | `SUPABASE_ANON_KEY` | `backend/auth_tokens.py` | **no** — server-side token verification only |
| Supabase service-role key | `SUPABASE_SERVICE_ROLE_KEY` | `scripts/seed_auth_users.py` | **no** — never referenced under `src/` |
| Supabase project URL | `SUPABASE_URL` | `backend/auth_tokens.py`, `routers/labs.py` | no |
| Demo account password | `DEMO_USER_PASSWORD` | `scripts/seed_auth_users.py`, `routers/auth.py` | only if `EXPOSE_DEMO_PASSWORD=true` (off) |
| LLM key (optional) | `GROQ_API_KEY` | `backend/llm.py` | no — feature falls back if unset |
| Backend origin | `VITE_API_URL` | `src/services/api.ts` | yes — and it is a URL, not a credential |

Two deliberate exclusions from "move it to an env var":

- **The anon key is not a browser value here.** It is only safe client-side
  *with RLS on every table*, and this app talks to Postgres directly, so the
  frontend never needs it. It is verified server-side and never shipped.
  RLS is on for all 18 public tables, so a leaked anon key would still be
  inert.
- **`Demo@1234` stays a literal.** Vite inlines `VITE_*` into the same bundle,
  so an env var would hide it from grep without removing it from view-source.
  See "Demo Credentials" above for how to delete it before deploying.

## Git History

**No secret has ever been committed to this repository.** All five commits on
`main` (`71e33f7`, `8248885`, `effa84a`, `2f99272`, `f97e3ef`) were scanned —
every blob in every revision — for JWTs, Stripe/Groq/OpenAI/AWS/GitHub/
Slack/SendGrid keys, `sb_` keys, connection strings with inline passwords, and
PEM private keys: zero hits outside the documented allowlist. No `.env` (the
gitignored file, as opposed to `.env.example` placeholders) has ever been added
to the index, and gitleaks reports `no leaks found` against
`--log-opts="--all"`.

So there is **nothing to rotate today.** `Demo@1234` is permanently in history
(it shipped with the platform code), but it is a demo credential with no real
value. That only changes if you later give it value — at which point rotate the
demo password and the Supabase service_role key, and rewrite history
(`git filter-repo`, then force-push and have everyone re-clone).

**If you ever add a real key, rotate it the moment it is committed.** A key that
reached a remote is compromised regardless of whether it is later deleted: forks,
clones, caches and the hosting provider's own logs may already hold it. Deleting
the line prevents the next reader from seeing it; it does not un-disclose it.


## Security Model

**The picker is a convenience, not the authentication.** Selecting an account
only fills in the form. The password is verified by Supabase, the access token
is checked on every subsequent request, and the caller's role is read from the
database row the token maps to — never from the request.

Why the guard lives in FastAPI and not in Postgres RLS
--------------------------------------------------------
`supabase/migrations/002_rls.sql` defines real per-user policies, but they are
written against `auth.uid()`, which only resolves when Supabase's PostgREST
layer injects JWT claims into the Postgres session. The backend talks to
Postgres directly with `psycopg`, so there is no such session variable and every
per-user policy would deny all rows. **RLS is currently a safety net for a
future PostgREST frontend, not the active boundary — FastAPI's
`require_self_or_admin` / `require_admin` dependencies are what actually
enforce access today.** Do not remove them believing the database has you
covered.

Public (no session) endpoints: `/api/health`, `/api/auth/login`,
`/api/auth/demo-users`, `/api/competencies`, `/api/roles`,
`/api/roles/{role}/requirements`, `/api/igot/courses`, `/api/labs`.
Everything else requires a valid token, and every endpoint that takes a
`user_id` additionally verifies it matches the caller unless the caller is an
admin.

### Sign-in throttling

`/api/auth/login` counts **failed** attempts only, on two axes — per client IP
(5 per email, 20 per IP by default, over a 15-minute sliding window) and per
email. Exceeding either returns `429` with `Retry-After`.

Three deliberate choices:

- A *correct* password never consumes budget, so someone signing in repeatedly
  is never locked out.
- Only genuine credential rejections (`401`/`403`) count. A `503` from an
  unreachable auth provider does **not** — otherwise a Supabase outage would
  lock every real user out of their own account for the full window. Verified:
  8 consecutive attempts during an outage produce 0 lockouts.
- The limiter **fails open** — if its own bookkeeping throws, the error is logged
  and the request continues to the real auth check. Verified: 5 wrong passwords
  then `429`; 40 correct logins unaffected; a deliberately broken lock still
  yields the true `401` rather than a `500` or a blanket lockout.

Scope, stated plainly: the counters are per process and in memory, so behind
multiple replicas the effective limit is per replica, and a restart clears
everything. It bounds guessing rate, not request volume. See
`backend/rate_limit.py`.

### Request limits

Quiz uploads are read in capped 1 MB chunks with a 20 MB ceiling
(`MAX_UPLOAD_BYTES`), so an oversized body is refused with `413` as it streams
in rather than after being buffered. Verified: a 500 MB upload is rejected after
21 MB is read, not after 500 MB is held in memory.

### TLS and deployment

**→ See [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) for the Vercel + Render +
Supabase walkthrough**, including the full environment-variable matrix, the
post-deploy verification commands, and why the frontend must be served
same-origin with the API rather than pointed at it cross-origin (the session
cookie is `SameSite=strict`, so a direct cross-origin Vercel→Render split
silently 401s every request). `vercel.json` and `render.yaml` encode the whole
setup.

**Do not put this on a public IP without terminating TLS.** The session token
travels as an `httpOnly` cookie, so page script cannot read it — but over plain
HTTP it is still visible to anything on the path, including shared or hostile
Wi-Fi. The cookie is marked `Secure` automatically whenever the request's `Host`
is not loopback, so a plain-HTTP deployment fails closed (every request 401s)
rather than quietly serving a cleartext session. Set `COOKIE_SECURE=true` to
force it on everywhere.

Code deliberately does not force HTTPS, because that would break local
development. Instead:

- Terminate TLS at a reverse proxy or load balancer, and redirect `:80` to
  `:443`. Set `ALLOWED_HOSTS` to your real domains; the app then rejects any
  request with a forged `Host` with `400`, blocking Host-header poisoning of
  redirects and cached URLs. Verified: a forged Host is refused, a real one
  passes, and leaving the variable unset keeps local development unaffected.
- Set `CORS_ORIGINS` to your real frontend origin instead of relying on the
  loopback defaults.
- Add HSTS at the proxy (`Strict-Transport-Security: max-age=31536000;
  includeSubDomains`), not in the app, so it applies to every path.
- Set `ALLOW_CODE_EXECUTION=false` (the default once `SUPABASE_URL` is set) and
  leave `/api/labs/run` off in production entirely.
- Replace the in-process rate limiter with Redis if you run more than one
  replica.
- Set `EXPOSE_DEMO_PASSWORD=false` and change or remove the seeded demo
  passwords before any real user data exists.

> **Resolved: `/api/labs/run` is remote code execution.** It was reachable
> without a session, and the subprocess limits are not a sandbox. The three
> escapes below were verified by execution, not inferred — `RLIMIT_CPU`,
> `RLIMIT_AS` and `RLIMIT_NOFILE` stop none of them.
>
> | Capability | Consequence |
> |---|---|
> | Reads any file the server can read | `backend/.env` — `DATABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` |
> | Inherits the server's environment | every secret in the process, no path guessing needed |
> | Unrestricted outbound TCP | exfiltrates the above to any host |
>
> So one anonymous `POST` was enough to take the server over. It now requires a
> signed-in user, and is refused outright whenever `SUPABASE_URL` is set —
> pointing the app at a real database is treated as the signal that it is no
> longer a laptop demo. See `ALLOW_CODE_EXECUTION` in `.env.example`.
>
> This reduces the blast radius; it does not make the sandbox safe. A signed-in
> user can still read the server's files. To run genuinely untrusted code, put
> the executor in its own container with no credentials, no network, and a
> read-only filesystem. Do not solve that by re-enabling the flag on a public
> deployment.

### Errors don't leak infrastructure

Three endpoints are reachable without a session, so none of them return a
driver or transport exception verbatim:

- **`/api/health`** — psycopg masks the password in its messages but still names
  the **host, port and username** (`aws-0-<region>.pooler.supabase.com`,
  `postgres.<ref>`). The public response now carries a fixed `detail` and only
  the exception *class name* in `error_type`; the full text goes to the log. The
  `hint` about paused free projects is kept — it is the most useful thing the
  endpoint says and contains nothing sensitive.
- **Supabase Auth failures** (`auth_tokens.py`) — httpx embeds the request URL,
  which contains the project ref. Those 503 bodies are now static messages and
  the detail is logged instead.
- **`/api/auth/demo-users`** — the shared password requires an explicit
  `EXPOSE_DEMO_PASSWORD=true`. See *Demo Credentials* above.

Verified by calling `healthcheck()` in-process against a deliberately leaky
DSN: the password, project ref, hostname and scheme are all absent from the
response.

## Supabase Project Pauses

Free Supabase projects are paused after a period of inactivity and reject
connections while they restart (up to ~24 hours). This is a platform limit, not
something the application can prevent — only a paid plan avoids it.

Before a demo, either confirm the project is active, or:

1. Open the Supabase dashboard — a paused project shows a **Restore project**
   button.
2. Wait for it to finish restoring.
3. `curl -s your-api/api/health` and confirm `"status": "ok"`.

`/api/health` reports a `503` with a `hint` when the database cannot be
reached, so a stale service can be diagnosed in one request instead of by
guessing why the dashboard is empty.

## Analytics Honesty

| Endpoint | Status |
|---|---|
| `GET /api/admin/overview` | **Real** — counts, average competency and total gaps are computed from the `learner_directory` view; learning hours are summed from the declared duration of actually-completed modules. |
| `GET /api/admin/learners` | **Real** — the learner directory view, derived from `users`, `competency_scores` and `course_enrollments`. |
| `GET /api/admin/forecast` | **Partly mock** — the regression maths is real, but the six-month `engagement` series it regresses over is hardcoded sample data. |
| `GET /api/admin/charts` | **Mock** — illustrative chart filler, not measurements. |

This replaces the previous state, where every `/api/admin/overview` figure was a
literal (including a hardcoded 1240 learning hours) and the counts came from an
`org_learners` table of fictional officials that shared no rows with the real
users table.

## Architecture Overview

```
saksham-ai/
├── supabase/
│   └── migrations/
│       ├── 001_schema.sql      # Tables, JSONB columns, learner_directory view
│       ├── 002_rls.sql         # Supabase RLS policies (see Security Model)
│       └── 003_seed.sql        # Generated by scripts/export_seed.py
├── scripts/
│   ├── export_seed.py          # Regenerate 003_seed.sql from database.py
│   ├── seed_auth_users.py      # Create + link Supabase Auth accounts
│   └── check_sql.py            # Static check: routers' SQL parses as PostgreSQL
├── backend/                    # FastAPI + PostgreSQL API
│   ├── main.py                 # App entry, CORS, routers, /api/health
│   ├── database.py             # psycopg pool, migration runner, healthcheck, seed constants
│   ├── auth_tokens.py          # Supabase Auth client + FastAPI access guards
│   ├── models.py               # Pydantic request/response models
│   ├── llm.py                  # Groq LLM client (env-driven, fail-safe)
│   ├── requirements.txt
│   └── routers/
│       ├── auth.py             # Demo-user list + real credential login
│       ├── users.py            # Profile + competencies CRUD
│       ├── competency.py       # Framework, roles, gap analysis
│       ├── courses.py          # Catalogue, enroll, modules, competency auto-update
│       ├── quiz.py             # Generate (LLM + real file parsing), submit, history
│       ├── assistant.py        # AI Virtual Assistant (LLM, Q&A, plans, mentors)
│       ├── igot.py             # Personalized iGOT Karmayogi learning plan
│       ├── labs.py             # Virtual Labs data + sandboxed Python runner
│       ├── assessment.py       # Competency test generation + scoring
│       └── admin.py            # Org-wide analytics + predictive forecast
└── src/                        # React frontend
    ├── types/index.ts          # TypeScript type definitions
    ├── data/mockData.ts        # Offline fallback data
    ├── services/
    │   ├── api.ts              # API client (httpOnly session cookie, offline fallback)
    │   └── appService.ts       # Local business logic (fallback)
    ├── store/AppContext.tsx    # React Context state
    ├── components/             # Layout & reusable UI
    └── pages/                  # Route components
```

## API Endpoints

Endpoints marked **auth** require a session. A browser gets one from the
`httpOnly` cookie that `POST /api/auth/login` sets; any other client may instead
send `Authorization: Bearer <token>` with the same token. Header-authenticated
requests are exempt from the CSRF origin check, since a page cannot attach that
header cross-origin.

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/auth/login` | Credential sign-in (`{"email", "password"}`) → `{token, user}` |
| GET | `/api/auth/demo-users` | Seeded demo accounts for the login picker |
| GET | `/api/auth/me` | **auth** Current caller's own profile |
| GET | `/api/competencies` | Competency framework |
| GET | `/api/roles` | Role list |
| GET | `/api/roles/{role}/requirements` | Required levels for a role |
| POST | `/api/assessment/gaps` | **auth** Skill-gap analysis + course recommendations |
| POST | `/api/assessment/generate` | **auth** Generate a role-based competency test |
| POST | `/api/assessment/submit` | **auth** Grade a test and persist the attempt |
| GET | `/api/courses?user_id=` | Course catalogue; per-user progress needs **auth** |
| GET | `/api/courses/{course_id}` | Course detail incl. modules + completion status |
| POST | `/api/courses/enroll` | **auth** Enroll in a course |
| POST | `/api/courses/module-complete` | **auth** Mark module done → auto competency bump (+1, max 5) |
| GET | `/api/igot/courses` | Mock iGOT Karmayogi API response |
| POST | `/api/igot/plan` | **auth** Personalized iGOT Karmayogi learning plan |
| POST | `/api/quiz/generate` | **auth** MCQ generation from text — LLM when key configured, else mock |
| POST | `/api/quiz/generate/file` | **auth** Real text extraction from PDF/DOCX/PPTX/TXT/SRT/VTT + LLM MCQs |
| POST | `/api/quiz/submit` | **auth** Score and store a quiz attempt |
| GET | `/api/quiz/history/{user_id}` | **auth** Quiz history (own, or any as admin) |
| POST | `/api/assistant/chat` | **auth** AI Virtual Assistant — also records the turn |
| GET | `/api/assistant/history` | **auth** Persisted transcript (survives refresh) |
| DELETE | `/api/assistant/history` | **auth** Clear own transcript |
| GET | `/api/labs` | Interactive Virtual Labs data |
| POST | `/api/labs/run` | Sandboxed CPython execution — **see Security Model, do not expose publicly** |
| GET | `/api/admin/overview` | **auth, admin** Real org statistics |
| GET | `/api/admin/learners` | **auth, admin** Learner directory |
| GET | `/api/admin/charts` | **auth, admin** Chart data — **mock** |
| GET | `/api/admin/forecast` | **auth, admin** Predictive forecast — **partly mock** |
| GET | `/api/health` | Liveness + live database check (503 when down) |

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
- **Backend**: FastAPI (Python 3), Uvicorn, psycopg 3 connection pooling, Supabase Auth
- **Database**: Supabase PostgreSQL — schema and seed applied as ordered migrations in `supabase/migrations/`, tracked in the `seed_meta` table

## Graceful Fallback (backend offline)

If the FastAPI backend is not running, the frontend transparently falls back to
in-memory mock data and functions, so the UI can still be demoed standalone.
This fallback triggers **only** on a genuine network failure. A 401/403 is
surfaced to the user and, for an expired session, signs them out — an auth
failure must never masquerade as a working offline demo with invented numbers.

When the backend is running, data persists to PostgreSQL (profile edits,
enrollments, module completions, competency scores, quiz attempts and
assessment history all survive a refresh, and are shared across browsers).

## LLM Configuration & Security

| Env var (in `backend/.env`) | Default | Purpose |
|-----------------------------|---------|---------|
| `GROQ_API_KEY` | *(empty → mock)* | Enables LLM features (quiz, assistant, iGOT plan) |
| `GROQ_MODEL` | `openai/gpt-oss-120b` | Chat model (free-tier keys: `qwen/qwen3.8-27b`, `groq/compound`) |
| `GROQ_TEMPERATURE` | `0.4` | Sampling temperature |
| `GROQ_TIMEOUT` | `60` | Request timeout in seconds |
| `ADVISOR_SHARE_PROFILE` | `false` | Whether the assistant sends the officer's department/education/experience/career goal to the provider (their name is never sent either way) |
| `SAKSHAMAI_LOG_DEBUG` | `false` | Local-only: write raw exception text to logs. Off by default because driver text can embed user values |

- The key lives **only** in `backend/.env` (gitignored) and is never sent to the browser — all LLM calls happen server-side.
- Every LLM call has a short timeout and falls back to deterministic logic on any failure/rate limit.
- AI output (quizzes, plans, assistant answers) is flagged for review by an authorized trainer before official use.
- The assistant prompt carries the minimum needed to advise: target role, competency levels, skill gaps, progress and the chat itself. It does not carry the officer's name, email, employee id, department, education or career goal unless `ADVISOR_SHARE_PROFILE` is set. See [docs/PRIVACY.md](docs/PRIVACY.md).
- If a key is shared, rotate it in the Groq console and update `.env`.

## Personal Data & Privacy

Full field-by-field map — what is collected, where it travels, what is stored, and what leaves the machine — is in **[docs/PRIVACY.md](docs/PRIVACY.md)**. Summary of the current state:

- **Never collected:** phone number, date of birth, address, payment card data, ID documents, device fingerprint, location.
- **No user PII in the browser.** The session token is an `httpOnly` cookie that script cannot read, and it is never returned in a response body. Nothing at all is written to `localStorage` or `sessionStorage`. No `console.*` anywhere in `src/`. See [docs/PRIVACY.md](docs/PRIVACY.md) §5.
- **No password is ever stored, hashed, or logged by this app.** Passwords go straight to Supabase Auth over TLS, which hashes them with bcrypt. There is no password column in any table.
- **No PII in logs.** Driver and transport exception text is suppressed in favour of the exception class plus SQLSTATE — a psycopg unique violation on `users.email` embeds the email in its message, so it is not logged verbatim.
- **Third-party egress is one path:** the AI assistant chat. Minimised as described above. Quiz generation sends only material the user supplied; the iGOT plan and assessment generation send no personal data at all.
- **Response filtering is an allowlist.** `users.email`, `users.auth_id` and `users.status` are never returned by any endpoint; `USER_PROFILE_COLUMNS` in `backend/routers/users.py` names the only columns that may be read for a response.
- **Right to erasure:** `DELETE /api/users/me` from *Settings → Delete my data*. It returns a per-table receipt of what was removed, invalidates the session, and deletes the Supabase Auth identity. The last remaining administrator cannot be deleted this way.

```bash
# 57 assertions covering response filtering, log redaction, LLM minimisation,
# the erasure flow, and the ownership checks on every person-scoped endpoint.
# Destructive: drops and recreates the schema. Use a throwaway instance.
DATABASE_URL=postgresql://... backend/.venv/bin/python scripts/check_privacy.py
```

## Future Integration Placeholders

Implemented already, and previously listed here as future work:

- ~~Role-based access control~~ — learner/admin guards on every user-scoped
  endpoint, roles resolved server-side (see [Security Model](#security-model))
- ~~Audit logs~~ — `score_update_log` records every competency level change with
  its source (`assessment` vs `course`) and a reference to what caused it

Still outstanding:

- Government SSO (Aadhaar/e-HRMS) — see `Settings` page
- iGOT Karmayogi live API (mock endpoint at `/api/igot/courses` today; the LLM plan already uses real `course_code`s from the catalogue)
- DPDP Act compliance
- Encrypted data exchange
- Full multilingual coverage for all 10 scheduled languages (EN/HI toggle today)
- A real sandbox for `/api/labs/run` (container isolation, or an external
  execution service)

## Verifying the Migration

### A note on `get_db_connection()`

`get_db_connection()` must return `pool.getconn()`, **not** `pool.connection()`.
`connection()` is a `@contextmanager` generator, so calling it yields a
`_GeneratorContextManager` — an object with no `execute`, `commit` or `close`.
Every router does `conn = get_db_connection()` then `conn.execute(...)` in a
`try/finally`, so the whole API would raise `AttributeError` before reaching
Postgres. `getconn()` checks out a real `PoolConnection` whose `.close()` returns
it to the pool, which is what those `try/finally` blocks assume.

This was a live bug, not a theoretical one. It is the first thing to check if
every endpoint 500s once a database is connected.

### Checks

```bash
# Every .sql migration and the generated seed parse with the real PostgreSQL parser
backend/.venv/bin/pip install pglast
backend/.venv/bin/python -c "from pglast import parse_sql; from pathlib import Path; \
  [parse_sql(f.read_text()) for f in sorted(Path('supabase/migrations').glob('*.sql'))]; print('SQL OK')"

# Seed column names/arity match the schema, and all router SQL is valid
# PostgreSQL with %s placeholders matching argument counts
backend/.venv/bin/python scripts/check_sql.py

# Frontend
npx tsc --noEmit && npm run build && npm run lint
```

`scripts/check_sql.py` is the one worth running after any query edit. It parses
every `conn.execute(...)` literal with `pglast` and compares the `%s` count to
the number of arguments, which catches the two mistakes that a `.py` syntax
check misses and that otherwise only surface against a live database.

## License

SIH 2025 Demonstration Prototype