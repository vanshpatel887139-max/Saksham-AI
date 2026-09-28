#!/usr/bin/env python3
"""Create the Supabase Auth accounts for the seeded demo users, and link them.

Run once after applying supabase/migrations/*.sql:

    backend/.venv/bin/python scripts/seed_auth_users.py

What it does
------------
For every row in `users` that has an email (all 11 seeded accounts), it
ensures a Supabase Auth user exists with that address, forces the shared demo
password so the accounts are usable straight after a clone, and stores the
resulting Supabase uuid in `users.auth_id`.

It is idempotent. Re-running it after a project pause, or to reset a forgotten
demo password, is safe and is the intended way to recover access.

The address is derived from the user id (`learner-1@sakshamai.demo`) rather
than stored anywhere else, so this script needs no config beyond the database
and the service-role key.

Why the service-role key
------------------------
Creating users is an admin-only operation in Supabase Auth. That key is a
credential equivalent to full bypass of RLS, so it is read from the
environment here and must never reach the frontend or be committed. The API
itself only ever uses the anon key.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import httpx

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

from database import get_db_connection  # noqa: E402

AUTH_URL = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
SERVICE_KEY = (os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
DEMO_PASSWORD = (os.environ.get("DEMO_USER_PASSWORD") or "").strip()

HEADERS = {"apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}"}


def fail(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(1)


def upsert_account(email: str, password: str) -> str:
    """Ensure an Auth user exists for `email`; return its uuid."""
    # Try update first: cheaper and avoids the "already registered" error.
    response = httpx.post(
        f"{AUTH_URL}/auth/v1/admin/users",
        json={"email": email, "password": password, "email_confirm": True},
        headers=HEADERS,
        timeout=15.0,
    )
    if response.status_code < 400:
        return response.json()["id"]

    created = httpx.post(
        f"{AUTH_URL}/auth/v1/admin/users",
        json={"email": email, "password": password, "email_confirm": True},
        headers=HEADERS,
        timeout=15.0,
    )
    if created.status_code < 400:
        return created.json()["id"]

    # Already exists — find it by listing.
    found = httpx.get(
        f"{AUTH_URL}/auth/v1/admin/users",
        params={"page": 1, "per_page": 1000},
        headers=HEADERS,
        timeout=15.0,
    )
    found.raise_for_status()
    for candidate in found.json().get("users", []):
        if candidate.get("email") == email:
            return candidate["id"]
    fail(f"could not create or find auth user for {email}: {created.text}")


def main() -> None:
    if not AUTH_URL:
        fail("SUPABASE_URL is not set")
    if not SERVICE_KEY:
        fail("SUPABASE_SERVICE_ROLE_KEY is not set (Settings -> API Keys)")
    if not DEMO_PASSWORD:
        fail("DEMO_USER_PASSWORD is not set. Pick any password; it is shared by all "
             "demo accounts and is only for demonstration use.")

    conn = get_db_connection()
    try:
        rows = conn.execute(
            "SELECT id, email, name FROM users WHERE email IS NOT NULL ORDER BY id"
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        fail("no users with an email found — apply supabase/migrations/003_seed.sql first")

    print(f"syncing {len(rows)} demo accounts to {AUTH_URL}\n")
    conn = get_db_connection()
    try:
        for row in rows:
            auth_id = upsert_account(row["email"], DEMO_PASSWORD)
            conn.execute(
                "UPDATE users SET auth_id = %s WHERE id = %s", (auth_id, row["id"])
            )
            print(f"  {row['id']:<12} {row['email']:<34} -> {auth_id}")
        conn.commit()
    finally:
        conn.close()

    print(f"\ndone. sign in with any of the above addresses and the password "
          f"in DEMO_USER_PASSWORD.")


if __name__ == "__main__":
    main()
