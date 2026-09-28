"""SakshamAI FastAPI backend entrypoint.

Run:
    uvicorn main:app --reload --port 8000

This starts an API on http://localhost:8000 with CORS enabled for the
Vite frontend running on http://localhost:3000.
"""

from contextlib import asynccontextmanager
import logging
import os
import re
import uuid
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

import deploy_config
import security_headers
from database import close_pool, healthcheck, init_db
from auth_tokens import SESSION_COOKIE
from log_safety import RedactingFormatter, scrub_access_log, debug_enabled, redact
from routers import auth, users, competency, courses, quiz, admin, assistant, labs, igot, assessment, stats, dashboard

logger = logging.getLogger("sakshamai.api")


def _redacted_target(request: Request) -> str:
    """The request target, with user ids removed, for log lines.

    Reuses the same scrubber as the access log so an error log and an access
    line cannot disagree about what the target was.
    """
    return scrub_access_log(request.url.path)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Refuse to start on a broken configuration. This runs before the pool is
    # warmed and before any request is accepted, so a bad deploy fails here
    # rather than answering /api/health with 200 and then 500ing on real traffic.
    report = deploy_config.validate()
    print(deploy_config.describe(report))
    deploy_config.enforce(report)
    # Apply any pending migrations and seed rows, then warm the pool.
    init_db()
    # Re-assert access-log redaction at startup. The module-level call below
    # already did this, but uvicorn owns the `uvicorn.access` logger and the
    # order of its logging setup versus the app import is version-dependent.
    # Startup is unambiguously after both, and the function is idempotent.
    _install_access_log_redaction()
    yield
    # Release Postgres connections on shutdown instead of leaving the process
    # to be reaped; uvicorn --reload restarts this often enough to matter.
    close_pool()



# The interactive docs execute an inline bootstrap script and are therefore
# incompatible with the production CSP (script-src 'self', no 'unsafe-inline').
# Rather than weaken the policy for the whole API to accommodate a developer
# page, production drops the docs surface: /docs, /redoc and /openapi.json are
# not served. That also means production publishes no schema, which is a small
# information-disclosure win on its own.
#
# Read at import time, which is why it works at all: this is the one setting
# that has to be decided when the app object is built, before startup validation
# runs. An unrecognised SAKSHAMAI_ENV counts as production (deploy_config
# treats unknown values as production), so a typo here fails closed and takes
# the docs with it.
_PRODUCTION_MODE = deploy_config.environment() == "production"

app = FastAPI(
    title="SakshamAI API",
    version="0.1.0",
    description="Skill Intelligence Platform for Official Statistics — SIH demo backend",
    lifespan=lifespan,
    docs_url=None if _PRODUCTION_MODE else "/docs",
    redoc_url=None if _PRODUCTION_MODE else "/redoc",
    openapi_url=None if _PRODUCTION_MODE else "/openapi.json",
)

# CORS: the Vite dev server and preview by default, plus any extra origins the
# deployment needs. The LAN address is dev-only and is harmless to keep because
# these are all plain-http loopback/private origins; a real deployment should
# list its own public origin in CORS_ORIGINS instead of relying on the defaults.
#
# In production the defaults are refused outright by deploy_config, so reaching
# this point with an unset CORS_ORIGINS means development. That is what keeps
# the LAN entry from silently becoming a production cross-origin allowance.
_allowed = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://192.168.11.23:3000",
    "http://localhost:4173",
]
_allowed += [
    origin.strip().rstrip("/")
    for origin in (os.environ.get("CORS_ORIGINS") or "").split(",")
    if origin.strip()
]
# A wildcard is never valid here: the session is a cookie, and a credentialed
# CORS response cannot legally carry `Access-Control-Allow-Origin: *`. Some
# clients will "helpfully" reflect the caller's Origin instead, which turns the
# wildcard into an open CORS policy with credentials attached. Refuse it at
# startup rather than relying on the client behaving.
_allowed = [o for o in _allowed if o != "*"]
if "*" in [o.strip().rstrip("/") for o in (os.environ.get("CORS_ORIGINS") or "").split(",")]:
    logger.error("CORS_ORIGINS contains '*', which is dropped: credentialed CORS cannot use a wildcard")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed,
    allow_credentials=True,
    # Named explicitly rather than "*". A preflight that advertises every method
    # and header tells a caller more about this API than it needs to know.
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID", "Retry-After"],
    max_age=600,
)

