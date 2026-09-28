#!/usr/bin/env python3
"""Generate supabase/migrations/003_seed.sql from the canonical seed data.

The reference data (32 competencies, 288 role requirements, 17 courses,
5 labs) lives as plain Python constants in backend/database.py. This script
turns those into an idempotent SQL seed rather than hand-typing 337 rows,
which is the main way a migration like this silently corrupts its own
reference data.

It also promotes the nine `ORG_LEARNERS` entries into real `users` rows with
real `competency_scores`, which is what makes the admin dashboard compute
genuine numbers instead of reporting the old hardcoded figures.

Usage:
    python3 scripts/export_seed.py            # writes 003_seed.sql
    python3 scripts/export_seed.py --check    # verify the committed file is current
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

import database as db  # noqa: E402

OUT = ROOT / "supabase" / "migrations" / "003_seed.sql"
SEED_VERSION = "3"

# Notifications/activity for the primary demo learner, lifted out of
# database.py's init so the seed generator and the runtime agree.
NOTIFICATIONS = [
    ("n1", "learner-1",
     "Your Data Visualization competency improved from Level 2 to Level 3 after completing the recommended course and assessment.",
     "success", "2025-09-01", False),
    ("n2", "learner-1", "New course available: Advanced Machine Learning for Statistics",
     "info", "2025-08-28", False),
    ("n3", "learner-1", "You have multiple high-priority skill gaps to address for your target role.",
     "warning", "2025-08-25", True),
    ("n4", "learner-1", "Monthly learning streak: 7 days! Keep it up.",
     "success", "2025-08-20", True),
]

ACTIVITIES = [
    ("a1", "learner-1", "Completed Quiz", "Python for Government Data Analysis - Score: 80%", "2025-09-01", "\U0001F4DD"),
    ("a2", "learner-1", "Enrolled in Course", "Data Visualization with Power BI", "2025-08-28", "\U0001F4DA"),
    ("a3", "learner-1", "Skill Improved", "Data Visualization: Level 2 → Level 3", "2025-08-25", "\U0001F3AF"),
    ("a4", "learner-1", "Completed Course", "Introduction to Artificial Intelligence", "2025-08-20", "✅"),
    ("a5", "learner-1", "Profile Updated", "Added career goal: Senior Statistical Officer", "2025-08-15", "\U0001F464"),
]


def q(value) -> str:
    """Render a Python value as a SQL literal."""
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        return "'" + value.replace("'", "''") + "'"
    raise TypeError(f"unsupported literal: {value!r}")


def jsonb(value: str) -> str:
    """Render a JSON document as a jsonb literal."""
    return q(value) + "::jsonb"


def insert(table: str, columns: list[str], rows: list[tuple]) -> str:
    if not rows:
        return ""
    cols = ", ".join(columns)
    body = ",\n    ".join(
        "(" + ", ".join(q(v) for v in row) + ")" for row in rows
    )
    return (
        f"INSERT INTO {table} ({cols})\nVALUES\n    {body}\n"
        f"ON CONFLICT DO NOTHING;\n"
    )


def slugify(name: str) -> str:
    """Stable short id from a display name.

    This is MD5 and that is correct here, but only because this is an
    identifier, never a credential: it turns "Data Analysis" into a
    deterministic primary key so re-running the export produces the same rows
    and ON CONFLICT DO NOTHING actually dedupes. It protects nothing.

    No password, token or key is ever hashed anywhere in this project. Those
    are handled by Supabase Auth, which applies bcrypt server-side; this
    application never receives a password to store. See docs/PRIVACY.md.
    """
    return hashlib.md5(name.lower().encode()).hexdigest()[:8]


def synth_levels(avg: float, seed: str, comp_ids: list[str]) -> dict[str, int]:
    """Deterministic per-competency levels whose mean is close to `avg`.

    Flat assignment would make every gap look identical and the admin
    dashboard boring, so each competency gets a stable hash-derived jitter of
    -1/0/+1 on top of a floor/ceil split. Same input, same output, every time
    the seed is regenerated.
    """
    base = max(1, min(5, int(avg)))
    frac = max(0.0, min(1.0, avg - base))
    n_up = int(round(frac * len(comp_ids)))
    levels: dict[str, int] = {}
    for i, cid in enumerate(comp_ids):
        h = int(hashlib.md5(f"{seed}:{cid}".encode()).hexdigest()[:8], 16)
        jitter = (h % 3) - 1
        levels[cid] = max(1, min(5, base + (1 if i < n_up else 0) + jitter))
    return levels


def synth_enrollments(user_id: str, seed: str) -> tuple[list[tuple], list[tuple]]:
    """Deterministic enrolments + module completions for one learner.

    Without this the admin dashboard's learning-hours and completion-rate
    figures are legitimately zero on a fresh demo, because nobody has
    enrolled in anything. Progress is derived from the course's own module
    count so a 100% course really does have every module marked complete.
    """
    enrolments: list[tuple] = []
    modules: list[tuple] = []
    h = int(hashlib.md5(seed.encode()).hexdigest()[:8], 16)
    n_courses = 2 + (h % 3)
    for k in range(n_courses):
        course = db.COURSES[(h >> (k * 3)) % len(db.COURSES)]
        course_id = course[0]
        titles = [m["title"] for m in json.loads(course[12])]
        if not titles:
            continue
        # Every third enrolment is finished, the rest are part-way through.
        if k == 0:
            progress = 100
        else:
            progress = [25, 40, 60, 75][(h >> (k * 2)) % 4]
        enrolments.append((user_id, course_id, progress, "2025-09-01"))
        done = titles if progress == 100 else titles[: max(1, round(len(titles) * progress / 100))]
        for title in done:
            modules.append((user_id, course_id, title, "2025-09-01"))
    return enrolments, modules


def build() -> str:
    comp_ids = [c[0] for c in db.COMPETENCIES]
    out: list[str] = []
    add = out.append

    add("-- SakshamAI — 003_seed.sql  (generated by scripts/export_seed.py)\n")
    add("-- Idempotent: safe to re-run. Do not edit by hand; edit database.py\n")
    add("-- and regenerate with `python3 scripts/export_seed.py`.\n")
    add("\nBEGIN;\n")

    # -- reference data ----------------------------------------------------
    add("\n-- ---------------------------------------------------------------- reference")
    add(insert(
        "competencies", ["id", "name", "category", "description"],
        [tuple(c) for c in db.COMPETENCIES],
    ))

    add(insert(
        "role_requirements", ["role", "competency_id", "level"],
        [tuple(r) for r in db.ROLE_REQUIREMENTS],
    ))

    course_rows = [
        (
            cid, code, title, provider, desc,
            jsonb(skills), diff, dur, lang, rating, thumb, cat,
            jsonb(modules),
        )
        for (cid, code, title, provider, desc, skills, diff, dur, lang,
             rating, thumb, cat, modules) in db.COURSES
    ]
    add(insert(
        "courses",
        ["id", "course_code", "title", "provider", "description",
         "skills_covered", "difficulty", "duration", "language", "rating",
         "thumbnail", "category", "modules"],
        course_rows,
    ))

    # exercises deliberately stays text — see note 5 in 001_schema.sql
    add(insert(
        "labs", ["id", "title", "category", "description", "icon", "exercises"],
        [tuple(l) for l in db.LABS],
    ))

    # -- users -------------------------------------------------------------
    add("\n-- ---------------------------------------------------------------- users")
    user_rows = [
        ("learner-1", "Ananya Sharma", "GOV-2021-0847", "Statistical Investigator",
         "National Sample Survey Office", "learner", "Data Analyst",
         "M.Sc. Statistics, University of Delhi", 3, "Senior Statistical Officer",
         "Basic Data Entry, Census Operations Training", "English", True, "Active"),
        ("admin-1", "Dr. Rajesh Kumar", "GOV-2015-0123", "Director",
         "National Sample Survey Office", "admin", "Administrator",
         "Ph.D. Statistics, IIT Kanpur", 15, "Additional Secretary",
         "Leadership Development Program", "English", True, "Active"),
    ]
    # The nine ORG_LEARNERS become real accounts so learner_directory has
    # something real to aggregate. ORG_LEARNERS is (name, dept, job_role,
    # competency, gaps, completed, status); gaps/completed are deliberately
    # NOT copied — the view recomputes them from competency_scores and
    # course_enrollments, which is the whole point of the migration.
    for i, (name, dept, job_role, _avg, _gaps, _done, status) in enumerate(db.ORG_LEARNERS):
        user_rows.append((
            f"learner-{i + 2}", name, f"GOV-2018-{1000 + i}", job_role,
            dept, "learner", job_role, "", 0, job_role, "", "English",
            True, status,
        ))

    # Synthetic @sakshamai.demo addresses. Deliberately not real inboxes, so
    # the demo can never send mail to anyone, and deterministic, so
    # scripts/seed_auth_users.py can derive the same address without a lookup
    # table and be safely re-runnable.
    add(insert(
        "users",
        ["id", "email", "name", "employee_id", "designation", "department", "role",
         "target_role", "education", "experience", "career_goal",
         "previous_training", "preferred_language", "profile_completed", "status"],
        [(uid, f"{uid}@sakshamai.demo", *rest) for uid, *rest in user_rows],
    ))

    # -- competency scores -------------------------------------------------
    add("\n-- ------------------------------------------------- default competency levels")
    score_rows: list[tuple] = [
        ("learner-1", cid, lvl) for cid, lvl in db.LEARNER_COMPETENCIES.items()
    ]
    score_rows += [
        ("admin-1", cid, lvl) for cid, lvl in db.ADMIN_COMPETENCIES.items()
    ]
    for i, (name, _dept, job_role, avg, _g, _d, _s) in enumerate(db.ORG_LEARNERS):
        uid = f"learner-{i + 2}"
        for cid, lvl in synth_levels(avg, name, comp_ids).items():
            score_rows.append((uid, cid, lvl))
    add(insert(
        "competency_scores", ["user_id", "competency_id", "level"], score_rows,
    ))

    # -- learner activity --------------------------------------------------
    add("\n-- ------------------------------------------------------- learner activity")
    add(insert(
        "notifications", ["id", "user_id", "message", "type", "date", "is_read"],
        NOTIFICATIONS,
    ))
    add(insert(
        "activities", ["id", "user_id", "action", "detail", "date", "icon"],
        ACTIVITIES,
    ))

    # -- enrolments --------------------------------------------------------
    add("\n-- --------------------------------------------------- enrolments & progress")
    enrol_rows: list[tuple] = []
    module_rows: list[tuple] = []
    for uid, name in (("learner-1", "Ananya Sharma"), ("admin-1", "Dr. Rajesh Kumar")):
        e, m = synth_enrollments(uid, name)
        enrol_rows += e
        module_rows += m
    for i, (name, _dept, _role, _a, _g, _d, _s) in enumerate(db.ORG_LEARNERS):
        e, m = synth_enrollments(f"learner-{i + 2}", name)
        enrol_rows += e
        module_rows += m

    add(insert(
        "course_enrollments", ["user_id", "course_id", "progress", "enrolled_at"],
        enrol_rows,
    ))
    add(insert(
        "module_progress", ["user_id", "course_id", "module_title", "completed_at"],
        module_rows,
    ))

    add(f"""
-- Marks the seed as applied at version {SEED_VERSION}. database.py reads this
-- to decide whether init_db() has work to do, so reference data is not
-- rewritten on every boot or every --reload.
INSERT INTO seed_meta (key, value) VALUES ('version', {q(SEED_VERSION)})
ON CONFLICT (key) DO UPDATE SET value = excluded.value;

COMMIT;
""")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="exit non-zero if the committed file differs from a fresh build")
    args = ap.parse_args()

    sql = build()
    if args.check:
        if not OUT.exists():
            print(f"missing {OUT}", file=sys.stderr)
            return 1
        if OUT.read_text(encoding="utf-8") != sql:
            print(f"{OUT} is stale — run: python3 scripts/export_seed.py", file=sys.stderr)
            return 1
        print(f"{OUT.relative_to(ROOT)} is up to date")
        return 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(sql, encoding="utf-8")
    n_comp = len(db.COMPETENCIES)
    n_role = len(db.ROLE_REQUIREMENTS)
    n_course = len(db.COURSES)
    n_user = 2 + len(db.ORG_LEARNERS)
    print(
        f"wrote {OUT.relative_to(ROOT)}  "
        f"({n_comp} competencies, {n_role} role requirements, "
        f"{n_course} courses, {n_user} users)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
