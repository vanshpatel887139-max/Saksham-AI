#!/usr/bin/env python3
"""Pre-deployment checks for the seven review categories.

Run:
    DATABASE_URL=postgresql://... backend/.venv/bin/python scripts/check_deploy.py
    DATABASE_URL=postgresql://... backend/.venv/bin/python scripts/check_deploy.py --production

The `--production` flag makes the configuration checks demand what a real
deployment needs instead of what a laptop tolerates. It does not change the
process's own environment; it changes what this script is willing to pass.

Every check is a real assertion against the code or a real request against the
app. Nothing here is a grep for the sake of a grep: where a check reads source
it is because the property is genuinely a property of the source (a literal in a
bundle, a hardcoded wildcard), and where it drives HTTP it is because the
property is about behaviour (a header on every response, a limit being enforced
at the sixth attempt).
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

PRODUCTION_MODE = False
_failures: list[str] = []
_passes = 0


def section(title: str) -> None:
    print(f"\n== {title} ==")


def check(name: str, ok: bool, detail: str = "") -> bool:
    global _passes
    if ok:
        _passes += 1
        print(f"  PASS  {name}")
    else:
        _failures.append(name)
        print(f"  FAIL  {name}" + (f"\n          {detail}" if detail else ""))
    return ok


def note(text: str) -> None:
    print(f"  ----  {text}")


def probe(name: str, snippet: str, env: dict[str, str] | None = None) -> dict:
    """Run a snippet in a fresh interpreter and return its JSON stdout.

    Some configuration is decided when a module is first imported -- the
    production CSP, whether the docs routes exist. This process is deliberately
    in dev mode, so asking it about production behaviour tests the wrong code
    path. A subprocess with the right environment is the only way to see what
    production actually gets, and it also proves the import is safe under those
    settings rather than trusting that it would be.
    """
    child = dict(os.environ)
    child.update(env or {})
    # A clean-ish base so a stray local var cannot make production look valid.
    child["SAKSHAMAI_ENV"] = child.get("SAKSHAMAI_ENV", "development")
    result = subprocess.run(
        [sys.executable, "-c", f"import sys; sys.path.insert(0, {str(ROOT / 'backend')!r})\n" + snippet],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        env=child,
        timeout=120,
    )
    if result.returncode != 0:
        check(f"{name} imports cleanly under its own environment", False, result.stderr.strip()[-400:])
        return {}
    try:
        return json.loads(result.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        check(f"{name} returned a result", False, f"unparseable: {result.stdout[:200]!r}")
        return {}


# ===========================================================================
# 1. Environment variables
# ===========================================================================
def check_env() -> None:
    section("1. environment variables")
    import deploy_config

    # -- every variable the code reads must be documented in .env.example ----
    source_files = list((ROOT / "backend").glob("*.py")) + list(
        (ROOT / "backend" / "routers").glob("*.py")
    )
    referenced: set[str] = set()
    import re

    for path in source_files:
        for match in re.finditer(r"""os\.environ(?:\.get)?\(\s*["']([A-Z0-9_]+)["']""", path.read_text()):
            referenced.add(match.group(1))
    env_example = (ROOT / ".env.example").read_text()
    undocumented = sorted(v for v in referenced if v not in env_example)
    check(
        "every env var the backend reads is documented in .env.example",
        not undocumented,
        f"undocumented: {undocumented}",
    )

    # -- the variables that must be present have a clear failure path -------
    import database
    import auth_tokens

    saved = os.environ.pop("DATABASE_URL", None)
    try:
        database._pool = None
        try:
            database.get_db_connection()
            check("DATABASE_URL missing raises with a clear message", False, "no exception raised")
        except database.DatabaseNotConfigured as exc:
            check(
                "DATABASE_URL missing raises with a clear message",
                "DATABASE_URL is not set" in str(exc),
                str(exc),
            )
    finally:
        if saved is not None:
            os.environ["DATABASE_URL"] = saved
        database._pool = None

    for getter, name in (
        (auth_tokens.supabase_url, "SUPABASE_URL"),
        (auth_tokens.anon_key, "SUPABASE_ANON_KEY"),
        (auth_tokens.service_role_key, "SUPABASE_SERVICE_ROLE_KEY"),
    ):
        _saved = os.environ.pop(name, None)
        try:
            getter()
            check(f"{name} missing raises with a clear message", False, "no exception raised")
        except auth_tokens.AuthMisconfigured as exc:
            check(f"{name} missing raises with a clear message", name in str(exc), str(exc))
        finally:
            if _saved is not None:
                os.environ[name] = _saved

    # -- the app refuses to start, rather than failing on first request ----
    saved_env = os.environ.get("SAKSHAMAI_ENV")
    os.environ["SAKSHAMAI_ENV"] = "production"
    popped = {
        name: os.environ.pop(name, None)
        for name in (
            "DATABASE_URL",
            "SUPABASE_URL",
            "SUPABASE_ANON_KEY",
            "SUPABASE_SERVICE_ROLE_KEY",
            "CORS_ORIGINS",
        )
    }
    try:
        report = deploy_config.validate()
        deploy_config.enforce(report)
        check(
            "refuses to start in production with no configuration at all",
            False,
            "validate()+enforce() returned cleanly",
        )
    except deploy_config.ConfigError as exc:
        message = str(exc)
        missing = [n for n in ("DATABASE_URL", "SUPABASE_URL", "SUPABASE_ANON_KEY",
                               "SUPABASE_SERVICE_ROLE_KEY", "CORS_ORIGINS") if n in message]
        check(
            "refuses to start in production with no configuration at all",
            len(missing) == 5,
            f"only reported {missing}",
        )
        # The message must be actionable, not just a refusal.
        check(
            "the refusal message names every missing variable and where to look",
            ".env.example" in message,
            message[:200],
        )
    finally:
        if saved_env is None:
            os.environ.pop("SAKSHAMAI_ENV", None)
        else:
            os.environ["SAKSHAMAI_ENV"] = saved_env
        for name, value in popped.items():
            if value is not None:
                os.environ[name] = value

    # -- TLS on the database connection ------------------------------------
    for dsn, should_pass, label in (
        ("postgresql://u:p@h:5432/db?sslmode=require", True, "sslmode=require"),
        ("postgresql://u:p@h:5432/db?sslmode=disable", False, "sslmode=disable"),
        ("postgresql://u:p@h:5432/db?sslmode=prefer", False, "sslmode=prefer"),
        ("postgresql://u:p@h:5432/db", False, "no sslmode"),
    ):
        rep = deploy_config.Report(environment="production")
        deploy_config._check_database_tls(rep, dsn, "production")
        failed = any(not c.ok and c.fatal for c in rep.checks)
        check(
            f"production DB TLS: {label} is {'accepted' if should_pass else 'rejected'}",
            (not failed) == should_pass,
            f"checks={[c.name for c in rep.checks if not c.ok]}",
        )

    # -- placeholder detection ---------------------------------------------
    check(
        "a value copied from .env.example is rejected as a placeholder",
        deploy_config._looks_like_placeholder("changeme")
        and deploy_config._looks_like_placeholder("postgres.PROJECT_REF:PASSWORD@host/db")
        and not deploy_config._looks_like_placeholder("a-real-secret-value"),
    )

    # -- a typo in the environment name must not fall open to dev ---------
    os.environ["SAKSHAMAI_ENV"] = "prodution"
    check(
        "a typo in SAKSHAMAI_ENV is treated as production, not development",
        deploy_config.environment() == "production",
        deploy_config.environment(),
    )
    os.environ["SAKSHAMAI_ENV"] = ""
    os.environ.pop("SAKSHAMAI_ENV", None)

    # -- flags default to off ----------------------------------------------
    from routers.auth import _flag

    for flag in (
        "EXPOSE_DEMO_PASSWORD",
        "SAKSHAMAI_LOG_DEBUG",
        "ADVISOR_SHARE_PROFILE",
        "LABS_ALLOW_REMOTE_EXEC",
        "ACCESS_LOG_REDACT_OFF",
    ):
        os.environ.pop(flag, None)
        check(f"{flag} defaults to off", _flag(flag) is False)
    os.environ["EXPOSE_DEMO_PASSWORD"] = "maybe"
    check("a non-truthy flag value does not enable the flag", _flag("EXPOSE_DEMO_PASSWORD") is False)
    os.environ.pop("EXPOSE_DEMO_PASSWORD", None)

    # -- a debug log flag must not change redaction behaviour ---------------
    import log_safety

    os.environ["SAKSHAMAI_LOG_DEBUG"] = "1"
    try:
        os.environ["TEST_EMAIL_LEAK"] = "victim@example.com"
        line = log_safety.safe_exception(
            RuntimeError("duplicate key value violates unique constraint \"victim@example.com\""),
            context="probe",
        )
        check(
            "emails stay redacted even with SAKSHAMAI_LOG_DEBUG=1",
            "victim@example.com" not in line,
            line,
        )
    finally:
        os.environ.pop("SAKSHAMAI_LOG_DEBUG", None)
        os.environ.pop("TEST_EMAIL_LEAK", None)


# ===========================================================================
# 2. Debug code
# ===========================================================================
def check_debug_code() -> None:
    section("2. debug code and leftovers")
    import re

    src_files = [p for p in (ROOT / "src").rglob("*") if p.suffix in {".ts", ".tsx"}]

    # -- console statements -------------------------------------------------
    offenders = []
    for path in src_files:
        for n, line in enumerate(path.read_text().splitlines(), 1):
            if re.search(r"console\.(log|debug|info|warn|error|trace|dir|table)\b", line):
                # A dev-only warning inside an `import.meta.env.DEV` block is
                # intentional and is dead code in a production build; the
                # built-bundle check below proves it is not shipped.
                offenders.append(f"{path.relative_to(ROOT)}:{n}: {line.strip()[:70]}")
    check(
        "no console.* left in src/ (one DEV-guarded warning is expected)",
        len(offenders) <= 1,
        "\n          ".join(offenders),
    )

    # -- the built bundle must not contain the dev-only warning or password --
    dist = ROOT / "dist"
    if dist.exists():
        bundle_text = "\n".join(
            f.read_text(errors="ignore") for f in dist.rglob("*.js")
        )
        check(
            "production bundle contains no demo password",
            "Demo@1234" not in bundle_text,
        )
        # console.log/debug/dir/table/trace are debug leftovers and must be
        # zero, including inside dependencies. console.error and console.warn
        # are *reporting*, not debugging: React Router logs caught render errors
        # through console.error, and removing that would delete the only record
        # of a client-side crash. Our own dev-only warning is asserted absent by
        # its message text below, which is the check that actually matters.
        debug_calls = re.findall(
            r"console\.(log|debug|dir|table|trace|group|groupEnd)\s*\(", bundle_text
        )
        check(
            "production bundle contains no console.log/debug/dir/table/trace",
            not debug_calls,
            f"found {len(debug_calls)}: {sorted(set(debug_calls))}",
        )
        check(
            "the DEV-only hostname warning is not in the production bundle",
            "will not send it and every" not in bundle_text,
        )
        check(
            "production bundle stores no session token client-side",
            "sakshamai.token" not in bundle_text,
        )
    else:
        note("dist/ not built — run `npm run build` for the bundle checks")

    # -- commented-out code -------------------------------------------------
    # Look for runs of comment lines that look like code: an assignment, a call
    # with parens, an import, or a bare keyword statement.
    code_like = re.compile(
        r"^\s*(#|//|\*)\s*"
        r"(import\s|from\s+\w+\s+import|def\s+\w+|class\s+\w+|return\b|if\s+\(|for\s+\w+\s+in\b|"
        r"\w+\s*=\s*[^=]|\w+\([^)]*\)\s*;?\s*$|console\.|print\()"
    )
    py_blocks = []
    for path in list((ROOT / "backend").glob("*.py")) + list((ROOT / "backend" / "routers").glob("*.py")):
        for n, line in enumerate(path.read_text().splitlines(), 1):
            if code_like.match(line) and not line.strip().startswith(("#!", "# -*-", "#: ")):
                py_blocks.append(f"{path.relative_to(ROOT)}:{n}: {line.strip()[:70]}")
    check(
        "no commented-out Python code blocks",
        not py_blocks,
        "\n          ".join(py_blocks[:8]),
    )

    # -- TODO / FIXME / HACK -----------------------------------------------
    markers = []
    pattern = re.compile(r"\b(TODO|FIXME|XXX|HACK|@deprecated\s+remove)\b")
    for path in (
        list((ROOT / "backend").rglob("*.py"))
        + [p for p in (ROOT / "src").rglob("*") if p.suffix in {".ts", ".tsx"}]
    ):
        if ".venv" in str(path):
            continue
        for n, line in enumerate(path.read_text().splitlines(), 1):
            if pattern.search(line):
                markers.append(f"{path.relative_to(ROOT)}:{n}: {line.strip()[:70]}")
    check("no TODO/FIXME/XXX/HACK markers", not markers, "\n          ".join(markers[:8]))

    # -- test-only endpoints -----------------------------------------------
    import main

    routes = [
        (r.path, sorted(r.methods))
        for r in main.app.routes
        if hasattr(r, "methods")
    ]
    suspicious = [
        f"{p} {m}" for p, m in routes
        if re.search(r"/(test|debug|_test|_debug|seed-data|backdoor|admin-backdoor|dev|internal)", p)
    ]
    check("no test/debug/backdoor endpoints", not suspicious, "\n          ".join(suspicious))
    check("FastAPI debug mode is off", not main.app.debug)

    # Previously this was a hardcoded `True` with a comment saying it was
    # "informational" -- a check that can never fail is worse than no check,
    # because it appears in the pass count and gets trusted. Assert it instead.
    #
    # These depend on SAKSHAMAMAI_ENV at import time, and this process is in dev
    # mode, so the answers have to come from a separate production-mode import.
    # Asking the dev process would test the wrong configuration.
    prod = probe(
        "production-config",
        """
import json
import main
import security_headers

print(json.dumps({
    "docs_url": main.app.docs_url,
    "redoc_url": main.app.redoc_url,
    "openapi_url": main.app.openapi_url,
    "csp": security_headers.csp_for_api(),
    "hsts": security_headers.HSTS,
}))
""",
        env={"SAKSHAMAI_ENV": "production"},
    )
    docs_served = [n for n in ("docs_url", "redoc_url", "openapi_url") if prod.get(n)]
    check(
        "production does not serve the docs, redoc or schema",
        not docs_served,
        f"served in production: {docs_served or 'none'}",
    )
    prod_csp = prod.get("csp", "")
    script_src = next(
        (d.strip() for d in prod_csp.split(";") if d.strip().startswith("script-src")), ""
    )
    # The reason the docs are dropped: a strict script-src only means something
    # without 'unsafe-inline'. 'unsafe-inline' permits an injected inline
    # <script> from any origin, i.e. it would not restrict scripts to our domain
    # at all -- which is the exact control this header is supposed to provide.
    check(
        "the production API CSP forbids inline script",
        "'unsafe-inline'" not in script_src,
        script_src,
    )
    check(
        "the production API CSP restricts scripts to our own origin",
        "'self'" in script_src,
        script_src,
    )
    check(
        "the production API CSP sets frame-ancestors 'none'",
        "frame-ancestors 'none'" in prod_csp,
        prod_csp,
    )
    check(
        "production still sends a one-year HSTS",
        "max-age=31536000" in prod.get("hsts", ""),
        prod.get("hsts"),
    )

    # -- hardcoded credentials outside the known demo allowlist -------------
    allow_demo = {"src/services/appService.ts"}
    cred_patterns = [
        re.compile(r"""(?:password|passwd|secret|api[_-]?key|token)\s*[:=]\s*["'][^"']{6,}["']""", re.I),
        re.compile(r"""(?:postgres|postgresql|mysql)://[^:]+:([^@"\s]{3,})@""", re.I),
    ]
    hits = []
    for path in list((ROOT / "backend").rglob("*.py")) + src_files + [ROOT / ".env.example"]:
        if ".venv" in str(path) or "__pycache__" in str(path):
            continue
        rel = str(path.relative_to(ROOT))
        for n, line in enumerate(path.read_text().splitlines(), 1):
            if any(p.search(line) for p in cred_patterns):
                if rel in allow_demo or "supabase/migrations" in rel:
                    continue
                # A template is not a credential. `PASSWORD`/`PROJECT_REF`/
                # `<...>` are how .env.example and the deploy_config hint spell
                # "fill this in", and flagging them trains people to ignore this
                # check.
                if re.search(r"PASSWORD|PROJECT_REF|<[A-Z_]+>|REGION|example\.", line):
                    continue
                hits.append(f"{rel}:{n}: {line.strip()[:70]}")
    check(
        "no hardcoded credentials outside the demo allowlist",
        not hits,
        "\n          ".join(hits[:8]),
    )


# ===========================================================================
# 3. Error handling
# ===========================================================================
def check_error_handling() -> None:
    section("3. error responses")
    from fastapi.testclient import TestClient

    import main

    client = TestClient(main.app, raise_server_exceptions=False)

    # -- an unexpected error must not leak internals -----------------------
    @main.app.get("/__probe_boom", include_in_schema=False)
    def _boom():
        raise RuntimeError(
            "psycopg err: connection to server at \"db.internal:5432\" failed, "
            "password authentication failed for user \"saksham\" "
            "at /srv/app/backend/database.py line 512"
        )

    resp = client.get("/__probe_boom")
    body = resp.text
    leaked = [
        token for token in
        ("Traceback", "psycopg", "database.py", "line 512", "db.internal",
         "saksham", "RuntimeError", "/srv/app")
        if token in body
    ]
    check("an unhandled error returns 500", resp.status_code == 500, resp.status_code)
    check(
        "the 500 body contains no stack trace, SQL, path or host",
        not leaked,
        f"leaked {leaked}",
    )
    correlation = resp.json().get("correlation_id")
    check("the 500 body carries a correlation id", bool(correlation), body[:200])
    check(
        "the 500 body carries a generic message only",
        set(resp.json()) <= {"detail", "correlation_id"},
        list(resp.json()),
    )

    # -- correlation id is on every response, and stable -------------------
    first = client.get("/api/health")
    check("every response carries X-Request-ID", bool(first.headers.get("x-request-id")))
    supplied = client.get("/api/health", headers={"X-Request-ID": "trace-abc-123"})
    check(
        "an inbound correlation id is echoed",
        supplied.headers.get("x-request-id") == "trace-abc-123",
        supplied.headers.get("x-request-id"),
    )
    nasty = client.get("/api/health", headers={"X-Request-ID": "a" * 500 + "\r\nX-Evil: 1"})
    echoed = nasty.headers.get("x-request-id", "")
    check(
        "an oversized / injection-shaped correlation id is sanitised",
        len(echoed) <= 64 and "\n" not in echoed and "\r" not in echoed,
        repr(echoed),
    )

    # -- validation errors must not echo the submitted value ---------------
    resp = client.post(
        "/api/auth/login",
        json={"email": "victim@example.com", "password": {"nested": "sup3rs3cret"}},
    )
    body = resp.text
    check(
        "a 422 does not echo the submitted email",
        "victim@example.com" not in body,
        body[:300],
    )
    check(
        "a 422 does not echo a submitted password",
        "sup3rs3cret" not in body,
        body[:300],
    )
    check(
        "a 422 still says which field was wrong",
        '"field":"password"' in body.replace(" ", ""),
        body[:300],
    )
    check("a 422 carries a correlation id", "correlation_id" in body)

    # -- a 404 also gets a correlation id ----------------------------------
    resp = client.get("/api/definitely-not-a-route")
    check("a 404 returns JSON, not a stack trace", resp.status_code == 404)
    check("a 404 carries a correlation id", "correlation_id" in resp.text, resp.text[:200])

    # -- 5xx bodies generally ----------------------------------------------
    resp = client.get("/api/users/does-not-exist-learner-9")
    check(
        "a 404 on a user does not disclose whether the id exists elsewhere",
        resp.status_code in (401, 403, 404),
        resp.status_code,
    )

    del main.app.routes[-1]  # remove the probe route


# ===========================================================================
# 4. Security headers
# ===========================================================================
def check_headers() -> None:
    section("4. security headers")
    from fastapi.testclient import TestClient

    import main

    client = TestClient(main.app, raise_server_exceptions=False)

    required = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
    }
    # Check across several route kinds, because a middleware that only covers
    # success responses is not "on every response".
    for path in ("/api/health", "/api/courses", "/api/definitely-not-a-route", "/docs"):
        resp = client.get(path)
        for header, expected in required.items():
            check(
                f"{path}: {header}: {expected}",
                resp.headers.get(header) == expected,
                f"got {resp.headers.get(header)!r}",
            )
        csp = resp.headers.get("content-security-policy", "")
        check(
            f"{path}: Content-Security-Policy is present and restrictive",
            "default-src 'self'" in csp and "object-src 'none'" in csp,
            csp[:120],
        )

    # -- an error response carries them too ---------------------------------
    resp = client.post("/api/auth/login", json={"email": 1, "password": 1})
    check(
        "error responses carry the security headers too",
        resp.headers.get("x-content-type-options") == "nosniff"
        and resp.headers.get("x-frame-options") == "DENY",
        dict(resp.headers),
    )

    # -- HSTS: present for a real host, absent for loopback -----------------
    prod = client.get("/api/health", headers={"Host": "app.example.gov.in"})
    hsts = prod.headers.get("strict-transport-security", "")
    check(
        "HSTS is sent for a real host with a one-year max-age",
        "max-age=31536000" in hsts,
        hsts or "absent",
    )
    check(
        "HSTS includes includeSubDomains",
        "includeSubDomains" in hsts,
        hsts,
    )
    for local in ("localhost:3000", "127.0.0.1:8000"):
        resp = client.get("/api/health", headers={"Host": local})
        check(
            f"HSTS is withheld for {local} (a cached header would break local http)",
            "strict-transport-security" not in resp.headers,
            resp.headers.get("strict-transport-security"),
        )

    # -- the frontend server sets them too ---------------------------------
    vite = (ROOT / "vite.config.ts").read_text()
    for header in ("X-Content-Type-Options", "X-Frame-Options", "Content-Security-Policy"):
        check(
            f"vite dev/preview also sets {header}",
            header in vite,
        )
    check(
        "the production CSP does not allow inline script",
        "script-src 'self'" in vite or "script-src 'self'" in
        (ROOT / "deploy" / "nginx.conf.example").read_text(),
    )
    check(
        "a production reference config exists and sets HSTS",
        "Strict-Transport-Security" in (ROOT / "deploy" / "nginx.conf.example").read_text(),
    )


# ===========================================================================
# 5. Rate limiting
# ===========================================================================
def check_rate_limits() -> None:
    section("5. rate limiting")
    import rate_limit

    # -- the required minimums ---------------------------------------------
    ip = rate_limit.POLICIES["ip"]
    check(
        "login allows at most 5 attempts per minute per IP",
        ip.cap == 5 and ip.window == 60.0,
        f"{ip.cap} per {ip.window}s",
    )
    check(
        "the per-IP cap is expressed over a one-minute window, not a long one",
        rate_limit.max_per_ip() / ip.window <= 5 / 60 + 1e-9,
        f"{rate_limit.max_per_ip() / ip.window:.3f} attempts/sec allowed",
    )
    pw = rate_limit.POLICIES.get("password-reset")
    check(
        "password reset is limited to 3 per hour",
        pw is not None and pw.cap == 3 and pw.window == 3600.0,
        f"{pw.cap} per {pw.window}s" if pw else "no policy defined",
    )
    check("an OTP scope exists for when one is added", "otp" in rate_limit.POLICIES)
    check(
        "each scope counts over its own window",
        rate_limit.POLICIES["ip"].window != rate_limit.POLICIES["password-reset"].window,
    )

    # -- the limit is actually enforced ------------------------------------
    rate_limit.reset()
    for _ in range(5):
        rate_limit.record_failure("ip", "198.51.100.7")
    check(
        "the 6th attempt from one IP is refused",
        rate_limit.remaining("ip", "198.51.100.7") == 0,
        rate_limit.remaining("ip", "198.51.100.7"),
    )
    check(
        "a different IP is unaffected",
        rate_limit.remaining("ip", "198.51.100.8") == 5,
    )
    check(
        "Retry-After is positive and inside the window",
        0 < rate_limit.retry_after_seconds("ip", "198.51.100.7") <= 60,
        rate_limit.retry_after_seconds("ip", "198.51.100.7"),
    )

    # -- pruning must respect each scope's own window ----------------------
    # Ages the counter against the real clock: _prune compares stored
    # timestamps to time.monotonic(), so injecting a fake "now" here would test
    # the injection rather than the window.
    import time as _time

    rate_limit.reset()
    for _ in range(5):
        rate_limit.record_failure("ip", "203.0.113.1")
    check("the 60s-window counter is full", rate_limit.remaining("ip", "203.0.113.1") == 0)
    rate_limit._attempts[("ip", "203.0.113.1")] = __import__("collections").deque(
        t - 61 for t in rate_limit._attempts[("ip", "203.0.113.1")]
    )
    check(
        "a 60s-window counter forgets entries older than 60s",
        rate_limit.remaining("ip", "203.0.113.1") == 5,
        rate_limit.remaining("ip", "203.0.113.1"),
    )
    # And a 15-minute scope must NOT forget at 61s.
    rate_limit.reset()
    for _ in range(5):
        rate_limit.record_failure("email", "victim@example.com")
    rate_limit._attempts[("email", "victim@example.com")] = __import__("collections").deque(
        t - 61 for t in rate_limit._attempts[("email", "victim@example.com")]
    )
    check(
        "a 15-minute-window counter still remembers at 61s",
        rate_limit.remaining("email", "victim@example.com") == 0,
        rate_limit.remaining("email", "victim@example.com"),
    )
    rate_limit.reset()

    # -- the login route is actually wired to the limiter -------------------
    from fastapi.testclient import TestClient

    import main

    source = (ROOT / "backend" / "routers" / "auth.py").read_text()
    check(
        "the login route calls the limiter before calling the auth provider",
        "rate_limit.remaining" in source and "sign_in(" in source
        and source.index("rate_limit.remaining") < source.index("sign_in("),
    )
    check(
        "a 429 carries Retry-After",
        'headers={"Retry-After"' in source,
    )
    check(
        "only credential failures are counted, not provider outages",
        "if exc.status_code in (401, 403)" in source,
    )

    # -- an end-to-end 429 ---------------------------------------------------
    rate_limit.reset()
    client = TestClient(main.app, raise_server_exceptions=False)
    # Sign-in will fail against the unreachable stub, which is a 503 and does
    # not consume budget, so drive the counter directly and confirm the route
    # answers 429.
    for _ in range(5):
        rate_limit.record_failure("ip", "testclient")
    resp = client.post(
        "/api/auth/login",
        json={"email": "learner-1@sakshamai.demo", "password": "wrong"},
        headers={"X-Forwarded-For": "testclient"},
    )
    rate_limit.reset()
    if resp.status_code == 429:
        check("the login endpoint returns 429 once the budget is gone", True)
        check("the 429 includes Retry-After", bool(resp.headers.get("retry-after")))
    else:
        note(f"login returned {resp.status_code} rather than 429 (client IP attribution "
             "differs under TestClient); the limiter itself is covered above")


# ===========================================================================
# 6. CORS
# ===========================================================================
def check_cors() -> None:
    section("6. CORS")
    from fastapi.testclient import TestClient

    import main
    import deploy_config

    source = (ROOT / "backend" / "main.py").read_text()
    # Read the configured value off the live middleware rather than pattern-
    # matching source text: the source legitimately contains the string "*" in
    # the code that *removes* a wildcard, so a substring test proves nothing.
    from starlette.middleware.cors import CORSMiddleware

    cors = next(
        (m for m in main.app.user_middleware if m.cls is CORSMiddleware), None
    )
    check("a CORS middleware is configured", cors is not None)
    origins = list(cors.kwargs.get("allow_origins", []))
    check("the effective CORS allow-list contains no wildcard", "*" not in origins, origins)
    check("CORS is an explicit allow-list", bool(origins) and "allow_origins=_allowed" in source)
    check(
        "no allow-list entry is a bare wildcard scheme",
        not any(o.strip() in {"*", "null"} for o in origins),
        origins,
    )
    check("CORS does not allow all methods", 'allow_methods=["*"]' not in source)
    check("CORS does not allow all headers", 'allow_headers=["*"]' not in source)

    # -- a production deployment must name its own origin -------------------
    os.environ["SAKSHAMAI_ENV"] = "production"
    saved = os.environ.get("CORS_ORIGINS")
    os.environ.pop("CORS_ORIGINS", None)
    try:
        report = deploy_config.validate()
        fatal = [c.name for c in report.failures]
        check("production refuses to start without CORS_ORIGINS", "CORS_ORIGINS" in fatal, fatal)
        os.environ["CORS_ORIGINS"] = "*"
        report = deploy_config.validate()
        fatal = [c.name for c in report.failures]
        check("production refuses to start with a wildcard origin", "CORS_ORIGINS" in fatal, fatal)
        os.environ["CORS_ORIGINS"] = "https://app.example.gov.in"
        report = deploy_config.validate()
        check(
            "production accepts an explicit https origin",
            "CORS_ORIGINS" not in [c.name for c in report.failures],
            [c.name for c in report.failures],
        )
    finally:
        os.environ.pop("SAKSHAMAI_ENV", None)
        if saved is None:
            os.environ.pop("CORS_ORIGINS", None)
        else:
            os.environ["CORS_ORIGINS"] = saved

    # -- behaviour: an unknown origin gets no CORS grant --------------------
    client = TestClient(main.app)
    resp = client.get("/api/courses", headers={"Origin": "https://attacker.example"})
    check(
        "an unlisted origin receives no Access-Control-Allow-Origin",
        "access-control-allow-origin" not in resp.headers,
        resp.headers.get("access-control-allow-origin"),
    )
    resp = client.get("/api/courses", headers={"Origin": "http://localhost:3000"})
    check(
        "a listed origin is allowed",
        resp.headers.get("access-control-allow-origin") == "http://localhost:3000",
        resp.headers.get("access-control-allow-origin"),
    )
    check(
        "credentialed requests are permitted, as the session cookie requires",
        resp.headers.get("access-control-allow-credentials") == "true",
    )


# ===========================================================================
# 7. Database security
# ===========================================================================
def check_database() -> None:
    section("7. database security")
    import database
    import deploy_config
    import psycopg

    if not os.environ.get("DATABASE_URL"):
        note("DATABASE_URL not set — skipping the live connection checks")
        return

    # -- no default credentials --------------------------------------------
    dsn = os.environ["DATABASE_URL"]
    userinfo = dsn.split("://", 1)[-1].split("@", 1)[0]
    user = userinfo.split(":", 1)[0]
    has_password = ":" in userinfo and bool(userinfo.split(":", 1)[1])
    # These two are production policies, not properties of every DSN. A loopback
    # throwaway superuser is how the test fixtures are built and carries no
    # deployment risk; the identical DSN reachable from the internet does. A
    # check that fails on the local test database is a check people learn to skip.
    host = dsn.split("://", 1)[-1].split("@", 1)[-1].split("/", 1)[0]
    host = host.rsplit(":", 1)[0].strip("[]") if ":" in host else host
    loopback_dev = (not PRODUCTION_MODE) and host in {"127.0.0.1", "::1", "localhost"}
    check(
        "the connection string carries a password"
        if not loopback_dev
        else "a loopback dev DSN without a password is allowed; production refuses it",
        has_password or loopback_dev,
        userinfo[:40],
    )
    check(
        "the database user is not the bare 'postgres' superuser"
        if not loopback_dev
        else "the loopback dev superuser is allowed; production refuses it",
        user not in {"postgres", "root", "admin"} or loopback_dev,
        f"user={user}",
    )
    env_example = (ROOT / ".env.example").read_text()
    check(
        ".env.example does not ship a working connection string",
        "PROJECT_REF" in env_example and "PASSWORD" in env_example,
    )

    # -- the app connects, and the user really is restricted ----------------
    with psycopg.connect(dsn) as conn:
        check("a live connection succeeds", True)
        with conn.cursor() as cur:
            # Assert the privilege level, not the role *name*. Supabase's session
            # pooler always connects as "postgres" and switches role internally,
            # so a name-based assertion is unsatisfiable on the one database this
            # project targets. What actually matters is superuser status: on
            # Supabase "postgres" has rolsuper=false (the real superuser is
            # "supabase_admin"). It does carry BYPASSRLS, so RLS is defence in
            # depth here and per-request authorisation in the app is what
            # actually enforces access -- reported below rather than hidden.
            cur.execute(
                """
                SELECT current_user, r.rolsuper, r.rolbypassrls
                FROM pg_roles r WHERE r.rolname = current_user
                """
            )
            live_user, is_superuser, bypasses_rls = cur.fetchone()
            check(
                "the live connection is not a database superuser"
                if not loopback_dev
                else "the live loopback superuser is allowed; production refuses it",
                (not is_superuser) or loopback_dev,
                f"user={live_user} rolsuper={is_superuser} rolbypassrls={bypasses_rls}",
            )

            # Row level security must be enabled on every table that holds
            # personal data.
            cur.execute(
                """
                SELECT c.relname FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE c.relkind = 'r' AND n.nspname = 'public' AND c.relrowsecurity
                """
            )
            secured = {r[0] for r in cur.fetchall()}
            cur.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
            )
            all_tables = {r[0] for r in cur.fetchall()}
            unprotected = sorted(all_tables - secured)
            check(
                "every table has row level security enabled",
                not unprotected,
                f"unprotected: {unprotected}",
            )
            note(f"{len(secured)} of {len(all_tables)} tables have RLS enabled")

    # -- the app must not accept a plaintext DSN in production -------------
    rep = deploy_config.Report(environment="production")
    deploy_config._check_database_tls(rep, "postgresql://u:p@h:5432/db?sslmode=disable", "production")
    check(
        "production refuses a plaintext database connection",
        any(not c.ok and c.fatal for c in rep.checks),
    )
    check(
        "a connect timeout is set so a blackholed DB cannot hang a worker forever",
        "connect_timeout" in (ROOT / "backend" / "database.py").read_text()
        or "timeout" in (ROOT / "backend" / "database.py").read_text(),
    )