# Host header filtering. Without it, a request carrying a forged Host is used
# verbatim in redirects and in any absolute URL the app builds, which is the
# basis of password-reset-poisoning and cache-poisoning tricks. Only enabled
# when ALLOWED_HOSTS is set, so local development is unaffected; put your real
# domain in it for any deployment. See the TLS note in the README — filtering
# Host is not a substitute for terminating TLS.
_allowed_hosts = [
    h.strip()
    for h in (os.environ.get("ALLOWED_HOSTS") or "").split(",")
    if h.strip()
]
if _allowed_hosts:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=_allowed_hosts)
    print(f"[main] Host header restricted to {len(_allowed_hosts)} entr(y/ies)")


# CSRF defence for cookie-authenticated requests.
#
# Moving the session token into a cookie fixes the XSS-exfiltration half of the
# problem, but a cookie is an ambient credential: the browser attaches it to
# any request to this origin, including one a third-party page triggered. That
# is the CSRF half, and it needs answering.
#
# `SameSite=strict` on the cookie is the primary control. This Origin check is
# the second, for the cases SameSite does not cover (a compromised or
# attacker-controlled sibling subdomain, which is same-site, and older clients).
# Only requests whose credential came from the *cookie* are checked: a caller
# that sets an Authorization header is not subject to ambient-credential
# forgery, because the page cannot attach that header cross-origin without
# CORS approval. So curl, the seed scripts, and any future non-browser client
# keep working with no change and no special-casing.
_UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

# Body-size caps. Uploads are already bounded by the quiz route's chunked
# 20 MiB read, but every other endpoint accepts JSON and Starlette will happily
# buffer an unbounded request body into memory before any validation runs —
# a cheap memory-exhaustion DoS against a public endpoint such as
# /api/auth/login. The Content-Length header is checked first (browsers, curl
# and TestClient all set it); for a body without one we read it ourselves in
# chunks so the cap is enforced against the streamed size, not after the fact.
MAX_JSON_BODY_BYTES = 2 * 1024 * 1024
MAX_MULTIPART_BODY_BYTES = 25 * 1024 * 1024  # 20 MiB file cap + form overhead


@app.middleware("http")
async def csrf_origin_guard(request: Request, call_next):
    if request.method in _UNSAFE_METHODS and "authorization" not in request.headers:
        if SESSION_COOKIE in request.cookies:
            origin = request.headers.get("origin")
            # A missing Origin on a state-changing cookie-authenticated request
            # is not a browser being terse — browsers send it on every such
            # request. Its absence means something other than the app's own page
            # made this call, so it is refused rather than allowed as a
            # convenient default.
            if origin is None or origin.rstrip("/") not in _allowed:
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={"detail": "Cross-origin request refused."},
                )
    return await call_next(request)


async def _read_capped_body(request: Request, cap: int) -> Optional[bytes]:
    """Read the request body, stopping the moment it exceeds `cap`.

    Returns None when the body is too large (or unreadable), so the caller can
    answer 413 before the whole thing is buffered. On success the bytes are
    cached onto the request so FastAPI's own `request.body()` / `request.json()`
    reuse them instead of trying to re-read an already-consumed stream.
    """
    chunks = []
    total = 0
    try:
        async for chunk in request.stream():
            total += len(chunk)
            if total > cap:
                return None
            chunks.append(chunk)
    except Exception:
        return None
    return b"".join(chunks)


def _payload_too_large(request: Request) -> JSONResponse:
    return _error_response(
        request, status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, {"detail": "Request body too large."}
    )


@app.middleware("http")
async def body_size_guard(request: Request, call_next):
    if request.method not in _UNSAFE_METHODS:
        return await call_next(request)
    content_type = request.headers.get("content-type", "")
    multipart = content_type.startswith("multipart/form-data")
    cap = MAX_MULTIPART_BODY_BYTES if multipart else MAX_JSON_BODY_BYTES

    length = request.headers.get("content-length")
    if length is not None:
        if not length.isdigit():
            return _error_response(
                request, status.HTTP_400_BAD_REQUEST, {"detail": "Invalid Content-Length."}
            )
        if int(length) > cap:
            return _payload_too_large(request)

    if not multipart:
        body = await _read_capped_body(request, cap)
        if body is None:
            return _payload_too_large(request)
        request._body = body
    return await call_next(request)
