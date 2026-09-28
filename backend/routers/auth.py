"""Authentication routes.

The previous implementation was:

    user_id = "learner-1" if req.role == "learner" else "admin-1"
    return {"token": f"demo-token-{user_id}", "user": user}

with no verification of the token anywhere in the app, and a caller-supplied
`role` deciding whether you got the learner or the administrator. That is
"anyone can be anyone", so this router now performs a genuine credential check
against Supabase Auth and the token is verified on every subsequent request
(see auth_tokens.py).

The demo user picker survives, but as what it should be: a convenience for
choosing which of the seeded accounts to sign in as. It pre-fills the email
field. It does not authenticate anything by itself, because a picker that
logged you in without a password would reintroduce exactly the hole above.
"""

import logging
import os

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from auth_tokens import (
    Identity,
    REFRESH_COOKIE,
    clear_session_cookies,
    current_identity,
    invalidate_auth_cache,
    refresh_session,
    revoke_session,
    set_session_cookies,
    session_token,
    sign_in,
)
from database import get_db_connection
from models import LoginRequest
from log_safety import redact
from routers.users import USER_PROFILE_COLUMNS, fetch_user, user_to_dict
import rate_limit

router = APIRouter(prefix="/api/auth", tags=["auth"])

# The account-link refusal warning below still logs *something* for an operator
# to find, but the address value is passed through log_safety.redact(), so an
# email becomes [REDACTED]. The token and the password are never logged at all.
logger = logging.getLogger("sakshamai.auth")

# The personas the demo picker offers by default: one administrator and one
# learner. These two are the seeded accounts that have a real Supabase Auth
# identity, so they are the only ones whose buttons can complete a sign-in.
DEFAULT_DEMO_ACCOUNT_IDS = ("admin-1", "learner-1")


def _flag(name: str) -> bool:
    """Read a boolean environment variable, defaulting to off.

    Deliberately strict: only an explicit truthy spelling enables the flag, so
    a typo or an empty value fails closed rather than publishing something by
    accident.
    """
    return (os.environ.get(name) or "").strip().lower() in {"1", "true", "yes", "on"}


def _demo_account_ids() -> list[str]:
    """Which seeded accounts the public picker is allowed to list.

    The `users` table is seeded with every demo persona so that progress,
    courses and scores can reference them, but most of those personas have no
    Supabase Auth identity -- listing them offered a button that filled the
    email field and then failed to sign in with a 401. The picker is a
    convenience, not an authorization surface, so it may only advertise
    accounts that can actually authenticate.

    This narrows what is *displayed* and nothing else. Sign-in is still verified
    against Supabase Auth on every attempt, so an id excluded here gains no
    access, and an id included here still needs the correct password.

    Configurable via DEMO_ACCOUNT_IDS (comma separated, no quoting) so a
    deployment can change the roster without a code change. A blank or
    whitespace-only value falls back to the default rather than publishing an
    empty picker.
    """
    raw = os.environ.get("DEMO_ACCOUNT_IDS") or ""
    ids = [d.strip() for d in raw.split(",") if d.strip()]
    return ids or list(DEFAULT_DEMO_ACCOUNT_IDS)


def _linkable_emails() -> set[str]:
    """Emails permitted to be auto-linked to a `users` row on sign-in.

    Signing in does `UPDATE users SET auth_id = ... WHERE email = %s`, so the
    email in the credential is what chooses the account. On a Supabase project
    with public sign-up enabled -- the default, and this project's setting --
    anybody holding the public anon key can create an auth account for an
    arbitrary address. If a seeded persona ever carries a registerable domain,
    that is all it takes: register the address, sign in, and the link lands on
    the persona, administrator included.

    The seeded personas use `@sakshamai.demo`, which GoTrue rejects as an
    invalid TLD, so today the only addresses that can reach this are the demo
    accounts. That is luck, not a control, and it stops being true the moment a
    real domain is added. So the link is gated on an explicit allowlist, and an
    address that is not on it cannot be claimed by a self-registered account.

    Configurable via AUTH_LINK_ALLOWLIST (comma separated). A blank value falls
    back to the emails of the demo accounts rather than defaulting to "link
    anyone", so a misconfiguration fails closed.
    """
    raw = os.environ.get("AUTH_LINK_ALLOWLIST") or ""
    emails = {e.strip().lower() for e in raw.split(",") if e.strip()}
    if emails:
        return emails

    conn = get_db_connection()
    try:
        rows = conn.execute(
            "SELECT email FROM users WHERE email IS NOT NULL AND id = ANY(%s)",
            (_demo_account_ids(),),
        ).fetchall()
    finally:
        conn.close()
    return {r["email"].strip().lower() for r in rows if r["email"]}


