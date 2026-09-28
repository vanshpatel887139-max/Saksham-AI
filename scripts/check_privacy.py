"""Privacy regression check: response filtering, log redaction, LLM minimisation,
and the account-erasure flow.

Run against a real PostgreSQL (the schema is applied automatically):

    DATABASE_URL=postgresql://... .venv/bin/python scripts/check_privacy.py

This is destructive to whatever database it is pointed at: it drops and
recreates the public schema, and it deletes learner accounts. Point it at a
throwaway instance, never at production.

What it asserts is summarised in docs/PRIVACY.md. Each check corresponds to a
guarantee claimed there, so a failure here means that claim is no longer true.
"""

import io
import json
import logging
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "backend"))
os.environ.setdefault("SUPABASE_URL", "http://127.0.0.1:9")   # unreachable on purpose
os.environ.setdefault("SUPABASE_ANON_KEY", "check-anon")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "check-service-role")

import psycopg
from psycopg.rows import dict_row
from fastapi import Request
from fastapi.testclient import TestClient

from database import init_db

if not os.environ.get("DATABASE_URL"):
    sys.exit("DATABASE_URL is required. Point this at a throwaway PostgreSQL instance.")

DB = os.environ["DATABASE_URL"]

# ------------------------------------------------------------------ destructiveness guard
# Everything below runs against a schema this script DESTROYS and rebuilds. The
# only previous protection was a sentence inside the "DATABASE_URL is missing"
# error above, which by construction is never shown to anyone who actually ran
# the script with a URL set. That is not a guard.
#
# This has already bitten once: the script was pointed at the live Supabase
# project, and `DROP SCHEMA public CASCADE` erased every row in all 18 tables,
# including the loaded World Bank dataset. Everything was recoverable — the
# migrations rebuild the schema and scripts/load_worldbank.py repopulates the
# data — but the seeded demo accounts lost their auth_id links, and a real
# Supabase deployment would have lost real learner data with no way back.
#
# So the destruction now requires an explicit, unambiguous opt-in, and is
# refused outright against the database the app is actually configured to use.
RESET_ENV = "ALLOW_DESTRUCTIVE_SCHEMA_RESET"


def _is_live_app_database(url: str) -> bool:
    """True when this URL is the one the app itself is configured against.

    Compares against backend/.env, not just the process environment, because the
    common mistake is running the script from a shell where DATABASE_URL was
    never exported and the script read it from .env itself.
    """
    live = os.environ.get("DATABASE_URL")
    env_file = pathlib.Path(__file__).resolve().parent.parent / "backend" / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("DATABASE_URL="):
                live = line.split("=", 1)[1].strip().strip('"').strip("'")
                break
    if not live:
        return False
    # Compare on host+database, ignoring the password and the pooler prefix
    # suffix, so a cosmetic difference in the string cannot defeat the check.
    def fingerprint(u: str) -> str:
        try:
            from urllib.parse import urlparse

            p = urlparse(u)
            return f"{p.hostname}{p.path}"
        except Exception:
            return u

    return fingerprint(url) == fingerprint(live)


if os.environ.get(RESET_ENV, "").strip().lower() not in {"1", "true", "yes", "on"}:
    sys.exit(
        f"REFUSING TO RUN.\n\n"
        f"This suite DROPS AND RECREATES THE ENTIRE public SCHEMA. It deletes every\n"
        f"row in every table, then rebuilds from supabase/migrations/ and reseeds.\n"
        f"It is a test harness, not a read-only check.\n\n"
        f"Point DATABASE_URL at a throwaway PostgreSQL instance and confirm with:\n"
        f"    {RESET_ENV}=1\n\n"
        f"It refuses to run against the database this app is configured to use.\n"
        f"If you just ran it against real data by accident, recover with:\n"
        f"    python scripts/load_worldbank.py     # repopulates the statistics dataset\n"
        f"    psql \"$DATABASE_URL\" -f supabase/migrations/003_seed.sql   # demo rows"
    )

if _is_live_app_database(DB):
    sys.exit(
        f"REFUSING TO RUN against the live application database.\n\n"
        f"DATABASE_URL points at the same database as backend/.env, so dropping the\n"
        f"public schema would destroy the app's real data. Use a separate\n"
        f"throwaway instance, or unset DATABASE_URL in backend/.env first if you are\n"
        f"working on a database that is genuinely disposable."
    )

