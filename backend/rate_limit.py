"""In-process rate limiting for credential endpoints.

Why this exists: `/api/auth/login` had no attempt limit, so the shared demo
password (and any future real one) could be guessed indefinitely at whatever
rate the network allowed.

Limits, per scope:

| scope             | default            | why                                  |
|-------------------|--------------------|--------------------------------------|
| `ip`              | 5 / 60s            | sign-in guessing from one host       |
| `email`           | 5 / 900s           | focused run against one account      |
| `password-reset`  | 3 / 3600s          | mail-sending abuse (no route yet)    |
| `otp`             | 3 / 3600s          | same (no route yet)                  |

Each scope is counted over its own window; they are deliberately not shared.

Other scope and limits, stated plainly:

- **Per process, in memory.** Two workers each keep their own counters, and
  everything resets on restart. That is fine for the single-process demo
  deployment this project targets. Behind multiple replicas or a load balancer,
  replace this with a shared store (Redis `INCR` + `EXPIRE`) or the effective
  limit becomes per-replica.
- **Fails open.** If the limiter itself raises, the request proceeds and the
  error is logged. A bug in throttling must not become an outage, and this is
  not the only control — the password itself is the real one.
- **Not a DoS defence.** It bounds guessing rate, not request volume.
"""

from __future__ import annotations

import os
import threading
import time
import logging
from collections import defaultdict, deque
from typing import Deque, Optional, Tuple
from log_safety import safe_exception

logger = logging.getLogger("sakshamai.ratelimit")

# A failed-attempt counter per (scope, key). Successful logins are not counted:
# the limiter exists to slow guessing, and a real user who signs in correctly
# 50 times is not an attacker.
_attempts: dict[Tuple[str, str], Deque[float]] = defaultdict(deque)
_lock = threading.Lock()

class Policy:
    """One throttle: a cap and the window it is counted over.

    Scopes carry their own window because the required limits are not the same
    shape. Sign-in guessing is bounded per minute, so a short window is correct
    — a 15-minute window with a cap of 20 permits 20 attempts in the first
    second, which is four times the intended per-minute ceiling and is what the
    previous single shared window actually allowed. Password reset is bounded
    per hour, because it sends email and an attacker cares about the send rate,
    not the second.
    """

    def __init__(self, env_prefix: str, window: float, cap: int) -> None:
        self.env_prefix = env_prefix
        self.default_window = window
        self.default_cap = cap

    @property
    def window(self) -> float:
        return max(1.0, _env_float(f"{self.env_prefix}_WINDOW_SECONDS", self.default_window))

    @property
    def cap(self) -> int:
        return max(1, _env_int(f"{self.env_prefix}_MAX", self.default_cap))


# 5 attempts per minute per IP, and 5 per 15 minutes per account so a focused
# run against one user from many hosts is still bounded.
POLICIES = {
    "ip": Policy("RATE_LIMIT_LOGIN_IP", 60.0, 5),
    "email": Policy("RATE_LIMIT_LOGIN_EMAIL", 900.0, 5),
    # Not wired to an endpoint today — there is no password-reset route. It is
    # defined so that adding one cannot start from a blank page: a new
    # credential endpoint calls check("password-reset", ...) and inherits
    # 3 per hour, which is the limit that matters for a mail-sending flow.
    "password-reset": Policy("RATE_LIMIT_PASSWORD_RESET", 3600.0, 3),
    "otp": Policy("RATE_LIMIT_OTP", 3600.0, 3),
}

DEFAULT_POLICY = "ip"


def policy_for(scope: str) -> Policy:
    return POLICIES.get(scope, POLICIES[DEFAULT_POLICY])


# Retained for the call sites and for backwards compatibility with the previous
# single-window interface.
def window_seconds(scope: str = "email") -> float:
    return policy_for(scope).window


def max_per_ip() -> int:
    return POLICIES["ip"].cap


def max_per_email() -> int:
    return POLICIES["email"].cap


def _env_float(name: str, default: float) -> float:
    try:
        return float((os.environ.get(name) or "").strip() or default)
    except (TypeError, ValueError):
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int((os.environ.get(name) or "").strip() or default)
    except (TypeError, ValueError):
        return default


def _prune(now: float) -> None:
    """Drop expired buckets so the dict cannot grow without bound.

    Each bucket is judged against its own scope's window. A single global prune
    window would evict a password-reset counter on a one-minute boundary, or
    keep a sign-in counter alive for an hour — both wrong, and the second one
    silently defeats the tighter limit.
    """
    for (scope, _), ts in list(_attempts.items()):
        window = policy_for(scope).window
        if not ts or now - ts[-1] > window:
            del _attempts[(scope, _)]


def record_failure(scope: str, key: str, now: Optional[float] = None) -> None:
    """Note one failed attempt against `scope`/`key`."""
    try:
        ts = now if now is not None else time.monotonic()
        with _lock:
            _prune(ts)
            _attempts[(scope, key)].append(ts)
    except Exception as exc:  # never let bookkeeping break a login
        logger.error("rate limit could not record a failure: %s", safe_exception(exc))


def remaining(scope: str, key: str) -> int:
    """How many more failures are allowed before the scope locks out."""
    try:
        now = time.monotonic()
        with _lock:
            _prune(now)
            used = len(_attempts.get((scope, key), ()))
        return max(0, policy_for(scope).cap - used)
    except Exception as exc:
        logger.error("rate limit could not be read: %s", safe_exception(exc))
        return policy_for(scope).cap


def retry_after_seconds(scope: str, key: str) -> int:
    """Seconds until the oldest failure ages out of the window (>= 1)."""
    try:
        now = time.monotonic()
        with _lock:
            bucket = _attempts.get((scope, key))
            if not bucket:
                return 1
            window = policy_for(scope).window
            return max(1, int(window - (now - bucket[0])) + 1)
    except Exception:
        return int(policy_for(scope).window) + 1


def reset() -> None:
    """Clear all counters. For tests."""
    with _lock:
        _attempts.clear()
