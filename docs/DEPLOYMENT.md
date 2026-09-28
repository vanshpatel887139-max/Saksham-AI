# Deploying SakshamAI — Vercel + Render + Supabase

Three services, one repository, no shared filesystem:

```
GitHub
  ├── Vercel   → static React build (the SPA)
  │                └── rewrites /api/* to Render, server-side
  ├── Render   → FastAPI web service (the API)
  └── Supabase → managed PostgreSQL
```

Two config files encode this: `vercel.json` and `render.yaml`.

---

## The one decision that shapes everything: same-origin

The obvious wiring — point the frontend's `VITE_API_URL` straight at
`https://sakshamai-api.onrender.com` — **does not work with this app**, and fails
in a way that looks like a backend bug.

The session is a cookie with `SameSite=strict` (`backend/auth_tokens.py:88`).
`SameSite` is evaluated per *site* — a registrable domain — not per origin.
`my-app.vercel.app` and `sakshamai-api.onrender.com` are different sites, so the
browser silently withholds the cookie on every request. Each one comes back 401,
`api.ts` raises `UNAUTHORIZED_EVENT`, and the app bounces back to the login
screen. The password was correct. The backend was healthy. Nothing logs an error.

`src/services/api.ts` already warns about exactly this for the dev case.

So instead, `vercel.json` rewrites `/api/*` to Render **on the server side**:

```json
{ "source": "/api/(.*)", "destination": "https://sakshamai-api.onrender.com/api/:path*" }
```

The browser only ever sees one origin. Consequences, all of them good:

| | Direct cross-origin | Rewrite (what we do) |
|---|---|---|
| Session cookie | dropped, everything 401s | works, host-only on the Vercel domain |
| CORS | needs `Access-Control` on every response | not needed at all |
| CSRF guard | needs the Vercel origin allow-listed | still needs it, see below |
| CSP `connect-src` | must name Render | `'self'` |

The cookie is set without a `Domain` attribute, so the browser stores it
host-only against whichever origin served the response — the Vercel domain. That
is what makes `SameSite=strict` hold.

**`CORS_ORIGINS` is still required.** It looks redundant in a same-origin setup,
but the CSRF origin guard in `main.py:31` compares the browser's `Origin` header
against that list on every state-changing cookie-authenticated request. Set it to
your Vercel URL. `deploy_config.py` refuses to boot in production without it, and
refuses a `*` outright, because a wildcard cannot be combined with credentials.

### Rewrite order matters

`vercel.json` lists `/api/(.*)` **before** the SPA fallback. Vercel takes the
first matching rewrite, and `/api/*` also matches `/(.*)`. Reversed, every API
call would return `index.html` with HTTP 200 — the same misleading
"server works, nothing loads" symptom.

Vercel checks the static filesystem before applying rewrites, so
`/branding/logo.png` and the hashed `/assets/*` are still served directly, and
the SPA catch-all never shadows a real file.

---

## 1. Supabase

Already done in this repository — there is no SQLite step left. `backend/database.py`
speaks `psycopg` to `DATABASE_URL`, and the schema, RLS and seed live in
`supabase/migrations/*.sql`. `backend/sakshamai.db` is a leftover from the SQLite
era; it is gitignored and cannot reach a deployment.

Two things to do in the Supabase dashboard:

1. **Copy the session-pooler connection string** — Project → Connect →
   Connection string → **Session pooler**, port `5432`.

   Use the session pooler, not the transaction pooler (`6543`) and not the direct
   connection. Render is a long-lived server and `psycopg_pool` already pools
   connections itself; transaction mode is for serverless functions that need
   sharing across thousands of invocations, and it breaks the session-state
   checks in `_PooledConnection`. The direct port also has a low connection
   ceiling that a redeploy can exhaust.

   Append `?sslmode=require`. `deploy_config.py` reads `sslmode` out of the DSN
   and **refuses to boot in production** without it.

2. **Copy the three keys** — Project Settings → API Keys: `SUPABASE_URL`,
   `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`.

   The service-role key bypasses RLS and is required in production: without it,
   account deletion leaves the orphaned Auth identity behind. It stays on Render
   only. `deploy_config.py` fails the deploy if the anon and service-role slots
   hold the same value, since that is one copy-paste away.