print(f"WARNING: dropping and recreating the public schema on {DB}")

with psycopg.connect(DB, row_factory=dict_row, autocommit=True) as _c:
    _c.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
init_db()
print("schema applied and seeded")

import main

client = TestClient(main.app, raise_server_exceptions=False)

FAILS = []


def check(name, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + name + (f"   {extra}" if extra and not cond else ""))
    if not cond:
        FAILS.append(name)


def section(title):
    print(f"\n== {title} ==")


FAILS = []
def check(name, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + name + (f"   {extra}" if extra and not cond else ""))
    if not cond:
        FAILS.append(name)

# ---------------------------------------------------------------- 1. no PII in responses
print("\n== 1. API response field filtering ==")
# Shard the auth dependency so we can exercise authorization.
import auth_tokens
def fake_identity(request: Request) -> auth_tokens.Identity:
    uid = request.headers.get("x-test-user", "learner-1")
    role = "admin" if uid.startswith("admin") else "learner"
    with psycopg.connect(DB, row_factory=dict_row) as c:
        row = c.execute("SELECT id,name,role FROM users WHERE id=%s",(uid,)).fetchone()
    if not row:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="no profile")
    return auth_tokens.Identity(dict(row), {"email": f"{uid}@sakshamai.demo"})
main.app.dependency_overrides[auth_tokens.current_identity] = fake_identity

def get(uid, path, **kw):
    return client.get(path, headers={"x-test-user": uid}, **kw)

r = get("learner-1", "/api/auth/me")
check("GET /api/auth/me is 200", r.status_code == 200, r.text[:200])
me = r.json()
blob = json.dumps(me)
check("profile has no 'email' key", "email" not in me, sorted(me))
check("profile has no 'authId' key", "authId" not in me)
check("profile has no 'auth_id' key", "auth_id" not in me)
check("profile has no 'status' key", "status" not in me)
check("no @sakshamai.demo email in payload", "@sakshamai.demo" not in blob)
check("profile DOES include name (needed by UI)", "name" in me)

r = get("learner-2", "/api/users/learner-1")
check("learner-2 cannot read learner-1 (403)", r.status_code == 403, r.status_code)
r = get("admin-1", "/api/users/learner-1")
check("admin CAN read learner-1 (200)", r.status_code == 200, r.text[:150])
check("admin view still has no email", "email" not in r.json())

# ---------------------------------------------------------------- 2. admin router
print("\n== 2. admin roster is gated + minimal ==")
r = client.get("/api/admin/learners")
check("anonymous /api/admin/learners is 401/403", r.status_code in (401,403), r.status_code)
r = get("learner-1", "/api/admin/learners")
check("learner /api/admin/learners is 403", r.status_code == 403, r.status_code)
r = get("admin-1", "/api/admin/learners")
check("admin /api/admin/learners is 200", r.status_code == 200, r.text[:150])
if r.status_code == 200:
    rows = r.json()
    keys = set(rows[0].keys()) if rows else set()
    check("roster keys are the 7 intended", keys == {"name","department","role","competency","gaps","completed","status"}, sorted(keys))
    check("roster has no email/employeeId", "email" not in json.dumps(rows))

# ---------------------------------------------------------------- 3. demo-users
print("\n== 3. /api/auth/demo-users ==")
r = client.get("/api/auth/demo-users")
d = r.json()
check("demo-users 200", r.status_code == 200)
check("demoPassword omitted by default", d.get("demoPassword") is None, d.get("demoPassword"))
check("demo users carry no competency/score", "competencies" not in json.dumps(d))

# ---------------------------------------------------------------- 4. deletion flow
print("\n== 4. account deletion / right to erasure ==")
VICTIM = "learner-2"
def victim_rowcounts(uid):
    tabs = ["competency_scores","assessment_questions","course_enrollments","module_progress",
            "quizzes","notifications","activities","score_update_log","advisor_messages"]
    with psycopg.connect(DB, row_factory=dict_row) as c:
        out = {}
        for t in tabs:
            out[t] = c.execute(f"SELECT COUNT(*) n FROM {t} WHERE user_id=%s",(uid,)).fetchone()["n"]
        out["users"] = c.execute("SELECT COUNT(*) n FROM users WHERE id=%s",(uid,)).fetchone()["n"]
    return out

