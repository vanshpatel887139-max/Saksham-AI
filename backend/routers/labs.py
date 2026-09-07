"""Virtual Labs route — interactive lab data + sandboxed Python execution.

Run endpoint: compiles user code first (real SyntaxError reporting), then
executes it in a lightweight sandboxed subprocess with CPU/memory/file limits
and a timeout. DEMO-ONLY sandbox — not hardened for production use; do not run
this against untrusted code in a shared environment without stronger isolation.
"""

import json
import os
import resource
import subprocess
import sys
import tempfile
import time

from fastapi import APIRouter
from pydantic import BaseModel

from database import get_db_connection

router = APIRouter(prefix="/api/labs", tags=["labs"])

MAX_CODE_LEN = 8000
RUN_TIMEOUT = 5  # seconds


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


def _format_syntax_error(e: SyntaxError, code: str) -> str:
    line, col = e.lineno, e.offset or 0
    caret = ""
    if line is not None:
        src = code.splitlines()
        if 0 < line <= len(src):
            caret = f"\n  {src[line - 1]}\n  {' ' * max(0, col - 1)}^"
    return f"SyntaxError: {e.msg}{caret} (line {line})"


@router.post("/run")
def run_python(req: PythonRunRequest):
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
    path = None
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write(code)
            path = f.name
        proc = subprocess.run(
            [sys.executable, "-I", "-u", path],
            capture_output=True,
            text=True,
            timeout=RUN_TIMEOUT,
            preexec_fn=_sandbox_limits,
        )
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "output": "",
            "error": f"Execution timed out after {RUN_TIMEOUT}s (possible infinite loop)",
            "durationMs": int((time.perf_counter() - start) * 1000),
        }
    finally:
        if path and os.path.exists(path):
            try:
                os.unlink(path)
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