> **Free projects pause.** After roughly a week of inactivity Supabase refuses
> connections for up to ~24 hours while it restarts. `/api/health` reports this
> explicitly (`hint` names the Restore button) instead of surfacing a bare driver
> error. Expect it before a demo — open the dashboard, hit Restore, retry.

---

## 2. Render

Render reads `render.yaml` from the repository root, so **New → Blueprint** and
point it at this repo. Fill in the prompted values, deploy.

Set on the service:

| Variable | Value |
|---|---|
| `DATABASE_URL` | Supabase **session pooler** string, with `?sslmode=require` |
| `SUPABASE_URL` | `https://<ref>.supabase.co` |
| `SUPABASE_ANON_KEY` | anon/publishable key |
| `SUPABASE_SERVICE_ROLE_KEY` | service-role key |
| `CORS_ORIGINS` | `https://<your-app>.vercel.app` |
| `ALLOWED_HOSTS` | `sakshamai-api.onrender.com` |
| `GROQ_API_KEY` | optional; without it the AI features use deterministic fallbacks |

`SAKSHAMAI_ENV=production`, `WEB_CONCURRENCY=1` and the rest are already set in
the blueprint.

Three things in `render.yaml` are deliberate and worth not "fixing":

- **`rootDir` is unset.** `database.py:36` resolves migrations as
  `BACKEND_DIR.parent / "supabase" / "migrations"`, and `init_db()` runs in the
  FastAPI lifespan. Pointing Render's root directory at `backend/` puts that path
  outside the service and the app refuses to start. The commands run from the
  repository root and `cd` into `backend/` instead — same as local dev.

- **No `--workers`.** `rate_limit.py` and the sign-in throttles keep counters in
  a per-process dict, so a second worker silently doubles the effective limit.
  `WEB_CONCURRENCY=1` pins that, and `deploy_config.py` raises a check if it is
  ever changed. Scaling out means moving the counters to Redis first.

- **Health check is `/api/health`, and it touches the database.** It returns 503
  when Postgres is unreachable, so Render will not route traffic to an instance
  that cannot serve a request. The trade-off is real but correct: a paused
  Supabase project fails the health check rather than serving 500s to users.

Cold starts on the free tier are 30–50s after inactivity. For a live demo, either
use a paid instance for the window or `curl` the health endpoint a minute before
you present.

### If you get 400s from TrustedHostMiddleware

`ALLOWED_HOSTS` filtering is on whenever that variable is set. Whether Vercel
forwards the original `Host` (`<app>.vercel.app`) or the destination's
(`sakshamai-api.onrender.com`) through a rewrite is a proxy detail this repo
cannot verify for you. List both — it costs nothing:

```
ALLOWED_HOSTS=sakshamai-api.onrender.com,<your-app>.vercel.app
```

---

## 3. Vercel

**Add New → Project**, import this repo. Vercel auto-detects Vite; `vercel.json`
pins the framework, build command and output directory anyway.

**No environment variables are required on Vercel.** The rewrite makes the API
same-origin, and `src/services/api.ts` defaults a *production* build to relative
requests, so the bundle issues `/api/...` against the page's own origin.

> That default is the important part, and it is a change to `src/services/api.ts`.
> `VITE_*` values are inlined at build time. With the older `||` fallback, a
> production build with the variable unset carried a literal
> `http://localhost:8000`, so a Vercel deploy with no env var set would aim every
> request at the visitor's own machine, fail as a network error, and serve mock
> data — a complete-looking demo backed by nothing, with nothing logged. Making
> "unset" mean same-origin in production removes that failure mode, rather than
> relying on someone remembering to set an empty string in a dashboard.
>
> `npm run dev` still defaults to `http://localhost:8000` and addresses the
> backend directly, unchanged. A local `npm run build && npm run preview` now
> exercises the same same-origin shape Vercel serves, via a `/api` proxy added to
> the `preview` block in `vite.config.ts` — without it, preview would hit its own
> `/api`, find nothing, and fall back to mocks, which is a false pass.

Deploy, then set `CORS_ORIGINS` on Render to the resulting URL and redeploy the
API.

### Preview deployments