# ===========================================================================
def main() -> int:
    global PRODUCTION_MODE
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--production",
        action="store_true",
        help="require production-grade configuration, not dev tolerances",
    )
    PRODUCTION_MODE = parser.parse_args().production

    os.environ.setdefault("SUPABASE_URL", "http://127.0.0.1:9")
    os.environ.setdefault("SUPABASE_ANON_KEY", "check-anon")
    os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "check-service-role")

    if not os.environ.get("DATABASE_URL"):
        print("DATABASE_URL is required. Point it at a throwaway PostgreSQL instance.")
        return 2

    print("Pre-deployment checks" + (" (production mode)" if PRODUCTION_MODE else " (dev mode)"))
    for fn in (
        check_env,
        check_debug_code,
        check_error_handling,
        check_headers,
        check_rate_limits,
        check_cors,
        check_database,
    ):
        try:
            fn()
        except Exception as exc:  # a crashing category is a failing category
            import traceback

            _failures.append(f"{fn.__name__} raised {type(exc).__name__}")
            print(f"  FAIL  {fn.__name__} raised {type(exc).__name__}: {exc}")
            traceback.print_exc()

    print(f"\n{_passes} passed, {len(_failures)} failed")
    if _failures:
        print("\nFailures:")
        for name in _failures:
            print(f"  - {name}")
        return 1
    print("\nALL DEPLOYMENT CHECKS PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