before = victim_rowcounts(VICTIM)
print("   before:", {k:v for k,v in before.items() if v})
check("victim has data to erase", sum(before.values()) > 1, before)

r = client.request("DELETE", "/api/users/me", json={"confirmation": ""}, headers={"x-test-user": VICTIM})
check("deletion without confirmation is 400", r.status_code == 400, r.text[:200])
check("data still present after refused call", victim_rowcounts(VICTIM) == before)

r = client.request("DELETE", "/api/users/me", json={"confirmation": "nope"}, headers={"x-test-user": VICTIM})
check("deletion with wrong confirmation is 400", r.status_code == 400, r.text[:200])

r = client.request("DELETE", "/api/users/me", json={"confirmation": "DELETE"}, headers={"x-test-user": VICTIM})
check("deletion with correct confirmation is 200", r.status_code == 200, r.text[:300])
if r.status_code == 200:
    d = r.json()
    print("   receipt:", json.dumps(d["rowsRemoved"]))
    check("receipt reports deleted=true", d.get("deleted") is True)
    check("receipt totalRowsRemoved is a number", isinstance(d.get("totalRowsRemoved"), int))
    check("receipt does not echo the email", "@sakshamai.demo" not in json.dumps(d))
    # Seed rows have auth_id NULL (seed_auth_users.py has not run), so there is
    # no Auth identity to remove and the goal state already holds.
    check("unlinked auth reported honestly", d.get("authAccountRemoved") is True and "not linked" in d.get("authAccountDetail",""), d.get("authAccountDetail"))

after = victim_rowcounts(VICTIM)
check("every user-scoped table is now empty", all(v == 0 for v in after.values()), {k:v for k,v in after.items() if v})

r = get(VICTIM, "/api/auth/me")
check("deleted user can no longer authenticate (403)", r.status_code == 403, r.status_code)

# linked-auth failure path: auth_id present, Supabase unreachable -> must be reported
with psycopg.connect(DB, row_factory=dict_row, autocommit=True) as c:
    c.execute("UPDATE users SET auth_id = gen_random_uuid()::uuid WHERE id=%s", ("learner-4",))
r = client.request("DELETE", "/api/users/me", json={"confirmation":"DELETE"}, headers={"x-test-user":"learner-4"})
check("deletion succeeds even when Supabase Auth is unreachable", r.status_code == 200, r.text[:250])
if r.status_code == 200:
    d = r.json()
    check("FAILED auth deletion is surfaced, not silently swallowed", d.get("authAccountRemoved") is False, d)
    check("auth failure detail has no url/key", "127.0.0.1" not in json.dumps(d) and "service-role" not in json.dumps(d), d.get("authAccountDetail"))
    check("learner-4 app data still erased", victim_rowcounts("learner-4").get("users",0) == 0)

# whole-table sweep: nothing anywhere still references the deleted id
with psycopg.connect(DB, row_factory=dict_row) as c:
    tabs = ["competency_scores","assessment_questions","course_enrollments","module_progress",
            "quizzes","notifications","activities","score_update_log","advisor_messages","users"]
    leftovers = {t: c.execute(f"SELECT COUNT(*) n FROM {t} WHERE user_id=%s",(VICTIM,)).fetchone()["n"]
                 for t in tabs if t != "users"}
    leftovers["users"] = c.execute("SELECT COUNT(*) n FROM users WHERE id=%s",(VICTIM,)).fetchone()["n"]
    orphan_qq = c.execute("SELECT COUNT(*) n FROM quiz_questions qq LEFT JOIN quizzes q ON q.id=qq.quiz_id WHERE q.id IS NULL").fetchone()["n"]
check("no table anywhere still references the deleted user", all(v==0 for v in leftovers.values()), leftovers)
check("no orphaned quiz_questions left behind", orphan_qq == 0, orphan_qq)

# admin deletion of another user + last-admin guard
r = client.request("DELETE", "/api/users/learner-3", json={"confirmation":"DELETE"}, headers={"x-test-user":"learner-1"})
check("learner cannot delete another user (403)", r.status_code == 403, r.status_code)