Every branch gets its own Vercel URL, but a preview is a *different host*, so
`Origin: https://saksham-xyz.vercel.app` is not in `CORS_ORIGINS` and the CSRF
guard refuses every write — previews can load but cannot sign in. Add the preview
origin to `CORS_ORIGINS` while you need it, or use a Vercel preview to review
layout and leave interactive testing to the production URL.

---

## Environment variable matrix

| Variable | Lives on | In browser bundle? | Notes |
|---|---|---|---|
| `DATABASE_URL` | Render | no | session pooler, `sslmode=require` |
| `SUPABASE_SERVICE_ROLE_KEY` | Render | no | bypasses RLS; account deletion |
| `SUPABASE_ANON_KEY` | Render | no | frontend never calls Supabase directly |
| `SUPABASE_URL` | Render | no | |
| `CORS_ORIGINS` | Render | no | also drives the CSRF origin guard |
| `ALLOWED_HOSTS` | Render | no | Host-header filtering |
| `SAKSHAMAI_ENV` | Render | no | `production` makes validation fatal |
| `GROQ_API_KEY` | Render | no | optional, AI features only |
| `VITE_API_URL` | nowhere | n/a | leave unset; same-origin via rewrite |

**No secret is exposed to the browser.** The frontend makes no network call
outside `src/services/api.ts`, and it reaches only same-origin `/api/*`; Supabase
and Groq are called from the backend. CSP `connect-src` is `'self'`, which is the
enforced form of that claim. Verify in DevTools → Network after deploying.

---

## Verifying the deployment

```bash
# 1. Health, and a real database round trip. 200 only when Postgres answers.
curl -i https://sakshamai-api.onrender.com/api/health
#    {"status":"ok","service":"sakshamai-backend","database":"ok",...}
#    503 => Supabase is paused or DATABASE_URL is wrong. Read the "hint" field.

# 2. The SPA rewrite reaches the API through the frontend origin.
curl -i https://<your-app>.vercel.app/api/health
#    200 as above. 200 with HTML instead => the rewrite order is wrong.

# 3. History-API routing survives a hard refresh.
curl -o /dev/null -w '%{http_code}\n' https://<your-app>.vercel.app/dashboard
#    200 (served index.html), not 404

# 4. A restart does not lose data — the real test that Supabase is the
#    source of truth rather than a local file.
#    Trigger a redeploy, then sign in and confirm your data is still there.

# 5. No secrets in the bundle.
curl -s https://<your-app>.vercel.app/assets/*.js | grep -iE 'service_role|postgresql://|eyJ'
#    no matches
```

Then in a browser, as an anonymous visitor:

- sign in, and confirm a second browser or a private window shows the same data
- sign out, and confirm the session cookie is `HttpOnly`, `Secure`, `SameSite=Strict`
- open DevTools → Network and confirm every request is to your own origin, and
  that no response body contains a key or a connection string
- check `/api/labs/run` returns 503 — that route is remote code execution and is
  **refused whenever `SUPABASE_URL` is set**, so it must be off in production.
  Do not "fix" it with `ALLOW_CODE_EXECUTION`; that needs a separate isolated
  container with no credentials and no network.

### Where the frontend's CSP actually lives

`vercel.json`. Not the backend — `csp_for_frontend()` in
`backend/security_headers.py` is never called, because the FastAPI process mounts
no static files and has no document route to put a policy on. The
`CSP_FRONTEND` environment variable is therefore inert; tuning it changes
nothing. Three lists describe the same policy and are kept in step by hand:

| Where | For |
|---|---|
| `vercel.json` | the Vercel deployment |
| `deploy/nginx.conf.example` | a self-hosted nginx deployment |
| `CSP_DEV` in `vite.config.ts` | local dev, deliberately looser for HMR |

`connect-src` is `'self'` in all three production lists. That is not a
restriction to apologise for: the frontend makes no network call outside
`src/services/api.ts` and reaches only same-origin `/api/*`, while Supabase and
Groq are called from the backend. It is the enforced form of that claim — if a
future feature needs the browser to talk to a third party directly, it has to
earn its way into this list rather than discovering the policy by debugging a
blocked request.

Locally, the same gates run without a database:

```bash
npm run build && npm run lint
backend/.venv/bin/python scripts/check_deploy.py
```
