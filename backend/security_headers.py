"""Response security headers.

The API previously set none of these. That is survivable for a JSON API whose
responses are only ever read by `fetch()`, but not for the parts of this
surface a browser will render directly: `/docs`, `/redoc`, and `/openapi.json`.
A missing `X-Content-Type-Options` there is enough for a browser to be persuaded
to execute a JSON document as HTML, and `X-Frame-Options` is what stops the
Swagger UI from being framed for clickjacking an authenticated operator.

The frontend's own static responses need the same headers, and a stricter CSP,
since that is where scripts actually run. See `deploy/nginx.conf.example` and
the headers block in `vite.config.ts` — headers set here do not cover the
bundle, because the bundle is served by a different server.
"""

from __future__ import annotations

import os


# Dev policy. Swagger UI injects an inline bootstrap <script> and a <style>
# block, so a dev server that still serves /docs has to permit both.
#
# This is NOT the production policy. 'unsafe-inline' in script-src does not
# restrict scripts to your own origin at all -- it permits any inline script
# from any origin, so an injected <script>alert(1)</script> still runs. Keeping
# it in production would mean the one header meant to stop XSS stopped nothing.
API_CSP_DEV = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self' 'unsafe-inline'",
        "style-src 'self' 'unsafe-inline'",
        "img-src 'self' data:",
        "font-src 'self'",
        "connect-src 'self'",
        "frame-ancestors 'none'",
        "base-uri 'none'",
        "form-action 'self'",
        "object-src 'none'",
    ]
)

# Production policy. No inline script at all, which is only possible because
# production does not serve the Swagger page (see main.py). The API returns
# JSON, so nothing needs to execute: script-src 'self' is the whole control.
API_CSP_PROD = "; ".join(
    [
        "default-src 'none'",
        "script-src 'self'",
        "style-src 'self'",
        "img-src 'self' data:",
        "font-src 'self'",
        "connect-src 'self'",
        "frame-ancestors 'none'",
        "base-uri 'none'",
        "form-action 'self'",
        "object-src 'none'",
    ]
)

HSTS = "max-age=31536000; includeSubDomains"


def csp_for_api() -> str:
    """Return the API policy, strict in production.

    ``CSP_API`` still overrides, so a deployment can tighten further. Overriding
    is one-directional in practice: the value has to be a non-empty string, and
    leaving it unset gets the stricter of the two policies.
    """
    override = (os.environ.get("CSP_API") or "").strip()
    if override:
        return override
    import deploy_config

    return API_CSP_PROD if deploy_config.environment() == "production" else API_CSP_DEV

def csp_for_frontend() -> str:
    """The policy the *static* app needs.

    Separate from the API policy because the app is a real document: it runs
    bundled React, so `script-src 'self'` applies to the built files and no
    inline script is needed in production. Vite injects an inline module script
    only in dev, which is why dev needs 'unsafe-inline' and production does not.

    NOTE: nothing calls this. The FastAPI process does not serve the SPA — it
    mounts no StaticFiles and has no catch-all route — so it has no response to
    put a document policy on. The frontend's CSP is whatever serves the built
    files: `vercel.json` for the Vercel deployment, or the
    `Content-Security-Policy` line in `deploy/nginx.conf.example` for a
    self-hosted one. Setting CSP_FRONTEND here therefore has no effect, which is
    a trap worth stating rather than leaving to be discovered. If the policy
    needs to change, change it in the place that actually emits the header, and
    keep these three lists in step.
    """
    return (os.environ.get("CSP_FRONTEND") or "").strip() or "; ".join(
        [
            "default-src 'self'",
            "script-src 'self'",
            "style-src 'self' 'unsafe-inline'",
            "img-src 'self' data: blob:",
            "font-src 'self' data:",
            "connect-src 'self' https://*.supabase.co",
            "frame-ancestors 'none'",
            "base-uri 'self'",
            "form-action 'self'",
            "object-src 'none'",
            "upgrade-insecure-requests",
        ]
    )


def security_headers(*, csp: str, hsts: bool) -> dict[str, str]:
    """The header set applied to every response.

    HSTS is conditional. Sending it over plain HTTP in development is not merely
    pointless: a browser that has seen it will refuse to fall back to http for
    that host for a year, which breaks a developer's local setup in a way that
    is tedious to diagnose and impossible to undo from the page. It is also
    ignored by browsers over http, so nothing is lost by withholding it.

    `Referrer-Policy` is included because the app links out, and a full referrer
    can carry the current URL — which for an admin view may contain a user id.
    """
    headers = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Content-Security-Policy": csp,
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "X-Permitted-Cross-Domain-Policies": "none",
        "Cross-Origin-Opener-Policy": "same-origin",
    }
    if hsts:
        headers["Strict-Transport-Security"] = HSTS
    return headers


def should_send_hsts(request_host: str) -> bool:
    """HSTS only for real deployments, never for loopback.

    Same reasoning as the cookie's `Secure` attribute: the hosts here that are
    knowingly plain-HTTP are all local, and poisoning a developer's localhost
    costs an hour of confusion.
    """
    host = (request_host or "").split(":")[0].strip("[]")
    if host in {"localhost", "127.0.0.1", "::1", ""}:
        return False
    # A plain-HTTP production deployment is misconfigured; say so rather than
    # sending a header the browser will ignore anyway.
    return True