@router.get("/demo-users")
def demo_users():
    """List the seeded demo accounts.

    Public on purpose: the login screen needs it before anyone has signed in,
    and it exposes nothing that is not already visible in the app — name,
    department, job title, and a synthetic `.demo` address. No token,
    competency level or score is included.

    The shared demo password is echoed back only when EXPOSE_DEMO_PASSWORD is
    explicitly true, and is omitted otherwise. It used to be returned whenever
    DEMO_USER_PASSWORD was set, which handed a credential to any anonymous
    caller on a stock deployment — the variable is set for seeding, so "set"
    is the wrong condition for "safe to publish". Opting in separately is the
    difference between a default that leaks and a default that does not.

    Either way the login screen degrades gracefully: with the field absent the
    picker only pre-fills the email. Delete this endpoint when the demo
    accounts are replaced by real staff accounts.

    Only the accounts in DEMO_ACCOUNT_IDS are listed (see `_demo_account_ids`).
    The table holds every seeded persona, but the rest have no Auth identity, so
    offering them meant shipping buttons that could only ever fail. The filter
    only narrows what is advertised: it grants no access, and excludes nothing
    that is reachable by supplying credentials directly.
    """
    demo_ids = _demo_account_ids()
    conn = get_db_connection()
    try:
        rows = conn.execute(
            "SELECT id, email, name, department, designation, role "
            "FROM users WHERE email IS NOT NULL "
            "AND id = ANY(%s) "
            "ORDER BY (role = 'admin') DESC, id",
            (demo_ids,),
        ).fetchall()
    finally:
        conn.close()

    accounts = [
        {
            "userId": r["id"],
            "email": r["email"],
            "name": r["name"],
            "department": r["department"] or "",
            "designation": r["designation"] or "",
            "role": r["role"],
        }
        for r in rows
    ]

    demo_password: str | None = None
    if _flag("EXPOSE_DEMO_PASSWORD"):
        demo_password = (os.environ.get("DEMO_USER_PASSWORD") or "").strip() or None
    return {"users": accounts, "demoPassword": demo_password}


