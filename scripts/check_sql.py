#!/usr/bin/env python3
"""Static checks for the SQL embedded in the Python routers.

The SQLite -> PostgreSQL move touched ~124 parameter placeholders across ten
router modules, most of them rewritten by a script and the rest by hand. Two
classes of bug survive a syntax check of the .py files but only appear at
runtime against a real database, and both are caught here without one:

  1. SQL that is not valid PostgreSQL (a leftover `INSERT OR REPLACE`, a
     SQLite function, an unquoted reserved word).
  2. A placeholder count that does not match the number of arguments actually
     passed, which psycopg reports only when that specific query executes.

Usage:
    backend/.venv/bin/python scripts/check_sql.py

Requires `pglast` (the real PostgreSQL parser). Exits non-zero on failure.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

try:
    from pglast import parse_sql
except ImportError:
    print("pglast not installed: pip install pglast", file=sys.stderr)
    raise SystemExit(2)

BACKEND = Path(__file__).resolve().parent.parent / "backend"
REPO = BACKEND.parent

# Calls whose first argument is SQL. Anything not listed is assumed not to be.
SQL_CALLS = {"execute", "executemany", "fetchone", "fetchall"}

# SQLite spellings that have no PostgreSQL equivalent. Reported as errors
# rather than left to fail at runtime against a live database.
SQLITE_ONLY = [
    ("INSERT OR REPLACE", "PostgreSQL: INSERT ... ON CONFLICT ... DO UPDATE"),
    ("INSERT OR IGNORE", "PostgreSQL: INSERT ... ON CONFLICT DO NOTHING"),
    ("PRAGMA ", "PostgreSQL has no PRAGMA"),
    ("sqlite_master", "PostgreSQL: information_schema / pg_catalog"),
    ("strftime(", "PostgreSQL: to_char(), or format from Python"),
    ("julianday(", "PostgreSQL: extract(epoch from ...)"),
    ("IFNULL(", "PostgreSQL: COALESCE("),
    ("datetime('now')", "PostgreSQL: now()"),
    ("AUTOINCREMENT", "PostgreSQL: GENERATED ALWAYS AS IDENTITY"),
    ("rowid", "PostgreSQL: no equivalent; add a timestamp column"),
]


def sql_calls(tree: ast.AST):
    """Yield (lineno, sql_text, n_placeholders, n_args) for every SQL call."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
        if name not in SQL_CALLS or not node.args:
            continue

        first = node.args[0]
        # Implicitly concatenated string literals arrive as one Constant.
        if not (isinstance(first, ast.Constant) and isinstance(first.value, str)):
            continue

        sql = first.value
        n_ph = sql.count("%s")

        # Argument tuple is optional; a bare string means no parameters.
        n_args: int | None = None
        if len(node.args) > 1:
            second = node.args[1]
            if isinstance(second, ast.Tuple):
                n_args = len(second.elts)
            elif isinstance(second, ast.Starred):
                n_args = None  # unpacked, cannot verify statically
            else:
                n_args = 1
        else:
            n_args = 0

        yield node.lineno, sql, n_ph, n_args


def check_file(path: Path) -> list[str]:
    src = path.read_text()
    tree = ast.parse(src, filename=str(path))
    problems: list[str] = []

    for lineno, sql, n_ph, n_args in sql_calls(tree):
        snippet = sql.strip().splitlines()[0][:70]
        where = f"{path.name}:{lineno}"

        for token, advice in SQLITE_ONLY:
            if token.lower() in sql.lower():
                problems.append(f"{where}  SQLite-only `{token}` — {advice}")

        if "%(" in sql:
            problems.append(f"{where}  named placeholders `%(...)s` are not used here")

        # psycopg sends %s as a bind parameter; substitute a literal so the
        # PostgreSQL parser sees valid SQL.
        probe = sql.replace("%s", "NULL")
        try:
            parse_sql(probe)
        except Exception as exc:  # pglast.ParseError and friends
            first = str(exc).splitlines()[0][:110]
            problems.append(f"{where}  not valid PostgreSQL: {first}\n           in: {snippet}")

        if n_args is not None and n_ph != n_args:
            problems.append(
                f"{where}  placeholder/argument mismatch: "
                f"{n_ph} `%s` vs {n_args} args\n           in: {snippet}"
            )

    return problems


def main() -> int:
    targets = sorted((BACKEND / "routers").glob("*.py")) + [BACKEND / "database.py"]
    all_problems: list[str] = []
    checked = 0

    for path in targets:
        problems = check_file(path)
        checked += 1
        status = "OK" if not problems else f"{len(problems)} problem(s)"
        print(f"{path.name:<20} {status}")
        for p in problems:
            print(f"    {p}")

    all_problems = [p for path in targets for p in check_file(path)]
    print()
    if all_problems:
        print(f"FAILED: {len(all_problems)} problem(s) in {checked} files")
        return 1
    print(f"OK: {checked} files, all embedded SQL is valid PostgreSQL "
          f"with matching parameter counts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
