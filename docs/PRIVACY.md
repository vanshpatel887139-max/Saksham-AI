# Personal data map and handling policy

Every field of personal data this application handles, where it enters, where it
travels, and where it ends up. Written against the code as it stands; the
`scripts/check_privacy.py` suite asserts each guarantee claimed here, so a
failure in that suite means a statement in this document is no longer true.

## Summary

| | |
|---|---|
| Data categories held | name, employee id, job role, department, education, experience, career goal, prior training, preferred language, email, activity timestamps, assessment answers, quiz scores, advisor chat |
| Never collected | phone number, date of birth, home/work address, payment card data, government ID document, device fingerprint, precise location |
| Third parties receiving user data | 1 — the LLM provider (Groq), and only the advisor chat path |
| Browsers storing user PII | none |
| Cookies set by the app | none |
| Log lines containing user data | none — exception text and access-log ids are both scrubbed |
| Right to erasure | `DELETE /api/users/me` |

The two things that were genuinely wrong before this pass, both now fixed, are
the advisor prompt (it was sending the officer's name, department, education and
career goal to a US LLM vendor on every message) and the log statements (a
psycopg unique-violation message embeds the offending value, so
`users.email` could land in the log file verbatim). Details in
[What was fixed](#what-was-fixed).

---

## 1. Data collection points

The complete list of places a human or client supplies data about a person.
Anything not in this table is not collected.

| Endpoint | Collects | Notes |
|---|---|---|
| `POST /api/auth/login` | email, password | Password is forwarded to Supabase Auth over TLS and never stored, logged, or returned. See [§4](#4-password-handling). |
| `PUT /api/users/{id}` | name, employeeId, designation, department, currentRole, education, experience, careerGoal, previousTraining, preferredLanguage | The only endpoint that writes profile PII. Self or admin only. |
| `PUT /api/users/{id}/competencies` | self-rated competency levels | Self or admin only. |
| `POST /api/assessment/submit` | per-question answers, chosen options, self-ratings, test timestamp | `userId` in the body is validated against the session; a mismatch is rejected 403. |
| `POST /api/quiz/submit` | answers, scores | Self or admin only for history reads. |
| `POST /api/quiz/generate` | free-text study material | Sent to the LLM provider — see [§3](#3-third-party-egress). The user chooses what to paste. |
| `POST /api/quiz/generate/file` | an uploaded document | Capped at 20 MiB. Parsed server-side, excerpt sent to the LLM provider. |
| `POST /api/courses/enroll`, `POST /api/courses/module-complete` | course enrolment, module completion | Written against `identity.id`, never a body-supplied id. |
| `POST /api/assistant/chat` | the message, and the last 8 turns of history | Sent to the LLM provider and persisted to `advisor_messages`. |
| `POST /api/labs/run` | submitted source code | Executed server-side. See the sandbox caveat in the README. |
| `POST /api/igot/plan`, `POST /api/assessment/generate`, `POST /api/competency/assessment/gaps` | target role, requested counts, difficulty | No personal identifiers. |

### Data the platform derives about a person

Not collected from the user, but created about them and stored the same way:
competency levels, accuracy percentages, skill-gap counts, assessment
timestamps, module completion dates, notification rows, and activity-feed rows.

### Data collected incidentally, and deliberately not retained

- **IP address.** `request.client.host` is read in `POST /api/auth/login` and in
  `POST /api/labs/run`, used to rate-limit, held in an in-memory `deque` with a
  15-minute window, and never written to the database or to a log. It is not
  recoverable after the process restarts. Moving to Redis for multi-replica
  deployments will extend its life, so that store needs its own expiry — see the
  README caveats.
- **User agent / device.** Never read. There is no device fingerprinting.

---

## 2. Where data is stored

All of it is in one PostgreSQL database. There is no second store, no analytics
warehouse, and no file on disk containing user records.

| Table | Personal data held | On user delete |
|---|---|---|
| `users` | name, employee_id, designation, department, role, target_role, education, experience, career_goal, previous_training, preferred_language, profile_completed, **email**, **auth_id**, status | row deleted |
| `competency_scores` | levels, accuracy, self-rating, assessment timestamp | deleted |
| `assessment_questions` | every question, the chosen answer, the correct answer, timestamp | deleted |
| `quizzes` / `quiz_questions` | attempt scores, per-question answers | deleted (`quiz_questions` cascades) |
| `course_enrollments` | what is enrolled in, progress % | deleted |
| `module_progress` | which modules were completed, and when | deleted |
| `score_update_log` | every automated level change, with before/after | deleted |
| `notifications` | message text addressed to the person | deleted |
| `activities` | action-feed entries | deleted |
| `advisor_messages` | full advisor chat history, verbatim | deleted |

`competencies`, `role_requirements`, `courses` and `labs` are catalogue
reference data shared by everyone and contain no personal data.

### Fields deliberately not exposed over the API

`users.email`, `users.auth_id` and `users.status` are never returned by any
endpoint. This is enforced in two independent places so neither one alone is
load-bearing:

1. `USER_PROFILE_COLUMNS` in `backend/routers/users.py` names the only columns
   that may be read out of `users` for a response. `email`, `auth_id` and
   `status` are excluded, so a column added to the table in a future migration
   is not published until someone adds it to that list.
2. `user_to_dict()` is a hand-written allowlist that emits only the fields the
   UI actually reads.

Using `SELECT *` and filtering in Python would have meant any new column — a
phone number, a date of birth — would start appearing in API responses the
moment it was added to the schema.

---

## 3. Third-party egress

Four outbound integrations exist. Two carry no personal data at all.

| Integration | What is sent | Personal data |
|---|---|---|
| **Supabase Auth** `/auth/v1/token` | email, password | yes — this is the credential check, by necessity |
| **Supabase Auth** `/auth/v1/user` | the bearer token | yes — token verification |
| **Supabase Auth admin** `/auth/v1/admin/users/{id}` | `auth_id`, service-role key | only on account deletion |
| **Groq LLM** — advisor chat | designation, target role, full competency levels, skill gaps, course catalogue, enrolments, last 3 quiz results, the last 8 chat turns, the new message | **minimised, see below** |
| **Groq LLM** — study plan | target role, competency gaps, course catalogue, week count, language | none |
| **Groq LLM** — quiz generation | an excerpt of the material the user pasted or uploaded, plus difficulty | only what the user supplied |
| **Groq LLM** — assessment generation | competency ids, names, categories | none |

The service-role key is read from the environment on the server, used only to
delete an Auth identity, and is never returned, logged, or accepted from a
request. It is not present in the frontend bundle.

### What the advisor prompt deliberately withholds

`_llm_reply()` in `backend/routers/assistant.py` builds the advisor's system
prompt. It runs **without** the officer's:

- **name** — a direct identifier. The model used it only to choose a salutation,
  so the prompt now asks for address by designation instead, which is equally
  courteous and identifies nobody. The name is never sent, at any setting.
- **email, `auth_id`, `employee_id`** — login and internal identifiers, not
  needed to give career advice.
- **department, education, experience, career goal** — withheld by default.
  In a small office, department plus designation is often enough to single one
  person out, and none of it is needed to reason about competency gaps.

It still sends the target role, the competency levels, the gaps, the
enrolments and recent quiz scores, which is what actually produces the advice.

`ADVISOR_SHARE_PROFILE=1` re-enables department, education, experience and career
goal for deployments that have a data-processing agreement with the LLM
provider. It still does not send the name.

---

## 4. Password handling

**This application never stores, hashes, logs, or returns a password.** There is
no password column in any table and no password hashing code in the repository.

The flow, end to end:

1. `POST /api/auth/login` receives the password in `LoginRequest`.
2. `sign_in()` in `backend/auth_tokens.py` forwards it over TLS to Supabase's
   `/auth/v1/token` as the request body. It is never logged, never written, and
   never placed in an error message or response.
3. Supabase Auth verifies it and returns a session. Supabase stores it as a
   bcrypt hash. That hash never reaches this application's database and is
   never visible to it.
4. The API returns only the short-lived access token.

Therefore the "hash with bcrypt/argon2/scrypt, never MD5 or plain SHA-256"
requirement is met by delegation to a provider that uses bcrypt. The correct
alternative — adding local password storage — would be strictly worse: it would
create a second credential store for this application to protect.

The one MD5 in the repository is `slugify()` in `scripts/export_seed.py`, which
turns a course name into a deterministic primary key so re-running the export
dedupes correctly. It is an identifier, not a credential, and protects nothing.
It is commented as such.

Login is throttled on two axes — per client IP and per email — so the demo
password cannot be sprayed indefinitely. Only genuine credential rejections
count against the budget, so a provider outage cannot lock real users out.

---

## 5. Cookies and browser storage

**The session token is an `httpOnly` cookie and is never exposed to script.**
Login sets `sakshamai_session` with `HttpOnly`, `SameSite=Strict`, `Path=/`, and
`Max-Age` taken from the Supabase token's own `expires_in`, so the cookie never
outlives the credential inside it. The token is deliberately **not** returned in
the login response body — anything the body hands to script is readable by
injected script, which is the whole problem being solved.

The previous implementation kept the token in `sessionStorage`. That survives a
refresh, but `sessionStorage` is readable by any JavaScript on the page, so one
XSS anywhere in the bundle was enough to exfiltrate a live session. Nothing is
stored in any web store now; `setAccessToken`/`getAccessToken` are gone and
`api.ts` contains no `Authorization` header at all.

A cookie does create one risk that a bearer token does not: a cookie is an
*ambient credential*, so the browser attaches it to any request to this origin,
including one a third-party page triggered. That is CSRF, and it is answered
twice over:

- `SameSite=Strict` is the primary control — the browser withholds the cookie
  from cross-site requests entirely.
- `csrf_origin_guard` in `backend/main.py` refuses any state-changing request
  that carries the cookie without an `Origin` from the allow-list. Browsers
  always send `Origin` on such requests, so its absence means the call did not
  come from this app's own page.

The guard applies only to requests whose credential came from the *cookie*. A
caller setting an `Authorization` header is exempt, because a page cannot attach
that header cross-origin without CORS approval — so curl, the seed scripts and
any future non-browser client keep working with no special-casing.

**One deployment detail worth knowing.** `SameSite` compares *hostnames*, not
origins, and the port is irrelevant — but `localhost` and `127.0.0.1` are
different sites. Serving the app from one and the API from the other makes the
browser silently withhold the cookie, so every request 401s with no useful
error. Use the same hostname on both sides, or serve `/api` through the Vite
proxy so the app is same-origin. `api.ts` warns in a dev build if it detects
this mismatch.

**No other personal data is stored in the browser.** No profile, name, email,
competency or score is written to any web store, and zero `console.*` calls
exist anywhere in `src/`, so no data reaches the browser console or a crash
reporter.

`Secure` is set on the cookie everywhere except when the request's `Host` is
loopback. A `Secure` cookie is silently dropped over plain HTTP, so guessing
wrong in one direction logs every user out on the next request; loopback is not
a network exposure and is the one host knowingly served without TLS. Set
`COOKIE_SECURE` to override either way. This is *not* a licence to serve
anything else over plain HTTP — see the TLS note in the README.

**What this does not fix.** Supabase access tokens are stateless JWTs, so
`POST /api/auth/logout` clears the browser's cookie but cannot revoke the token,
which stays valid until it expires. Server-side revocation needs Supabase's
refresh-token endpoint and a session registry. The exposure window is therefore
one token lifetime (an hour by default), not forever, but it is not zero.

---

## 6. API response filtering

Every endpoint that returns person-scoped data enforces ownership server-side.

- `GET/PUT/DELETE /api/users/{id}` and `PUT /api/users/{id}/competencies` call
  `require_self_or_admin()`.
- `GET /api/quiz/history/{user_id}` calls `require_self_or_admin()`.
- `POST /api/courses/enroll` writes against `identity.id`; a mismatched body
  `user_id` is rejected rather than silently honoured.
- `POST /api/assistant/chat`, `POST /api/igot/plan` and `POST /api/labs/run`
  overwrite any client-supplied user id with `identity.id` before use, so the
  personal context they build can only ever be the caller's own.
- `POST /api/assessment/submit` rejects a body `userId` that is not the
  session's.
- The entire `/api/admin/*` router requires `require_admin` at the router level.

Responses never include a password hash (none exists), `auth_id`, or another
user's rows. The admin roster is served from the `learner_directory` view, which
is defined in SQL to expose only name, department, target role, aggregate
competency, gap count, completion count and status — no email, no employee id,
no education, no career goal.

---

## 7. Log hygiene

`backend/log_safety.py` centralises the policy. Driver and transport exception
text is not written to logs; the exception class and the SQLSTATE code are
instead:

```
database health query failed UniqueViolation sqlstate=23505
```

This was verified, not assumed. Against psycopg 3.2.3, a duplicate-email insert
raises an exception whose `str()` is:

```
duplicate key value violates unique constraint "t_email_key"
DETAIL:  Key (email)=(victim.worker@gov.example) already exists.
```

The offending value is in the message. `users.email` is `UNIQUE`, so any unique
violation on that column puts a real officer's email address into the log file.
httpx exception text similarly embeds the request URL, which contains the
Supabase project reference. Both are now suppressed.

`SAKSHAMAI_LOG_DEBUG=1` re-enables raw text for local development against
synthetic data, and even then `redact()` still strips anything email-, token-,
secret- or DSN-shaped. It must stay unset in any deployment handling real users.

Every other log statement was reviewed: migration filenames, pool state, and
host-allowlist counts. None can carry user data. The `print()` calls in
`database.py` that look like logging are inside a `PY_BASICS` string literal
containing sample tutorial code for the course catalogue.

One thing the application cannot control on its own: **uvicorn's access log
records the request target**, and three request targets embed a user id —

```
GET /api/users/learner-1
GET /api/quiz/history/learner-1
GET /api/courses?user_id=learner-1
```

A user id is a pseudonymous internal identifier rather than a name or email,
but it is a stable join key: a log shipper plus a timestamp is enough to
reconstruct who did what and when, which is exactly the kind of profile that
should not sit in log storage unasked. An access log is a legitimate security
and accountability control, so the fix is to remove the identifier rather than
the log line.

`backend/log_safety.py` installs a `RedactingFormatter` on the `uvicorn.access`
logger, which renders the line with the server's own formatter and then
replaces the id segment with `[redacted]`:

```
INFO:     127.0.0.1:54848 - "GET /api/users/[redacted] HTTP/1.1" 401 Unauthorized
INFO:     127.0.0.1:54850 - "GET /api/users/me HTTP/1.1" 401 Unauthorized
```

A hash is deliberately not used. These ids are `learner-1` … `learner-11`, so a
digest over a nine-character enumerable space is reversible in microseconds and
would be security theatre. `me` is preserved because it is a fixed literal, not
an identifier.

This is installed both at module import and at application startup, because
`uvicorn.access` is owned by the server and the ordering of its logging setup
versus the app import is version-dependent. It is idempotent, and the installed
formatter wraps rather than reconstructs the server's formatter: rebuilding one
from the original's format string drops uvicorn's custom percent-style, and the
resulting `KeyError` in the logging error handler emitted the *unredacted*
message to stderr instead.

Set `ACCESS_LOG_REDACT=false` to keep raw ids, which is occasionally wanted
when debugging one specific user.

Request *bodies* are never logged at any level, which is why no email or
password reaches the log from that direction.

---

## 8. Data deletion

`DELETE /api/users/me` — self-service right to erasure.
`DELETE /api/users/{id}` — the same operation, initiated by an administrator.

Both require `{"confirmation": "DELETE"}`, so a stray or replayed request cannot
destroy an account.

What happens:

1. Every row about the person is counted, per table, as a receipt.
2. All child rows are deleted explicitly — the tables are listed in
   `_USER_SCOPED_TABLES` and walked in order, rather than relying only on
   `ON DELETE CASCADE`, because an erasure guarantee should not depend on a
   foreign key definition staying correct in a future migration. A test asserts
   the list covers the live schema.
3. The `users` row is deleted, in the same transaction, so a partial failure
   rolls back rather than leaving a half-erased profile.
4. The `auth_id` → learner cache is invalidated, so a session issued moments
   earlier stops working immediately.
5. The Supabase Auth identity is deleted via the admin API, so the credential
   cannot be used to sign in again. Deleting only the application row would
   leave a live account behind.
6. A receipt is returned naming each table and the total rows removed. It
   contains no email and no other identifier.

Two deliberate choices:

- **No tombstone row is kept.** An anonymised shell is still personal data. The
  user asked for removal, so the record is removed.
- **The last administrator cannot be deleted** (409). Otherwise the
  organisation loses all admin access with no way back through the UI. The
  check applies to self-deletion too, since that is the likeliest way the last
  admin would disappear.

If the Auth deletion fails — for example the service-role key is not configured
— the application's own data is still fully erased and the response says so
explicitly via `authAccountRemoved: false`. The failure is never swallowed,
because a user who believes their account is gone when it is not is worse than
one who is told to finish the job in the Supabase dashboard.

---

## What was fixed

| # | Finding | Severity | Fix |
|---|---|---|---|
| 1 | Advisor prompt sent the officer's **name, department, education, experience and career goal** to Groq on every message | **High** — third-party transfer of identifiable employee data with no lawful basis configured | Payload reduced to role + competency data. Name never sent; background fields behind `ADVISOR_SHARE_PROFILE=1` |
| 2 | `logger.warning(..., exc)` wrote raw driver text, which **embeds the offending value** — a unique violation on `users.email` put a real email in the log | **High** — confirmed PII disclosure to log storage | `log_safety.safe_exception()`: class + SQLSTATE only, with regex redaction for email/JWT/DSN/secret patterns |
| 3 | **No way for a user to delete their data** | **High** — no right to erasure | `DELETE /api/users/me` with per-table receipt, cache invalidation, Auth account removal, last-admin guard |
| 4 | `SELECT *` into the user serializer fetched `email` and `auth_id` and relied on the serializer to drop them | Medium — one forgotten key leaks PII; a new column would leak silently | `USER_PROFILE_COLUMNS` allowlist + `fetch_user()`; serializer remains a second independent allowlist |
| 5 | httpx exceptions logged with the request URL, exposing the Supabase project ref | Low — infrastructure detail, not user PII | Same helper; class name only |
| 6 | `delete_auth_account` could have surfaced raw upstream error text to an API response | Low — would have leaked the project ref and key name | Returns short fixed strings; upstream status code only |
| 7 | **The session token sat in `sessionStorage`, readable by any script on the page — one XSS exfiltrated a live session** | High — a bearer token is a full account takeover for whoever reads it | Moved to an `httpOnly` `SameSite=Strict` cookie, token removed from the login body and from all client code; CSRF answered with `SameSite` plus an Origin guard |
| 8 | **uvicorn's access log recorded a user id in the request path** for `/api/users/{id}`, `/api/quiz/history/{id}` and `?user_id=` | Medium — a stable join key for who-did-what-when, in log storage | `RedactingFormatter` on `uvicorn.access`; ids become `[redacted]`. `ACCESS_LOG_REDACT=false` opts out |

Checked and found already correct, so left alone: the admin router is gated at
the router level; the `learner_directory` view is minimal by construction;
login throttling is two-axis and counts only real credential failures; no
console logging in the frontend; no PII in browser storage; no cookies; no
password storage anywhere; the iGOT plan, quiz generation and assessment
generation LLM calls already sent no personal data.

## Re-running the checks

```bash
DATABASE_URL=postgresql://... backend/.venv/bin/python scripts/check_privacy.py
```

Destructive — it drops and recreates the schema and deletes accounts. Point it
at a throwaway instance.
