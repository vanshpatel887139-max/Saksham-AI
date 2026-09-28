"""Virtual Labs route — interactive lab data + sandboxed Python execution.

Run endpoint: compiles user code first (real SyntaxError reporting), then
executes it in a lightweight sandboxed subprocess with CPU/memory/file limits
and a timeout. DEMO-ONLY sandbox — not hardened for production use; do not run
this against untrusted code in a shared environment without stronger isolation.

SECURITY. This route is remote code execution by design, so it is treated as
the most dangerous endpoint in the app. The sandbox still cannot stop the
executed code from reading any file the server can read (so an absolute path
to `backend/.env`, including SUPABASE_SERVICE_ROLE_KEY and the database
password) or from making outbound network calls to exfiltrate it. RLIMIT_CPU /
RLIMIT_AS / RLIMIT_NOFILE stop neither of those. A timeout is not a sandbox.

What has been hardened: the child runs in an isolated temp directory (so
repo-relative reads fail) with a scrubbed environment (so `os.environ` cannot
expose SUPABASE_*, DATABASE_URL, GROQ_* or other server secrets).

Therefore POST /run requires a signed-in user, and it is refused outright once
a real Supabase backend is configured, unless ALLOW_CODE_EXECUTION is
explicitly set. That default is the safe direction: pointing the app at a real
database is the signal that it is no longer a laptop demo.
"""

import json
import os
import resource
import shutil
import subprocess
import sys
import tempfile
import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth_tokens import Identity, current_identity
from database import get_db_connection

router = APIRouter(prefix="/api/labs", tags=["labs"])

MAX_CODE_LEN = 8000
RUN_TIMEOUT = 5  # seconds


def _flag(name: str) -> bool:
    """Read a boolean env var, defaulting to off. Fails closed on typos."""
    return (os.environ.get(name) or "").strip().lower() in {"1", "true", "yes", "on"}


def _code_execution_enabled() -> bool:
    """Is running caller-supplied Python allowed right now?

    On by default only while there is no real backend configured — i.e. the
    laptop demo. As soon as SUPABASE_URL is set the app is pointed at real
    infrastructure holding real credentials, so execution is off unless someone
    has deliberately turned it back on.
    """
    if _flag("ALLOW_CODE_EXECUTION"):
        return True
    if _flag("DISABLE_CODE_EXECUTION"):
        return False
    return not (os.environ.get("SUPABASE_URL") or "").strip()


class PythonRunRequest(BaseModel):
    code: str


@router.get("")
def list_labs():
    conn = get_db_connection()
    try:
        rows = conn.execute("SELECT * FROM labs").fetchall()
        return [
            {
                "id": r["id"],
                "title": r["title"],
                "category": r["category"],
                "description": r["description"],
                "icon": r["icon"],
                "exercises": json.loads(r["exercises"]),
            }
            for r in rows
        ]
    finally:
        conn.close()


def _sandbox_limits():
    """Resource limits applied in the child process before exec (best-effort)."""
    for res, soft, hard in (
        (resource.RLIMIT_CPU, 3, 3),
        (resource.RLIMIT_AS, 512 * 1024 * 1024, 512 * 1024 * 1024),
        (resource.RLIMIT_NOFILE, 64, 64),
    ):
        try:
            resource.setrlimit(res, (soft, hard))
        except (ValueError, OSError):
            pass


# Key names that may carry credentials or similar server secrets. The executed
# child inherits whatever we pass as its environment, and os.environ is the
# easiest exfiltration channel there is.
_SENSITIVE_VAR_PREFIXES = (
    "SUPABASE_", "DATABASE_URL", "GROQ_", "DEMO_", "COOKIE_",
    "AUTH_", "CORS_", "ALLOWED_HOSTS", "MAX_UPLOAD_BYTES",
    "FORWARDED_ALLOW_IPS", "EXPOSE_DEMO_PASSWORD",
)