@router.post("/login")
def login(req: LoginRequest, request: Request, response: Response):
    """Exchange email + password for a session.

    The session is set as an `httpOnly` cookie and the token is deliberately
    *not* returned in the body: anything the response hands to script can be
    read by injected script, and the point of the cookie is that it cannot. The
    `user` payload is produced by the canonical serializer in the users router,
    so login returns exactly what GET /api/users/{id} returns — including
    competency provenance.

    Throttled on two axes: per client IP (5 per minute), to stop one host
    spraying many accounts, and per email (5 per 15 minutes), to stop a focused
    guessing run against one user spread over many hosts.
    Only *credential* failures count, so a legitimate user signing in repeatedly
    is not locked out, nor is anyone locked out by an auth-provider outage.
    See rate_limit.py for the scope of what this does and does not protect.
    """
    email = req.email.strip().lower()
    client_ip = request.client.host if request.client else "unknown"

    for scope, key, limit in (
        ("ip", client_ip, rate_limit.max_per_ip()),
        ("email", email, rate_limit.max_per_email()),
    ):
        if rate_limit.remaining(scope, key) <= 0:
            raise HTTPException(
                status_code=429,
                detail=(
                    "Too many failed sign-in attempts. Wait before trying again."
                ),
                headers={"Retry-After": str(rate_limit.retry_after_seconds(scope, key))},
            )

    try:
        session = sign_in(email, req.password)
    except HTTPException as exc:
        # Only a genuine credential rejection counts against the budget. A 5xx
        # or 503 means the auth provider is unreachable, not that the user
        # mistyped anything -- counting those would let a Supabase outage lock
        # every real user out of their own account for the whole window.
        if exc.status_code in (401, 403):
            rate_limit.record_failure("ip", client_ip)
            rate_limit.record_failure("email", email)
        raise

    access_token = session.get("access_token")
    if not access_token:
        raise HTTPException(status_code=502, detail="Supabase returned no access token")

    auth_id = (session.get("user") or {}).get("id")

    # Refuse to let a self-registered auth account claim a seeded profile. See
    # _linkable_emails: the credential's email is what selects the row, and on a
    # project with public sign-up open, that email is attacker-chosen.
    if email not in _linkable_emails():
        logger.warning("refused account link for unlisted address %s", redact(email))
        raise HTTPException(
            status_code=403,
            detail="This account is not provisioned for SakshamAI. "
                   "Ask an administrator to add it to AUTH_LINK_ALLOWLIST.",
        )

    # Self-heal the users.auth_id link. seed_auth_users.py normally does this
    # up front, but doing it here as well means a project that was seeded
    # before Auth was wired up starts working without a manual SQL fix.
    invalidate_auth_cache()
    conn = get_db_connection()
    try:
        row = conn.execute(
            "UPDATE users SET auth_id = %s WHERE email = %s "
            f"RETURNING {USER_PROFILE_COLUMNS}",
            (auth_id, email),
        ).fetchone()
        if not row:
            raise HTTPException(
                status_code=403,
                detail="Signed in, but this account has no SakshamAI profile. "
                       "Run scripts/seed_auth_users.py to create the demo accounts.",
            )
        conn.commit()
        user = user_to_dict(row, conn)
    finally:
        conn.close()

    # Both cookies, in one place, each with a lifetime taken from the session.
    set_session_cookies(response, request, session)
    return {"user": user}


@router.post("/refresh")
def refresh(request: Request, response: Response):
    """Exchange the refresh cookie for a fresh access token.

    The frontend calls this exactly once when a request comes back 401, then
    replays the original call. Without it the access token's one-hour expiry is
    an involuntary sign-out, and a user who has genuinely left their tab open
    over a coffee break returns to a login screen.

    Both cookies are reissued because Supabase rotates the refresh token on
    every exchange: storing the one we sent instead of the one returned would
    work once and fail on the next refresh.

    Deliberately outside the credential-failure rate limiter. Throttling this
    would lock out exactly the users who are only refreshing because their
    session lapsed while idle.
    """
    token = request.cookies.get(REFRESH_COOKIE)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No session to refresh.",
        )
    session = refresh_session(token)
    set_session_cookies(response, request, session)
    return {"ok": True, "expiresIn": int(session.get("expires_in") or 3600)}


@router.post("/logout")
def logout(request: Request, response: Response):
    """Revoke the Supabase session and drop both cookies.

    Revoking matters: clearing the cookie alone leaves the access token valid
    until it expires and the refresh token usable for a week, so a token
    captured before sign-out keeps working for a long time afterwards. GoTrue's
    `scope=local` kills this session without signing the user out everywhere
    else.

    Clears the cookies regardless of whether revocation succeeded, so the
    caller's browser always ends up clean.
    """
    revoke_session(
        session_token(request), request.cookies.get(REFRESH_COOKIE)
    )
    clear_session_cookies(response, request)
    return {"ok": True}


@router.get("/me")
def me(identity: Identity = Depends(current_identity)):
    """Return the caller's own profile. Doubles as a token self-test."""
    conn = get_db_connection()
    try:
        row = fetch_user(conn, identity.id)
        if not row:
            raise HTTPException(status_code=404, detail="User not found")
        return user_to_dict(row, conn)
    finally:
        conn.close()