#
# Every response carries a correlation id, and every log line for that request
# carries the same one. Without it, the only way to tie a user's "it failed"
# report to a server-side traceback is a timestamp match, which is unreliable
# precisely when it is needed — during an incident, when several requests a
# second are failing.
#
# The id is accepted from an inbound `X-Request-ID` so a trace can span services,
# but only after being reduced to a safe character set. Echoing an attacker-
# supplied value into a response header and into log files without that is a
# log-injection and header-injection primitive, and a long value is a cheap way
# to bloat the log store.
# --------------------------------------------------------------------------

_REQUEST_ID_RE = re.compile(r"[^A-Za-z0-9._-]")
_CORRELATION_HEADER = "X-Request-ID"


def _correlation_id(raw: str | None) -> str:
    if raw:
        cleaned = _REQUEST_ID_RE.sub("", raw)[:64]
        if cleaned:
            return cleaned
    return uuid.uuid4().hex


@app.middleware("http")
async def correlation_and_security_headers(request: Request, call_next):
    request.state.correlation_id = _correlation_id(request.headers.get(_CORRELATION_HEADER))
    response = await call_next(request)
    _apply_security_headers(response, request)
    return response


def _apply_security_headers(response, request: Request) -> None:
    """Stamp the correlation id and the header set onto a response, in place.

    Called from two places on purpose. The middleware covers the normal path,
    but `ServerErrorMiddleware` sits *outside* every `@app.middleware` layer, so
    a response produced by an exception handler never travels back out through
    them. Without this second call an error response — the one an attacker
    triggers on purpose, and the one most likely to be screenshotted — would be
    the only response in the app with no `nosniff` and no `X-Frame-Options`.
    """
    response.headers[_CORRELATION_HEADER] = getattr(
        request.state, "correlation_id", "unknown"
    )
    for key, value in security_headers.security_headers(
        csp=security_headers.csp_for_api(),
        hsts=security_headers.should_send_hsts(request.headers.get("host", "")),
    ).items():
        response.headers.setdefault(key, value)


def _error_response(
    request: Request,
    status_code: int,
    payload: dict,
    headers: dict | None = None,
) -> JSONResponse:
    """Build an error response with the full header set already applied."""
    response = JSONResponse(status_code=status_code, content=payload, headers=headers)
    _apply_security_headers(response, request)
    return response


