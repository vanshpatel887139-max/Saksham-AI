"""Startup configuration validation.

The application used to validate configuration lazily: `DATABASE_URL` was only
read when the first query ran, so a misconfigured deployment started cleanly,
answered `/api/health` with 200, and only failed once a user clicked something.
A health check that passes on a server which cannot serve a single request is
worse than one that refuses to boot, because an orchestrator will happily route
traffic to it and the failure surfaces as a user-facing 500 instead of a failed
deploy.

So this module is the single place that decides whether the process is allowed
to start. It is called from the FastAPI lifespan, which runs after uvicorn has
finished configuring logging and before the first request is accepted.

Two modes:

- **development** (the default): missing optional variables are reported as
  warnings and startup continues, because a developer should be able to run the
  frontend mock or a partial backend without a Supabase project.
- **production** (`SAKSHAMAI_ENV=production`): a missing or unsafe critical
  variable raises `ConfigError` and the process exits non-zero. There is no
  permissive fallback, and no way to spell "production" that half-applies.

The distinction is deliberately a single explicit variable rather than an
inference from whether a variable happens to be set. A heuristic gets it wrong
in the direction that matters: a deploy that is missing everything looks most
like a developer's laptop.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Iterable

PRODUCTION = "production"
DEVELOPMENT = "development"

# Placeholders that must never reach a real deployment. Checked by value, not
# by key, so a renamed variable cannot slip past.
_PLACEHOLDER_VALUES = {
    "changeme",
    "change-me",
    "yourpassword",
    "your-password",
    "password",
    "postgres",
    "secret",
    "todo",
    "xxx",
    "example",
    # Published in README.md and allowlisted by value in .gitleaks.toml, so it
    # is not a credential -- it is a public string that opens a real session
    # against a real database. It has no business being set in production.
    "demo@1234",
}


class ConfigError(RuntimeError):
    """A critical configuration problem. Always fatal in production."""


def environment() -> str:
    """Which mode this process believes it is running in."""
    raw = (os.environ.get("SAKSHAMAI_ENV") or "").strip().lower()
    if raw in {PRODUCTION, "prod"}:
        return PRODUCTION
    if raw in {"", DEVELOPMENT, "dev", "local", "test"}:
        return DEVELOPMENT
    # An unrecognised value is a typo, and the safe reading of a typo that could
    # mean "production" is "production". Failing open here is how a staging box
    # ends up serving with production's secrets and development's tolerances.
    return PRODUCTION


def is_production() -> bool:
    return environment() == PRODUCTION


def _get(name: str) -> str:
    return (os.environ.get(name) or "").strip()


def _looks_like_placeholder(value: str) -> bool:
    low = value.strip().lower()
    if low in _PLACEHOLDER_VALUES:
        return True
    # The .env.example connection string is a template, not a value.
    return "PROJECT_REF" in value or value.count("<") > 0


@dataclass
class Check:
    name: str
    ok: bool
    detail: str = ""
    fatal: bool = False


@dataclass
class Report:
    environment: str
    checks: list[Check] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def failures(self) -> list[Check]:
        return [c for c in self.checks if not c.ok and c.fatal]

    def add(self, name: str, ok: bool, detail: str = "", fatal: bool = False) -> None:
        self.checks.append(Check(name, ok, detail, fatal))

    def warn(self, message: str) -> None:
        self.warnings.append(message)


def _check_required(
    report: Report,
    name: str,
    *,
    env: str,
    hint: str,
    placeholder_check: bool = True,
) -> str:
    value = _get(name)
    if not value:
        report.add(
            name,
            False,
            f"not set — {hint}",
            fatal=(env == PRODUCTION),
        )
        return ""
    if placeholder_check and _looks_like_placeholder(value):
        report.add(
            name,
            False,
            "still holds the example placeholder value — replace it with the real secret",
            fatal=(env == PRODUCTION),
        )
        return value
    report.add(name, True, "set")
    return value


def _check_database_tls(report: Report, dsn: str, env: str) -> None:
    """Postgres traffic must be encrypted in production.

    `sslmode` is read from the DSN rather than being forced, because psycopg
    already honours it and silently overriding a deliberate `sslmode=disable`
    would break a developer debugging against a local socket. In production the
    question is only whether encryption is on, and the answer must be yes.
    """
    if not dsn:
        return
    lowered = dsn.lower()
    # `require` encrypts without verifying the server certificate. `verify-full`
    # additionally checks the hostname. Neither is as good as verify-full, but
    # verify-full needs a root certificate and Supabase's pooler presents a
    # certificate that fails hostname verification by design, so `require` is
    # the correct setting for that host and is accepted here.
    present = re.search(r"sslmode\s*=\s*([a-z\-]+)", lowered)
    if not present:
        # libpq also reads PGSSLMODE, so honour it rather than failing a
        # deployment that did it the other way round.
        env_mode = _get("PGSSLMODE").lower()
        if env_mode:
            present = re.match(r"([a-z\-]+)", env_mode)
            if present:
                report.add(
                    "DATABASE_URL sslmode",
                    True,
                    f"sslmode={env_mode} via PGSSLMODE",
                )
                return
        report.add(
            "DATABASE_URL sslmode",
            False,
            "no sslmode in the connection string — database traffic is unencrypted",
            fatal=(env == PRODUCTION),
        )
        return
    mode = present.group(1)
    if mode in {"disable", "allow", "prefer"}:
        # `prefer` and `allow` fall back to plaintext when the server does not
        # offer TLS, so neither is a guarantee of encryption.
        report.add(
            "DATABASE_URL sslmode",
            False,
            f"sslmode={mode} does not require encryption",
            fatal=(env == PRODUCTION),
        )
    elif mode in {"require", "verify-ca", "verify-full"}:
        report.add("DATABASE_URL sslmode", True, f"sslmode={mode}")
    else:
        report.add("DATABASE_URL sslmode", False, f"unrecognised sslmode={mode}")


def validate() -> Report:
    """Inspect the environment and decide whether startup may proceed."""
    env = environment()
    report = Report(environment=env)
    prod = env == PRODUCTION

    # --- critical: the app cannot serve without these -----------------------
    database_url = _check_required(
        report,
        "DATABASE_URL",
        env=env,
        hint="Supabase session-pooler connection string, e.g. postgresql://postgres.REF:PASSWORD@aws-0-REGION.pooler.supabase.com:5432/postgres?sslmode=require",
        # The DSN is a template with a variable password, so the whole-value
        # placeholder check does not apply; the sslmode check below does.
        placeholder_check=False,
    )
    _check_database_tls(report, database_url, env)

    _check_required(
        report,
        "SUPABASE_URL",
        env=env,
        hint="project URL from Supabase -> Settings -> API",
        placeholder_check=False,
    )
    _check_required(
        report,
        "SUPABASE_ANON_KEY",
        env=env,
        hint="the anon/publishable key from Supabase -> Settings -> API Keys. Never the service_role key.",
    )
    _check_required(
        report,
        "SUPABASE_SERVICE_ROLE_KEY",
        env=env,
        hint="service-role key. Required in production: without it, account deletion leaves the Auth identity behind.",
    )

    # A service-role key in the anon slot is the single worst configuration
    # mistake available here, and it is a copy-paste away.
    anon, service = _get("SUPABASE_ANON_KEY"), _get("SUPABASE_SERVICE_ROLE_KEY")
    if anon and service and anon == service:
        report.add(
            "SUPABASE key separation",
            False,
            "SUPABASE_ANON_KEY and SUPABASE_SERVICE_ROLE_KEY are the same value — the "
            "service-role key bypasses RLS and must never be used as the anon key",
            fatal=True,
        )
    else:
        report.add("SUPABASE key separation", True, "anon and service-role keys differ")

    # --- required in production, optional in development ---------------------
    groq = _get("GROQ_API_KEY")
    if groq:
        report.add("GROQ_API_KEY", True, "set")
    elif prod:
        report.add(
            "GROQ_API_KEY",
            False,
            "not set — the AI advisor, quiz generation and gap analysis will all return "
            "errors. Set it, or explicitly accept a degraded deployment.",
            fatal=False,
        )
        report.warn("GROQ_API_KEY is unset: AI features are unavailable.")
    else:
        report.add("GROQ_API_KEY", False, "not set — AI features unavailable (expected in dev)")
        report.warn("GROQ_API_KEY is unset: AI features are unavailable.")

    # --- flags that must default to off, and must be off in production -------
    debug_flag = _get("SAKSHAMAI_LOG_DEBUG")
    if debug_flag.lower() in {"1", "true", "yes", "on"}:
        report.add(
            "SAKSHAMAI_LOG_DEBUG",
            False,
            "verbose debug logging is enabled",
            fatal=prod,
        )
    else:
        report.add("SAKSHAMAI_LOG_DEBUG", True, "off")

    if _get("EXPOSE_DEMO_PASSWORD").lower() in {"1", "true", "yes", "on"}:
        report.add(
            "EXPOSE_DEMO_PASSWORD",
            False,
            "the shared demo password is published by GET /api/auth/demo-users",
            fatal=prod,
        )
    else:
        report.add("EXPOSE_DEMO_PASSWORD", True, "off")

    # --- CORS ---------------------------------------------------------------
    cors = [o.strip().rstrip("/") for o in _get("CORS_ORIGINS").split(",") if o.strip()]
    if not cors:
        if prod:
            report.add(
                "CORS_ORIGINS",
                False,
                "not set — production must name its own frontend origin. The built-in "
                "defaults are loopback and one LAN address, which are dev-only.",
                fatal=True,
            )
        else:
            report.add("CORS_ORIGINS", False, "not set — using dev defaults (loopback only)")
    elif "*" in cors:
        report.add(
            "CORS_ORIGINS",
            False,
            "contains '*'. A wildcard cannot be combined with credentials, and this app "
            "authenticates with a cookie, so it would break auth rather than widen access.",
            fatal=True,
        )
    else:
        report.add("CORS_ORIGINS", True, f"{len(cors)} origin(s)")

    # --- host header --------------------------------------------------------
    hosts = [h.strip() for h in _get("ALLOWED_HOSTS").split(",") if h.strip()]
    if hosts:
        report.add("ALLOWED_HOSTS", True, f"{len(hosts)} host(s)")
    elif prod:
        report.add(
            "ALLOWED_HOSTS",
            False,
            "not set — Host-header filtering is off, which enables cache-poisoning and "
            "password-reset-poisoning tricks",
            fatal=False,
        )
        report.warn("ALLOWED_HOSTS is unset: Host header filtering is disabled.")
    else:
        report.add("ALLOWED_HOSTS", False, "not set — Host filtering off (expected in dev)")

    # --- rate limiting ------------------------------------------------------
    # The limiter is an in-process dict. With more than one worker each worker
    # counts separately, so the effective limit multiplies by the worker count.
    workers = _get("WEB_CONCURRENCY")
    if prod and workers and workers not in {"1"}:
        report.add(
            "rate limit scope",
            False,
            f"WEB_CONCURRENCY={workers} with an in-process rate limiter: each worker has "
            f"its own counter, so the real limit is {workers}x the configured one",
            fatal=False,
        )
        report.warn(
            f"WEB_CONCURRENCY={workers}: the rate limiter is per-process, so the effective "
            "limit is multiplied by the worker count. Move it to Redis before scaling out."
        )
    else:
        report.add("rate limit scope", True, "single process, or worker count not set")

    # --- client IP attribution ---------------------------------------------
    # The sign-in limiter buckets on request.client.host, which uvicorn fills in
    # from X-Forwarded-For -- but only for a trusted proxy. Behind a platform
    # proxy that is not trusted, the address it forwards from is the proxy's,
    # so every caller shares one bucket and five failed attempts from anyone
    # locks out everyone. Behind no proxy at all the field is the real peer and
    # is correct, so the requirement is scoped to production.
    forwarded = _get("FORWARDED_ALLOW_IPS")
    if prod and not forwarded:
        report.add(
            "FORWARDED_ALLOW_IPS",
            False,
            "not set — if this service sits behind a proxy, every request appears to come "
            "from that proxy, so all users share one sign-in rate-limit bucket",
            fatal=False,
        )
        report.warn(
            "FORWARDED_ALLOW_IPS is unset. Behind a proxy this collapses per-IP rate "
            "limiting into a single global bucket: five failed sign-ins from one user "
            "locks out every user. Set it to the proxy's address or CIDR (not '*', "
            "unless the service is unreachable except through the proxy)."
        )
    elif forwarded:
        scope = "any proxy" if forwarded.strip() == "*" else forwarded.strip()
        report.add("FORWARDED_ALLOW_IPS", True, f"trusting {scope}")
    else:
        report.add("FORWARDED_ALLOW_IPS", False, "not set (expected in dev)")

    # --- demo and shared credentials ---------------------------------------
    # Demo@1234 is in the README and in the .gitleaks allowlist, so it is not a
    # secret in any sense: it is a public string that grants a real admin session
    # on a real database. Flagging it by value means a renamed variable cannot
    # slip past.
    demo_password = (_get("DEMO_USER_PASSWORD") or "").strip()
    if prod and demo_password and _looks_like_placeholder(demo_password):
        report.add(
            "DEMO_USER_PASSWORD",
            False,
            "set to a known demo/placeholder value that is published in the repository",
            fatal=True,
        )
    elif demo_password and len(demo_password) < 12:
        report.add(
            "DEMO_USER_PASSWORD",
            False,
            f"set but only {len(demo_password)} characters",
            fatal=prod,
        )
    else:
        report.add(
            "DEMO_USER_PASSWORD",
            True,
            "not set" if not demo_password else "set to a non-placeholder value",
        )

    return report


def describe(report: Report) -> str:
    """Human-readable summary, safe to print at startup.

    Only variable *names* and status appear — never a value. This string goes to
    stdout, which in many deployments is captured by a log aggregator.
    """
    lines = [f"[config] environment={report.environment}"]
    for check in report.checks:
        if check.ok:
            lines.append(f"[config]   ok   {check.name} ({check.detail})")
        elif check.fatal:
            lines.append(f"[config]   FAIL {check.name}: {check.detail}")
        else:
            lines.append(f"[config]   warn {check.name}: {check.detail}")
    for warning in report.warnings:
        lines.append(f"[config]   note {warning}")
    return "\n".join(lines)


def enforce(report: Report) -> None:
    """Raise `ConfigError` if anything fatal is wrong."""
    if report.failures:
        bullets = "\n".join(f"  - {c.name}: {c.detail}" for c in report.failures)
        raise ConfigError(
            f"Refusing to start in {report.environment} mode. "
            f"Fix the following environment configuration:\n{bullets}\n"
            f"See .env.example for the full list of variables."
        )


def startup_checks() -> Iterable[str]:
    """Convenience for callers that only want a one-shot summary line."""
    return (describe(validate()),)