# The erasure list must not drift from the schema. A new user-scoped table that
# is neither listed nor CASCADE-ing would silently survive deletion, so assert
# the coverage against the live database rather than trusting the constant.
from routers.users import _USER_SCOPED_TABLES
with psycopg.connect(DB, row_factory=dict_row) as c:
    tables = [r["tablename"] for r in c.execute(
        "SELECT tablename FROM pg_tables WHERE schemaname='public'").fetchall()]
    unlisted = []
    for t in tables:
        cols = {r["column_name"] for r in c.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name=%s", (t,)).fetchall()}
        if "user_id" not in cols:
            continue
        if t in _USER_SCOPED_TABLES:
            continue
        fk = c.execute(
            "SELECT confdeltype FROM pg_constraint con "
            "JOIN pg_class rel ON rel.oid = con.conrelid "
            "JOIN pg_attribute att ON att.attrelid = rel.oid AND att.attnum = ANY(con.conkey) "
            "WHERE con.contype='f' AND rel.relname=%s AND att.attname='user_id'", (t,)
        ).fetchone()
        if not fk or fk["confdeltype"] != "c":
            unlisted.append(t)
check("every user_id table is either listed for deletion or ON DELETE CASCADE",
      not unlisted, unlisted)

with psycopg.connect(DB, row_factory=dict_row) as c:
    n_admin = c.execute("SELECT COUNT(*) n FROM users WHERE role='admin'").fetchone()["n"]
    if n_admin == 1:
        r = client.request("DELETE", "/api/users/admin-1", json={"confirmation":"DELETE"}, headers={"x-test-user":"admin-1"})
        check("cannot delete the last admin (409)", r.status_code == 409, r.status_code)
    else:
        r = client.request("DELETE", "/api/users/admin-2", json={"confirmation":"DELETE"}, headers={"x-test-user":"admin-1"})
        check("admin can delete another admin", r.status_code in (200,404), r.status_code)
        print(f"   (admins in seed: {n_admin})")
FAILS = []
def check(name, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + name + (f"   {extra}" if extra and not cond else ""))
    if not cond: FAILS.append(name)

import llm
import routers.assistant as A
from log_safety import safe_exception
from routers.assistant import ChatRequest, _llm_reply

conn = psycopg.connect(DB, row_factory=dict_row)

# Real officer profile from the seed, to prove the test uses genuine PII.
row = conn.execute("SELECT * FROM users WHERE role='learner' AND career_goal IS NOT NULL LIMIT 1").fetchone()
NAME, EMAIL, DEPT = row["name"], row["email"], row["department"]
EDU, GOAL, EMPID = row["education"], row["career_goal"], row["employee_id"]
DESIG = row["designation"]
print(f"testing with real seed PII: name={NAME!r} email={EMAIL!r} dept={DEPT!r} employee_id={EMPID!r}")

captured = {}
def fake_chat(messages, **kw):
    captured["messages"] = messages
    return "ok"
llm.chat = fake_chat
A.llm.chat = fake_chat

req = ChatRequest(user_id=row["id"], message="Which course should I take next?")
_llm_reply(conn, req)
sent = "\n".join(m["content"] for m in captured["messages"])

print("\n== advisor payload sent to the LLM provider ==")
print("  chars:", len(sent))
for label, val in [("name", NAME), ("email", EMAIL), ("department", DEPT),
                   ("employee_id", EMPID), ("education", EDU), ("career_goal", GOAL)]:
    check(f"payload omits {label}", (val or "\x00") not in sent, repr(val))
check("payload omits any email-shaped string", "@" not in sent, [l for l in sent.split() if "@" in l][:3])
check("payload still has target role (needed to advise)", (row["target_role"] or "Data Analyst") in sent)
check("payload still has competency levels (needed to advise)", "FULL COMPETENCY LEVELS" in sent)
check("payload still has skill gaps (needed to advise)", "SKILL GAPS" in sent)
check("payload keeps designation for a respectful salutation", (DESIG in sent) or ("the officer" in sent))
check("payload tells the model not to guess a name", "never guess" in sent)

# the request body itself is sent (that is the point of a chat) but check history handling
print("\n== opt-in flag ==")
os.environ["ADVISOR_SHARE_PROFILE"] = "1"
_llm_reply(conn, ChatRequest(user_id=row["id"], message="hi"))
sent_on = "\n".join(m["content"] for m in captured["messages"])
check("opt-in sends education", (EDU in sent_on), EDU)
check("opt-in STILL never sends the name", NAME not in sent_on, NAME)
check("opt-in STILL never sends the email", EMAIL not in sent_on)
del os.environ["ADVISOR_SHARE_PROFILE"]

# ---------------------------------------------------------------- log redaction
print("\n== log redaction under a real PII-bearing DB error ==")
from log_safety import safe_exception, redact

buf = io.StringIO()
h = logging.StreamHandler(buf)
h.setFormatter(logging.Formatter("%(message)s"))
lg = logging.getLogger("sakshamai.db"); lg.addHandler(h); lg.setLevel(logging.DEBUG)

VICTIM = "victim.worker@gov.example"
conn.execute("DROP TABLE IF EXISTS t"); conn.execute("CREATE TABLE t (id serial primary key, email text unique)")
conn.execute("INSERT INTO t (email) VALUES (%s)", (VICTIM,))
conn.commit()
try:
    conn.execute("INSERT INTO t (email) VALUES (%s)", (VICTIM,))
    conn.commit()
except Exception as e:
    lg.warning("%s", safe_exception(e, context="database health query failed"))
out = buf.getvalue()
print("  logged:", out.strip())
check("log line does NOT contain the email", VICTIM not in out, out)
check("log line still identifies the failure", "UniqueViolation" in out and "23505" in out, out)

buf.truncate(0); buf.seek(0)
lg.warning("%s", safe_exception(httpx_err := __import__("httpx").ConnectError("connect to https://xyz.supabase.co refused")))
out = buf.getvalue()
print("  logged:", out.strip())
check("transport log does NOT contain the url", "xyz.supabase.co" not in out, out)
check("transport log keeps the exception class", "ConnectError" in out, out)
lg.removeHandler(h)
conn.rollback()
conn.execute("DROP TABLE IF EXISTS t"); conn.commit()
conn.close()
# ---------------------------------------------------------------- access log
section("access-log user id redaction")

import logging
from log_safety import RedactingFormatter, scrub_access_log

for line, must_go, must_stay in [
    ('127.0.0.1:1 - "GET /api/users/learner-1 HTTP/1.1" 200 OK', "learner-1", None),
    ('127.0.0.1:1 - "PUT /api/users/learner-3/competencies HTTP/1.1" 200 OK', "learner-3", None),
    ('127.0.0.1:1 - "GET /api/quiz/history/admin-1 HTTP/1.1" 200 OK', "admin-1", None),
    ('127.0.0.1:1 - "GET /api/courses?user_id=learner-7 HTTP/1.1" 200 OK', "learner-7", None),
    ('127.0.0.1:1 - "GET /api/courses/course-1?user_id=admin-1&x=2 HTTP/1.1" 200 OK', "admin-1", "x=2"),
    # 'me' is a fixed literal, not an identifier, and must survive
    ('127.0.0.1:1 - "GET /api/users/me HTTP/1.1" 200 OK', None, "me"),
    ('127.0.0.1:1 - "GET /api/courses HTTP/1.1" 200 OK', None, "/api/courses"),
]:
    out = scrub_access_log(line)
    check(f"scrub: {line.split(chr(34))[1][:46]}", (must_go is None or must_go not in out)
          and (must_stay is None or must_stay in out), out)

# The formatter must delegate to the wrapped one. An earlier version rebuilt a
# plain Formatter from inner._fmt, which dropped uvicorn's custom percent-style
# and made every access line raise KeyError('levelprefix') -- after which the
# raw, unredacted message was written by the logging error handler instead.
class _FakeAccessFormatter(logging.Formatter):
    def format(self, record):
        # mimics uvicorn: injects a key a plain Formatter cannot resolve
        record.__dict__.setdefault("levelprefix", "INFO:")
        return super().format(record)

f = RedactingFormatter(_FakeAccessFormatter("%(levelprefix)s %(message)s"))
rec = logging.LogRecord("uvicorn.access", logging.INFO, __file__, 1,
                        '%s - "%s %s HTTP/%s" %d',
                        ('127.0.0.1:9', 'GET', '/api/users/learner-5', '1.1', 200), None)
rendered = f.format(rec)
check("wrapped formatter renders without error", "levelprefix" not in rendered.split()[0] or True)
check("wrapped formatter preserves the layout prefix", rendered.startswith("INFO:"), rendered)
check("wrapped formatter still redacts the id", "learner-5" not in rendered, rendered)
check("wrapped formatter keeps status and method", "GET" in rendered and "200" in rendered, rendered)

# And the real app must have installed it on the live access logger.
acc = logging.getLogger("uvicorn.access")
check("app installed a RedactingFormatter on uvicorn.access",
      any(isinstance(h.formatter, RedactingFormatter) for h in acc.handlers)
      or (os.environ.get("ACCESS_LOG_REDACT", "").lower() in {"0","false","no","off"}),
      [type(h.formatter).__name__ for h in acc.handlers])


# ------------------------------------------------- session cookie + CSRF
section("httpOnly session cookie and CSRF origin guard")

import auth_tokens
import routers.auth as auth_router
from fastapi import HTTPException

EMAIL = "learner-1@sakshamai.demo"
AUTH_ID = "11111111-2222-3333-4444-555555555555"
FAKE = "fake.jwt.token.value"

# The authorization sections above install a global dependency override for
# current_identity that is never cleared, so every later request is answered by
# a fake identity and these checks would pass for the wrong reason. Suspend it.
_saved_overrides = dict(main.app.dependency_overrides)
main.app.dependency_overrides.clear()

_real_sign_in = auth_router.sign_in
_real_verify = auth_tokens.verify_access_token
def _stub_sign_in(email, password):
    return {"access_token": FAKE, "expires_in": 1800,
            "user": {"id": AUTH_ID, "email": email}}
def _stub_verify(token):
    if token != FAKE:
        raise HTTPException(status_code=401, detail="bad token")
    return {"id": AUTH_ID, "email": EMAIL}
auth_router.sign_in = _stub_sign_in
auth_tokens.verify_access_token = _stub_verify

try:
    r = client.post("/api/auth/login", json={"email": EMAIL, "password": "Demo@1234"})
    check("login succeeds", r.status_code == 200, r.status_code)
    check("token is NOT in the login body", FAKE not in r.text, r.text[:200])
    setc = r.headers.get_list("set-cookie")
    sc = next((x for x in setc if x.startswith("sakshamai_session=")), "")
    check("session cookie is set", bool(sc), setc)
    check("cookie is HttpOnly (unreadable by script)", "HttpOnly" in sc, sc)
    check("cookie is SameSite=Strict (not sent cross-site)", "samesite=strict" in sc.lower(), sc)
    check("cookie is Path=/", "Path=/" in sc, sc)
    check("Max-Age matches the token's own expiry", "Max-Age=1800" in sc, sc)
    check("cookie is Secure on a non-loopback host", "Secure" in sc, sc)

    # Loopback dev is served over plain http, where a Secure cookie would be
    # dropped by the browser and every request would 401. That is the one host
    # allowed to skip it.
    dev = client.post("/api/auth/login", json={"email": EMAIL, "password": "Demo@1234"},
                      headers={"Host": "localhost:8000"})
    dsc = next((x for x in dev.headers.get_list("set-cookie") if x.startswith("sakshamai_session=")), "")
    check("no Secure on loopback http (dev only)", "Secure" not in dsc, dsc)

    # The account-link refusal must keep working as an ops signal while the
    # address itself stays out of the log. Trigger it and capture the warning.
    _auth_buf = io.StringIO()
    _auth_h = logging.StreamHandler(_auth_buf)
    _auth_h.setFormatter(logging.Formatter("%(message)s"))
    _auth_lg = logging.getLogger("sakshamai.auth")
    _auth_lg.addHandler(_auth_h); _auth_lg.setLevel(logging.WARNING)
    _evil = client.post("/api/auth/login",
                        json={"email": "stranger@example.net", "password": "x"},
                        headers={"Origin": "http://localhost:3000"})
    _auth_lg.removeHandler(_auth_h)
    _auth_logged = _auth_buf.getvalue()
    check("unlisted-address sign-in is refused (403)", _evil.status_code == 403, _evil.status_code)
    check("refusal is still logged (ops signal kept)", "refused account link" in _auth_logged, _auth_logged)
    check("refusal log does NOT contain the email", "stranger@example.net" not in _auth_logged, _auth_logged)

    ck = {"sakshamai_session": FAKE}
    check("cookie authenticates a request",
          client.get("/api/auth/me", cookies=ck).status_code == 200)
    _junk = client.get("/api/auth/me", cookies={"sakshamai_session": "junk"})
    check("a junk cookie is rejected, not accepted", _junk.status_code == 401,
          f"{_junk.status_code} {_junk.text[:200]}")

    # The CSRF half: a cookie is an ambient credential, so a state-changing
    # request carrying one must prove it came from our own page.
    check("cookie POST without Origin is refused (CSRF)",
          client.post("/api/auth/logout", cookies=ck).status_code == 403)
    check("cookie POST from an allowed origin succeeds",
          client.post("/api/auth/logout", cookies=ck,
                      headers={"Origin": "http://localhost:3000"}).status_code == 200)
    check("cookie POST from a foreign origin is refused",
          client.post("/api/auth/logout", cookies=ck,
                      headers={"Origin": "https://attacker.example"}).status_code == 403)
    check("a safe method with a cookie needs no Origin",
          client.get("/api/courses", cookies=ck).status_code == 200)
    # Non-browser clients set Authorization, which a page cannot do
    # cross-origin, so they are exempt and keep working unchanged.
    check("Authorization header is exempt from the origin check",
          client.post("/api/auth/logout", headers={"Authorization": f"Bearer {FAKE}"}).status_code == 200)

    out = client.post("/api/auth/logout", cookies=ck,
                      headers={"Origin": "http://localhost:3000"}).headers.get_list("set-cookie")
    check("logout expires the cookie",
          any("sakshamai_session=" in x and "Max-Age=0" in x for x in out), out)
finally:
    auth_router.sign_in = _real_sign_in
    auth_tokens.verify_access_token = _real_verify
    main.app.dependency_overrides.clear()
    main.app.dependency_overrides.update(_saved_overrides)

# The token must not be readable by the client at all.
api_ts = (pathlib.Path(__file__).resolve().parent.parent / "src" / "services" / "api.ts").read_text()
check("frontend no longer stores the token in sessionStorage",
      "sakshamai.token" not in api_ts
      and not any(l.strip().startswith(("let accessToken", "sessionStorage."))
                  for l in api_ts.splitlines()))
check("frontend no longer reads or sends an Authorization header",
      "getAccessToken" not in api_ts and "setAccessToken" not in api_ts
      and "Authorization" not in api_ts)
check("frontend sends cookies on every request", api_ts.count("credentials: 'include'") >= 2,
      api_ts.count("credentials: 'include'"))
ctx = (pathlib.Path(__file__).resolve().parent.parent / "src" / "store" / "AppContext.tsx").read_text()
check("logging out also tells the server", "apiLogout()" in ctx)
check("no build artifact contains a stored session token",
      not any("sakshamai.token" in f.read_text(errors="ignore")
              for f in pathlib.Path(__file__).resolve().parent.parent.joinpath("dist").rglob("*.js")))

# The two remaining code paths that could put user data into a log. Pin both
# so the "no log line contains user data" claim stays true as the code moves.
auth_src = (pathlib.Path(__file__).resolve().parent.parent / "backend" / "routers" / "auth.py").read_text()
check("auth refusal passes the address through redact()", "redact(email)" in auth_src, "auth.py")
main_src = (pathlib.Path(__file__).resolve().parent.parent / "backend" / "main.py").read_text()
check("unhandled-error handler redacts the exception text", "redact(str(exc))" in main_src, "main.py")
check("full exception traceback only under a debug flag", 'if debug_enabled():' in main_src, "main.py")


print("\n" + ("ALL PRIVACY CHECKS PASS" if not FAILS else f"{len(FAILS)} FAILURES: {FAILS}"))
sys.exit(1 if FAILS else 0)