def _client_message(exc: Exception) -> str:
    """The only text an unexpected failure is allowed to show a caller.

    Deliberately constant. Anything shaped like an explanation invites someone
    to paste it into a public issue, and a stack trace names modules, file
    paths, line numbers and — via the DSN in a connection error — the database
    host and the fact that a password was involved.
    """
    return "An internal error occurred. Quote the reference below when reporting it."


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Contain anything that escaped a route.

    Registered for bare `Exception`, which makes it the last handler in the
    chain: HTTPException and the validation handler registered below are more
    specific and still take precedence.
    """
    correlation_id = getattr(request.state, "correlation_id", "unknown")
    # Class name plus a *redacted* message to the log. A full traceback is
    # useful locally, but the exception value can carry user data — a psycopg
    # unique-violation message embeds the offending value, for example — so the
    # raw traceback is only written when SAKSHAMAI_LOG_DEBUG is on (a
    # developer-only flag, matching log_safety.debug_enabled()).
    if debug_enabled():
        logger.error(
            "unhandled error correlation_id=%s %s %s",
            correlation_id,
            request.method,
            _redacted_target(request),
            exc_info=exc,
        )
    else:
        logger.error(
            "unhandled error correlation_id=%s %s %s exc=%s: %s",
            correlation_id,
            request.method,
            _redacted_target(request),
            type(exc).__name__,
            redact(str(exc)),
        )
    if isinstance(exc, HTTPException):
        return _error_response(
            request,
            exc.status_code,
            {"detail": exc.detail, "correlation_id": correlation_id},
            headers=getattr(exc, "headers", None),
        )
    return _error_response(
        request,
        500,
        {"detail": _client_message(exc), "correlation_id": correlation_id},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Return a shape description, never the submitted values.

    FastAPI's default 422 embeds pydantic's `input` for each error, which
    reflects the *rejected value* straight back to the caller and into the
    access log. For a login request that means a mistyped field echoes the
    submitted email, and a body that fails validation after a password is
    present can echo the password too — into the response, and into any log
    collector that keeps request bodies. The field name and the reason are
    enough for a client to render a useful message.
    """
    correlation_id = getattr(request.state, "correlation_id", "unknown")
    fields = []
    for error in exc.errors():
        location = [str(p) for p in error.get("loc", ()) if p != "body"]
        fields.append(
            {
                "field": ".".join(location) or "body",
                "problem": error.get("msg", "invalid value"),
                "type": error.get("type", "value_error"),
            }
        )
    logger.info(
        "validation error correlation_id=%s %s %s fields=%s",
        correlation_id,
        request.method,
        _redacted_target(request),
        ",".join(f["field"] for f in fields) or "-",
    )
    return _error_response(
        request,
        422,
        {
            "detail": "One or more fields are invalid.",
            "correlation_id": correlation_id,
            "fields": fields,
        },
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Add the correlation id to framework-generated errors too.

    404s and 405s from the router have no id of their own, and those are exactly
    the responses someone will screenshot when asking why an endpoint is
    "missing".
    """
    correlation_id = getattr(request.state, "correlation_id", "unknown")
    return _error_response(
        request,
        exc.status_code,
        {"detail": exc.detail, "correlation_id": correlation_id},
        headers=getattr(exc, "headers", None),
    )



def _install_access_log_redaction() -> None:
    """Strip user ids out of uvicorn's access log.

    Three request targets embed a user id: `/api/users/{id}`,
    `/api/quiz/history/{id}` and `/api/courses?user_id={id}`. uvicorn logs the
    full request line, so without this the access log holds a stable join key
    for every action any user took. A `logging.Filter` cannot scrub this
    reliably because uvicorn composes the line from format arguments whose
    layout differs by version; a Formatter runs after rendering, so it sees the
    finished string and cannot be bypassed by an argument we do not know about.

    Applied here rather than relying on the app's own logging config, because
    `uvicorn.access` is configured by the server, not by FastAPI. Idempotent,
    so a reload does not stack formatters. Set ACCESS_LOG_REDACT=false to keep
    raw ids, which is occasionally wanted when debugging a single user.
    """
    if (os.environ.get("ACCESS_LOG_REDACT") or "true").strip().lower() in {
        "0", "false", "no", "off",
    }:
        return
    access = logging.getLogger("uvicorn.access")
    for handler in access.handlers:
        if isinstance(handler.formatter, RedactingFormatter):
            return
        # Wrap the server's own formatter rather than rebuilding one from its
        # _fmt string: uvicorn's AccessFormatter uses a custom percent-style
        # that supplies keys like `levelprefix`, so re-creating a plain
        # Formatter with the same format string breaks rendering and the raw
        # message escapes unredacted via the logging error handler.
        handler.setFormatter(RedactingFormatter(handler.formatter))
    if not access.handlers:
        # No server-managed handler yet (e.g. tests importing the app directly).
        # Add one so the guarantee holds regardless of who configures logging.
        handler = logging.StreamHandler()
        handler.setFormatter(RedactingFormatter())
        access.addHandler(handler)
    access.propagate = False


_install_access_log_redaction()

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(competency.router)
app.include_router(courses.router)
app.include_router(quiz.router)
app.include_router(admin.router)
app.include_router(assistant.router)
app.include_router(labs.router)
app.include_router(stats.router)
app.include_router(igot.router)
app.include_router(assessment.router)
app.include_router(dashboard.router)


@app.get("/api/health")
def health():
    """Liveness plus a real database round trip.

    Previously this returned a hardcoded ok without touching the database, so
    it reported healthy while every real endpoint was failing. It now surfaces
    the actual cause, because the most common cause for a Supabase project is
    not a bug: free projects are paused after a period of inactivity and start
    rejecting connections for up to ~24 hours while they restart.
    """
    result = healthcheck()
    status_code = 200 if result["status"] == "ok" else 503
    return JSONResponse(status_code=status_code, content=result)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)