def _sandbox_env() -> dict[str, str]:
    """A minimal environment for the executed child.

    Without this the lab inherits every variable the server runs with, and the
    point of POST /run is to execute caller-supplied Python — so a signed-in
    user could print SUPABASE_SERVICE_ROLE_KEY, the database URL or the Groq
    key straight out of os.environ. The child gets only what the interpreter
    needs to run, plus whatever local demo flags are deliberately made visible.
    """
    keep = {"PATH", "HOME", "LANG", "LC_ALL", "TMPDIR", "TEMP", "TMP", "PYTHONIOENCODING"}
    env = {k: v for k, v in os.environ.items() if k in keep and v}
    for k in list(env):
        if k.startswith(_SENSITIVE_VAR_PREFIXES) or "SECRET" in k.upper() or "KEY" in k.upper():
            env.pop(k)
    return env


def _format_syntax_error(e: SyntaxError, code: str) -> str:
    line, col = e.lineno, e.offset or 0
    caret = ""
    if line is not None:
        src = code.splitlines()
        if 0 < line <= len(src):
            caret = f"\n  {src[line - 1]}\n  {' ' * max(0, col - 1)}^"
    return f"SyntaxError: {e.msg}{caret} (line {line})"


@router.post("/run")
def run_python(
    req: PythonRunRequest,
    identity: Identity = Depends(current_identity),
):
    if (rate_limit.llm_budget_remaining(f"llm:{identity.id}") or 0) < 0:
        raise HTTPException(
            status_code=429,
            detail="Daily AI generation limit reached. Try again tomorrow.",
            headers={"Retry-After": "86400"},
        )
    if not _code_execution_enabled():
        raise HTTPException(
            status_code=503,
            detail=(
                "Code execution is disabled on this deployment. It runs "
                "caller-supplied Python without real isolation, so it is only "
                "available in local demo mode."
            ),
        )

    code = (req.code or "").strip()
    if not code:
        return {"ok": False, "output": "", "error": "No code provided", "durationMs": 0}
    if len(code) > MAX_CODE_LEN:
        return {"ok": False, "output": "", "error": f"Code too long (max {MAX_CODE_LEN} characters)", "durationMs": 0}

    # Real compile step → genuine SyntaxError with line/column
    try:
        compile(code, "<lab>", "exec")
    except SyntaxError as e:
        return {"ok": False, "output": "", "error": _format_syntax_error(e, code), "durationMs": 0}
    except ValueError as e:
        return {"ok": False, "output": "", "error": f"Could not compile code: {e}", "durationMs": 0}

    start = time.perf_counter()
    workdir = None
    try:
        workdir = tempfile.mkdtemp(prefix="sakshamai-lab-", suffix="-tmp")
        snippet = os.path.join(workdir, "snippet.py")
        with open(snippet, "w") as f:
            f.write(code)
        # cwd is the temp dir, not the repo, so relative reads like
        # `open("backend/.env")` cannot reach the server's own files. The env
        # is scrubbed in _sandbox_env() so os.environ cannot leak credentials.
        proc = subprocess.run(
            [sys.executable, "-I", "-u", "snippet.py"],
            capture_output=True,
            text=True,
            timeout=RUN_TIMEOUT,
            preexec_fn=_sandbox_limits,
            env=_sandbox_env(),
            cwd=workdir,
        )
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "output": "",
            "error": f"Execution timed out after {RUN_TIMEOUT}s (possible infinite loop)",
            "durationMs": int((time.perf_counter() - start) * 1000),
        }
    finally:
        if workdir and os.path.exists(workdir):
            try:
                shutil.rmtree(workdir, ignore_errors=True)
            except OSError:
                pass

    duration_ms = int((time.perf_counter() - start) * 1000)
    output = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()
    ok = proc.returncode == 0
    if not ok and not err:
        if proc.returncode < 0:
            err = f"Execution stopped by system ({proc.returncode}) — likely a CPU/resource limit"
        else:
            err = f"Execution failed with exit code {proc.returncode}"
    return {
        "ok": ok,
        "output": output,
        "error": "" if ok else err,
        "durationMs": duration_ms,
    }