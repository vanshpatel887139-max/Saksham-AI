"""Supabase Auth integration and the API's access-control boundary.

Why this exists: the previous implementation minted `demo-token-{user_id}` and
never checked it, and `POST /api/auth/login` took a `role` straight from the
request body — so anyone could promote themselves to admin with a single curl.
This module replaces both with a real credential check.

How verification works
---------------------
Supabase issues a JWT on sign-in. Rather than verify its signature locally
(which would mean shipping the project JWT secret into the API), the token is
validated against Supabase's own `/auth/v1/user` endpoint. One small round
trip per request, and it is authoritative: expired, revoked and forged tokens
all fail the same way.

Why enforcement lives here rather than in Postgres RLS
------------------------------------------------------
The backend connects directly with psycopg, and `auth.uid()` only resolves when
Supabase's PostgREST layer injects the JWT claims into the Postgres session. A
direct connection has no such session variable, so every per-user RLS policy
would deny all rows. RLS is written and enabled (supabase/migrations/002_rls.sql)
as the safety net for the day a frontend holds the anon key, but FastAPI is
what actually decides today. See that file for the full reasoning.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any, Optional

import httpx
from fastapi import Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from database import get_db_connection
from log_safety import safe_exception

# Transport failures are logged, never returned. httpx exception text embeds
# the request URL, which contains the Supabase project ref — infrastructure
# detail an anonymous caller has no business learning from a 503 body.
logger = logging.getLogger("sakshamai.auth")

bearer = HTTPBearer(auto_error=False)

SESSION_COOKIE = "sakshamai_session"
REFRESH_COOKIE = "sakshamai_refresh"

# Supabase's default access-token lifetime is one hour, and the session cookie
# is minted to match it. Without a refresh path that means a signed-in user is
# ejected at the sixty-minute mark with no warning and no way to stay signed in,
# which is unacceptable for a demo that runs longer than a lecture period. The
# refresh token is kept in its own cookie rather than returned in the body, so
# the "nothing here is readable by script" property survives.
REFRESH_COOKIE_MAX_AGE = 60 * 60 * 24 * 7  # one week

AUTH_CACHE_TTL = 30.0
_auth_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_cache_lock = threading.Lock()


def cookie_secure(request: Request) -> bool:
    """Whether the session cookie should carry the `Secure` attribute.

    A `Secure` cookie is silently dropped by the browser over plain HTTP, so
    guessing wrong in one direction logs every user out on the next request
    while guessing wrong in the other ships a session cookie in cleartext. The
    only host that is knowingly served over plain HTTP here is loopback, which
    is not a network exposure, so that is the single exception; anything else is
    required to be HTTPS. `COOKIE_SECURE` overrides for a deployment that
    terminates TLS somewhere unusual.
    """
    forced = (os.environ.get("COOKIE_SECURE") or "").strip()
    if forced:
        return forced.lower() in {"1", "true", "yes", "on"}
    host = (request.headers.get("host") or "").split(":")[0].strip("[]")
    return host not in {"localhost", "127.0.0.1", "::1"}


def set_session_cookie(response: Response, request: Request, token: str, max_age: int) -> None:
    """Attach the access token as a cookie that script cannot read.

    `httpOnly` is the point: the token is no longer reachable from injected
    script, so an XSS can no longer exfiltrate a session. `SameSite=strict`
    means the browser also withholds it from cross-site requests, which is what
    stops the cookie from becoming a CSRF vector. The Origin check in
    `main.py` is the belt to that pair of braces.
    """
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=max_age,
        httponly=True,
        secure=cookie_secure(request),
        samesite="strict",
        path="/",
    )


def clear_session_cookie(response: Response, request: Request) -> None:
    response.delete_cookie(
        SESSION_COOKIE,
        path="/",
        httponly=True,
        secure=cookie_secure(request),
        samesite="strict",
    )


def set_refresh_cookie(response: Response, request: Request, token: str) -> None:
    """Attach the refresh token, with the same protections as the access token.

    `httpOnly` and `SameSite=strict` for the same reasons as the access cookie:
    script must not be able to read it, and the browser must not attach it to a
    cross-site request. It outlives the access token deliberately -- that is the
    entire point of holding one.
    """
    response.set_cookie(
        REFRESH_COOKIE,
        token,
        max_age=REFRESH_COOKIE_MAX_AGE,
        httponly=True,
        secure=cookie_secure(request),
        samesite="strict",
        path="/",
    )


def clear_refresh_cookie(response: Response, request: Request) -> None:
    response.delete_cookie(
        REFRESH_COOKIE,
        path="/",
        httponly=True,
        secure=cookie_secure(request),
        samesite="strict",
    )


def set_session_cookies(response: Response, request: Request, session: dict[str, Any]) -> None:
    """Attach both halves of a Supabase session from one dict.

    The access cookie's lifetime is taken from the session itself rather than
    assumed, so the cookie never outlives the credential it carries. The
    refresh cookie is only set when Supabase actually returned one, which keeps
    a provider that stops issuing refresh tokens from silently leaving a stale
    cookie behind.
    """
    access_token = session.get("access_token")
    if not access_token:
        raise HTTPException(status_code=502, detail="Supabase returned no access token")
    set_session_cookie(
        response, request, access_token, int(session.get("expires_in") or 3600)
    )
    refresh_token = session.get("refresh_token")
    if refresh_token:
        set_refresh_cookie(response, request, refresh_token)


def clear_session_cookies(response: Response, request: Request) -> None:
    """Drop both session cookies. A logout must not leave a refresh token behind."""
    clear_session_cookie(response, request)
    clear_refresh_cookie(response, request)


class AuthMisconfigured(RuntimeError):
    """SUPABASE_URL / SUPABASE_ANON_KEY missing."""


def supabase_url() -> str:
    url = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
    if not url:
        raise AuthMisconfigured(
            "SUPABASE_URL is not set. Copy .env.example to backend/.env and fill in "
            "your project URL (Settings -> API)."
        )
    return url


def anon_key() -> str:
    key = (os.environ.get("SUPABASE_ANON_KEY") or "").strip()
    if not key:
        raise AuthMisconfigured(
            "SUPABASE_ANON_KEY is not set. Use the anon/publishable key from "
            "Settings -> API Keys. Never put the service_role key here."
        )
    return key


def sign_in(email: str, password: str) -> dict[str, Any]:
    """Exchange credentials for a Supabase access token.

    Raises HTTPException 401 on bad credentials. A 400 from Supabase means the
    account does not exist, which we deliberately report the same way as a
    wrong password so the endpoint is not an account-existence oracle.
    """
    try:
        response = httpx.post(
            f"{supabase_url()}/auth/v1/token?grant_type=password",
            json={"email": email, "password": password},
            headers={"apikey": anon_key(), "Content-Type": "application/json"},
            timeout=10.0,
        )
    except AuthMisconfigured:
        raise
    except httpx.HTTPError as exc:
        logger.warning("%s", safe_exception(exc, context="supabase auth unreachable"))
        raise HTTPException(
            status_code=503,
            detail="Could not reach Supabase Auth.",
        ) from exc

    if response.status_code >= 400:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return response.json()


def refresh_session(refresh_token: str) -> dict[str, Any]:
    """Exchange a refresh token for a fresh session.

    Supabase *rotates* the refresh token on every exchange, so the caller must
    persist whatever comes back rather than re-using the one it sent; re-using a
    rotated token fails the next time with a 400. A 400/401 here means the
    session is genuinely gone -- expired, revoked, or signed out -- and the
    caller should re-authenticate rather than retry.
    """
    try:
        response = httpx.post(
            f"{supabase_url()}/auth/v1/token?grant_type=refresh_token",
            json={"refresh_token": refresh_token},
            headers={"apikey": anon_key(), "Content-Type": "application/json"},
            timeout=10.0,
        )
    except AuthMisconfigured:
        raise
    except httpx.HTTPError as exc:
        logger.warning("%s", safe_exception(exc, context="supabase refresh unreachable"))
        raise HTTPException(
            status_code=503, detail="Could not reach Supabase Auth."
        ) from exc

    if response.status_code in (400, 401, 403):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your session has expired. Please sign in again.",
        )
    if response.status_code >= 400:
        raise HTTPException(status_code=503, detail="Could not refresh session")
    return response.json()


def revoke_session(access_token: Optional[str], refresh_token: Optional[str]) -> None:
    """Revoke the Supabase session server-side. Best effort, never raises.

    Without this, "sign out" only removes the cookie: the access token stays
    cryptographically valid until it expires and the refresh token stays usable
    for a week, so a token captured earlier keeps working. GoTrue's
    `scope=local` revokes just this session rather than every session the user
    has, which is the behaviour a sign-out button is expected to have.

    Failure here is deliberately not surfaced. The cookies are cleared either
    way, so the caller's own browser is clean; an inability to reach Supabase
    leaves a credential valid until it expires on its own, and turning that into
    a 500 would mean telling a user who asked to sign out that they are still
    signed in.
    """
    token = access_token or refresh_token
    if not token:
        return
    try:
        httpx.post(
            f"{supabase_url()}/auth/v1/logout",
            json={"scope": "local"},
            headers={
                "apikey": anon_key(),
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            timeout=10.0,
        )
    except (AuthMisconfigured, httpx.HTTPError) as exc:
        logger.warning(
            "%s", safe_exception(exc, context="session revoke failed (cookies still cleared)")
        )


def verify_access_token(token: str) -> dict[str, Any]:
    """Return the Supabase identity behind an access token, or raise 401."""
    try:
        response = httpx.get(
            f"{supabase_url()}/auth/v1/user",
            headers={"apikey": anon_key(), "Authorization": f"Bearer {token}"},
            timeout=10.0,
        )
    except AuthMisconfigured:
        raise
    except httpx.HTTPError as exc:
        logger.warning("%s", safe_exception(exc, context="token verification transport failure"))
        raise HTTPException(
            status_code=503, detail="Could not verify token."
        ) from exc

    if response.status_code in (401, 403):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session. Please sign in again.",
        )
    if response.status_code >= 400:
        raise HTTPException(status_code=503, detail="Could not verify session")
    return response.json()


def service_role_key() -> str:
    """Read the service_role key for the Supabase admin API.

    Needed for exactly one operation: deleting an Auth account when a user
    requests erasure. The key bypasses RLS and row-level security entirely, so
    it is read here, on the server, and never returned, logged, or accepted
    from a request. If it is absent, account deletion still completes for all
    data held in this application's own database, and the caller is told the
    Auth identity could not be removed so an operator can finish it.
    """
    key = (os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
    if not key:
        raise AuthMisconfigured(
            "SUPABASE_SERVICE_ROLE_KEY is not set. Account deletion can still "
            "remove all application data, but the Supabase Auth identity must "
            "be deleted manually (Supabase dashboard -> Authentication -> Users)."
        )
    return key


def delete_auth_account(auth_id: str) -> tuple[bool, str]:
    """Delete a Supabase Auth user by uuid.

    Returns ``(ok, reason)``. ``reason`` is a short machine-readable string,
    never exception text, because this value can reach an API response.
    """
    try:
        response = httpx.delete(
            f"{supabase_url()}/auth/v1/admin/users/{auth_id}",
            headers={
                "apikey": service_role_key(),
                "Authorization": f"Bearer {service_role_key()}",
            },
            timeout=10.0,
        )
    except AuthMisconfigured as exc:
        return False, str(exc)
    except httpx.HTTPError as exc:
        # The Auth uuid is an internal identifier, and the URL contains the
        # Supabase project ref, so neither the type chain beyond the class name
        # nor the text is safe to surface.
        logger.warning("%s", safe_exception(exc, context="auth account delete failed"))
        return False, "Could not reach Supabase Auth to delete the account."

    if response.status_code in (204, 200):
        return True, "deleted"
    if response.status_code == 404:
        # Already gone. The goal state is "this identity cannot sign in", and
        # that is satisfied, so this is a success, not a failure.
        return True, "already absent"
    logger.warning(
        "auth account delete rejected: status=%s", response.status_code
    )
    return False, f"Supabase Auth returned HTTP {response.status_code}."


def _lookup_learner(auth_id: str) -> Optional[dict[str, Any]]:
    """Map a Supabase auth uuid onto our learner row, with a short TTL cache.

    Cached because it is a database round trip on every authenticated request
    and the mapping only changes when someone re-links an account.
    """
    now = time.monotonic()
    with _cache_lock:
        hit = _auth_cache.get(auth_id)
        if hit and now - hit[0] < AUTH_CACHE_TTL:
            return hit[1]

    conn = get_db_connection()
    try:
        row = conn.execute(
            "SELECT id, name, role, auth_id FROM users WHERE auth_id = %s", (auth_id,)
        ).fetchone()
    finally:
        conn.close()

    result = dict(row) if row else None
    with _cache_lock:
        _auth_cache[auth_id] = (now, result)
    return result


def invalidate_auth_cache() -> None:
    """Drop the auth_id -> learner cache. Used by tests and by re-seeding."""
    with _cache_lock:
        _auth_cache.clear()


class Identity:
    """The authenticated caller, resolved to a row in `users`."""

    def __init__(self, learner: dict[str, Any], auth: dict[str, Any]):
        self.id: str = learner["id"]
        self.name: str = learner.get("name") or ""
        self.role: str = learner.get("role") or "learner"
        self.auth_id: str = learner.get("auth_id") or ""
        self.email: str = auth.get("email") or ""

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Identity {self.id} role={self.role}>"


def session_token(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = None,
) -> Optional[str]:
    """The caller's access token, from the header or the session cookie.

    The header wins when both are present so a script that somehow still holds
    a token cannot be overridden by an ambient cookie, and non-browser clients
    (curl, the seed scripts, a future mobile app) keep working unchanged.

    `credentials` defaults to None rather than to `Depends(bearer)` on purpose.
    This function is also called directly -- the logout route needs the raw
    token to revoke -- and a `Depends` default is a sentinel object that is
    never None, so the header branch below would try to read `.credentials` off
    it and raise AttributeError. Every FastAPI path supplies the argument
    explicitly, so nothing depends on the default resolving.
    """
    if credentials is not None and credentials.credentials:
        return credentials.credentials
    return request.cookies.get(SESSION_COOKIE) or None


def current_identity(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
) -> Identity:
    """Require any valid session.

    This is the dependency that closes the escalation hole: the caller's role
    now comes from the database row their token resolves to, never from the
    request body.
    """
    token = session_token(request, credentials)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    auth = verify_access_token(token)
    auth_id = auth.get("id")
    if not auth_id:
        raise HTTPException(status_code=401, detail="Malformed session")

    learner = _lookup_learner(auth_id)
    if not learner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is not linked to a SakshamAI profile. "
                   "Run scripts/seed_auth_users.py to link it.",
        )
    return Identity(learner, auth)


def require_admin(identity: Identity = Depends(current_identity)) -> Identity:
    """Require an administrator."""
    if not identity.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Administrator access required"
        )
    return identity


def optional_identity(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
) -> Optional[Identity]:
    """Resolve the caller if a token is present, but never demand one.

    For endpoints that are partly public and partly private — the course
    catalogue renders for a signed-out visitor, but the per-user progress
    columns behind the same URL must not be readable by asking for
    `?user_id=someone-else`. Those handlers call require_self_or_admin()
    themselves, but only once they know a user_id was actually requested.
    """
    token = session_token(request, credentials)
    if not token:
        return None
    try:
        return current_identity(request, credentials)
    except HTTPException:
        # A bad token is treated as no token here; the handler's own guard will
        # reject the request if it turns out to need an identity.
        return None


def require_self_or_admin(user_id: str, identity: Identity) -> None:
    """Assert the caller may act on `user_id`.

    Applied to every route that takes a user id, so a learner cannot read or
    write another learner's profile, scores, enrolments or quiz history just by
    changing an id in the URL.
    """
    if identity.is_admin:
        return
    if identity.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only access your own records",
        )
