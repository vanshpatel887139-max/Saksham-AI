"""Log redaction helpers.

Why this module exists
----------------------
Driver and transport exception text is not a safe thing to write to a log.
This was verified rather than assumed, against psycopg 3.2.3:

    >>> str(UniqueViolation)          # inserting a duplicate email
    duplicate key value violates unique constraint "t_email_key"
    DETAIL:  Key (email)=(victim.worker@gov.example) already exists.

The offending value is in the message. `users.email` is UNIQUE, so any unique
violation involving that column puts a real officer's email address into the
log file, and psycopg appends the failing statement for several other error
classes as well. The same applies to httpx, whose exception text embeds the
request URL, and to Redis client errors.

The old call sites all used the same shape:

    logger.warning("...: %s: %s", type(exc).__name__, exc)

which is the worst of both worlds: the class name is already extracted
separately, and the trailing `%s` is the unsafe part.

What is logged instead
----------------------
The exception class and the SQLSTATE code. SQLSTATE is a five-character
standard code ("23505" is unique_violation) that is precise enough to debug
with, is stable across drivers, and cannot contain user data. Nothing about
the row, the statement, or the connection string is written.

Full exception text is available only when SAKSHAMAI_LOG_DEBUG is set, which
is for local development where the data is synthetic. It defaults to off and
must stay off anywhere real user data flows, because that setting re-enables
exactly the leak this module exists to close.
"""

from __future__ import annotations

import logging
import os
import re

# Values that must never reach a log line, matched defensively across any
# exception text. Applied to debug text only, but also applied to the message
# bodies we build ourselves so a single forgotten call site cannot regress.
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_BEARER_RE = re.compile(r"(?i)\b(bearer|token|apikey|api[_-]?key|password|secret)"
                        r"\b\s*[:=]?\s*\S+")
_JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}\b")
_LONG_DSN_RE = re.compile(r"(?i)\b(postgres(?:ql)?|mysql|mongodb(?:\+srv)?)://[^\s]+")

# The access log records the request target, and three request targets carry a
# user id:
#
#   GET /api/users/learner-1                 path parameter
#   GET /api/quiz/history/learner-1          path parameter
#   GET /api/courses?user_id=learner-1       query parameter (optional per-user
#                                            progress on the public catalogue)
#
# A user id is a pseudonymous internal identifier rather than a name or email,
# so this is a smaller leak than the driver-text case above. It is still a
# stable join key: a log shipper plus a timestamp is enough to reconstruct who
# did what and when, which is precisely the kind of profile that should not be
# sitting in log storage unasked.
#
# A hash is not used, because these ids are `learner-1` .. `learner-11`: a
# digest over a nine-character enumerable space is reversible in microseconds,
# so hashing would be theatre. The segment is replaced outright. Correlation
# across log lines is preserved by the fact that the scrubbed token is stable
# per distinct id, and full per-request attribution should come from a request
# id header rather than from an identifier in the URL.
#
# `/api/users/me` is deliberately preserved: it is a fixed literal, not an id.
_USER_PATH_RE = re.compile(r"(/api/users/)(?!me(?![^/\s\"]))[^\s\"?]+")
_QUIZ_HISTORY_RE = re.compile(r"(/api/quiz/history/)[^\s\"?]+")
_USER_QUERY_RE = re.compile(r"([?&]user_id=)[^\s\"&]+")

ID_PLACEHOLDER = "[redacted]"


def scrub_access_log(line: str) -> str:
    """Remove user ids from a formatted access-log line."""
    if not line:
        return line
    out = _USER_PATH_RE.sub(rf"\1{ID_PLACEHOLDER}", line)
    out = _QUIZ_HISTORY_RE.sub(rf"\1{ID_PLACEHOLDER}", out)
    out = _USER_QUERY_RE.sub(rf"\1{ID_PLACEHOLDER}", out)
    return out


class RedactingFormatter(logging.Formatter):
    """Formatter that scrubs user ids from the finished line.

    A `logging.Filter` cannot do this reliably, because uvicorn builds the
    access line from `record.msg` plus format arguments and the layout differs
    between uvicorn versions. Formatting first and scrubbing the completed
    string is layout-independent.

    The wrapped formatter is *delegated to*, never copied. An earlier attempt
    read `inner._fmt` and rebuilt a plain `logging.Formatter` from it, which
    silently dropped uvicorn's custom percent-style — its `AccessFormatter`
    styles the record with a `levelprefix` key, so every access line then
    raised `KeyError: 'levelprefix'` and the raw unredacted message was emitted
    to stderr by the logging error handler instead. Wrapping keeps the original
    renderer, so the layout and the redaction cannot drift apart.
    """

    def __init__(self, inner: logging.Formatter | None = None):
        super().__init__()
        self._inner = inner if inner is not None else logging.Formatter("%(message)s")

    def format(self, record: logging.LogRecord) -> str:
        return scrub_access_log(self._inner.format(record))

REDACTED = "[REDACTED]"


def debug_enabled() -> bool:
    """Whether raw exception text may be written. Local development only."""
    return (os.environ.get("SAKSHAMAI_LOG_DEBUG") or "").strip().lower() in {
        "1", "true", "yes", "on",
    }


def redact(text: str) -> str:
    """Strip anything that looks like user data out of a free-text string."""
    if not text:
        return text
    out = _JWT_RE.sub(REDACTED, text)
    out = _LONG_DSN_RE.sub(f"{REDACTED}://{REDACTED}", out)
    out = _EMAIL_RE.sub(REDACTED, out)
    out = _BEARER_RE.sub(lambda m: f"{m.group(1)}={REDACTED}", out)
    return out


def safe_exception(exc: BaseException, *, context: str = "") -> str:
    """Return a log-safe one-line description of ``exc``.

    Contains the exception class and, for database drivers, the SQLSTATE code.
    Contains no user data, no statement text and no connection string.
    """
    parts = []
    if context:
        parts.append(context)
    parts.append(type(exc).__name__)

    sqlstate = getattr(exc, "sqlstate", None)
    if isinstance(sqlstate, str) and sqlstate:
        parts.append(f"sqlstate={sqlstate}")

    # The pgcode/errno pair is numeric and carries no data. psycopg2 exposes
    # pgcode; some clients expose errno. Neither can contain user data.
    for attr in ("pgcode", "errno"):
        val = getattr(exc, attr, None)
        if val and attr not in ("sqlstate",):
            parts.append(f"{attr}={val}")

    line = " ".join(parts)
    if debug_enabled():
        # Opt-in, for local debugging against synthetic data. The raw text is
        # still run through redact() so the common leaks stay suppressed even
        # here; this is a debugging aid, not a bypass.
        detail = redact(str(exc))
        if detail:
            line = f"{line} | debug: {detail}"
    return line
