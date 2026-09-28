"""Course catalogue, enrollment, module completion and competency auto-update routes.

Simulates the mock iGOT Karmayogi + NSSTA APIs. Completing a course module bumps the
linked competencies on the learner profile, which re-runs gap analysis automatically.
"""

import time
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from auth_tokens import (
    Identity,
    current_identity,
    optional_identity,
    require_self_or_admin,
)
from database import get_db_connection
from models import EnrollRequest
from routers.logic import row_to_course

router = APIRouter(prefix="/api", tags=["courses"])


def _assert_may_read(user_id: str, identity: Optional[Identity]) -> None:
    """Enforce self-or-admin for a user-scoped read on a public endpoint."""
    if identity is None:
        raise HTTPException(
            status_code=401, detail="Sign in to view per-user course progress"
        )
    require_self_or_admin(user_id, identity)


@router.get("/courses")
def list_courses(
    user_id: str = "", identity: Optional[Identity] = Depends(optional_identity)
):
    # The catalogue itself stays public so a signed-out landing page can render
    # it, but the optional per-user progress does not: without this check
    # anyone could pass ?user_id=admin-1 and read the administrator's
    # enrolments.
    if user_id:
        _assert_may_read(user_id, identity)
    conn = get_db_connection()
    try:
        rows = conn.execute("SELECT * FROM courses").fetchall()
        enrolled = {}
        if user_id:
            rows_e = conn.execute(
                "SELECT course_id, progress FROM course_enrollments WHERE user_id = %s",
                (user_id,),
            ).fetchall()
            enrolled = {r["course_id"]: r["progress"] for r in rows_e}

        result = []
        for r in rows:
            course = row_to_course(r)
            if r["id"] in enrolled:
                course["enrolled"] = True
                course["progress"] = enrolled[r["id"]]
            result.append(course)
        return result
    finally:
        conn.close()


@router.get("/courses/{course_id}")
def course_detail(
    course_id: str,
    user_id: str = "",
    identity: Optional[Identity] = Depends(optional_identity),
):
    if user_id:
        _assert_may_read(user_id, identity)
    conn = get_db_connection()
    try:
        row = conn.execute(
            "SELECT * FROM courses WHERE id = %s OR course_code = %s",
            (course_id, course_id),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Course not found")
        course = row_to_course(row)
        # Progress and enrolment are keyed on the primary key, not the code the
        # caller may have used, so they are looked up with the resolved id.
        # Passing the raw course_id here made a code-addressed request silently
        # report zero progress and unenrolled, which reads as data loss.
        resolved_id = row["id"]
        if user_id:
            completed = {
                r["module_title"]
                for r in conn.execute(
                    "SELECT module_title FROM module_progress WHERE user_id = %s AND course_id = %s",
                    (user_id, resolved_id),
                ).fetchall()
            }
            for m in course.get("modules", []):
                m["completed"] = m["title"] in completed
            e = conn.execute(
                "SELECT progress FROM course_enrollments WHERE user_id = %s AND course_id = %s",
                (user_id, resolved_id),
            ).fetchone()
            if e:
                course["enrolled"] = True
                course["progress"] = e["progress"]
        return course
    finally:
        conn.close()


@router.post("/courses/enroll")
def enroll(req: EnrollRequest, identity: Identity = Depends(current_identity)):
    # The write below uses `identity.id`, never the body, so a caller cannot
    # enrol somebody else. The field is still checked rather than silently
    # ignored, so a client that sends the wrong id gets told rather than
    # quietly succeeding against the wrong record.
    require_self_or_admin(req.user_id, identity)
    conn = get_db_connection()
    try:
        user = conn.execute("SELECT id FROM users WHERE id = %s", (identity.id,)).fetchone()
        course = conn.execute(
            "SELECT id FROM courses WHERE id = %s OR course_code = %s",
            (req.course_id, req.course_id),
        ).fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")

        conn.execute(
            "INSERT INTO course_enrollments (user_id, course_id, progress) VALUES (%s, %s, 0) "
            "ON CONFLICT (user_id, course_id) DO NOTHING",
            (identity.id, req.course_id),
        )
        conn.commit()
        return {"ok": True, "courseId": req.course_id, "user_id": identity.id}
    finally:
        conn.close()


class ModuleCompleteRequest(BaseModel):
    user_id: str
    course_id: str
    module_title: str
    assessment_score: int = Field(
        default=0,
        ge=0,
        le=5,
        description="Quiz-module score, clamped to the 5 questions a module quiz holds.",
    )


@router.post("/courses/module-complete")
def complete_module(
    req: ModuleCompleteRequest, identity: Identity = Depends(current_identity)
):
    """Mark a module complete; for quiz-type modules, use the assessment score.

    When all modules are done, bumps each linked competency by +1 (max 5),
    updates enrollment progress and logs activity + notification.

    Side effects (quiz attempt, competency bump, activity, notification) run
    only on the *first* completion of a module: module_progress has a primary
    key of (user_id, course_id, module_title), so the progress upsert is
    idempotent, and replaying the request must not re-insert a fabricated quiz
    attempt, re-bump a competency, or spam the feed.
    """
    require_self_or_admin(req.user_id, identity)
    conn = get_db_connection()
    try:
        user = conn.execute("SELECT id FROM users WHERE id = %s", (identity.id,)).fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        course_row = conn.execute(
            "SELECT * FROM courses WHERE id = %s OR course_code = %s",
            (req.course_id, req.course_id),
        ).fetchone()
        if not course_row:
            raise HTTPException(status_code=404, detail="Course not found")

        course = row_to_course(course_row)
        modules = course.get("modules", [])
        matching = [m for m in modules if m["title"] == req.module_title]
        if not matching:
            raise HTTPException(status_code=404, detail="Module not found")

        module = matching[0]
        is_quiz = module.get("type") == "quiz"

        # Record module completion. The PK is (user_id, course_id,
        # module_title), so this is idempotent; rowcount tells us whether this
        # call is the *first* completion, which is the only time side effects
        # below may fire.
        cur = conn.execute(
            "INSERT INTO module_progress (user_id, course_id, module_title, completed_at) "
            "VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING",
            (identity.id, req.course_id, req.module_title, time.strftime("%Y-%m-%d")),
        )
        new_completion = cur.rowcount == 1

        completed_titles = {
            r["module_title"]
            for r in conn.execute(
                "SELECT module_title FROM module_progress WHERE user_id = %s AND course_id = %s",
                (identity.id, req.course_id),
            ).fetchall()
        }
        course_complete = all(m["title"] in completed_titles for m in modules)

        # progress
        total_mods = max(len(modules), 1)
        progress = int((len(completed_titles) / total_mods) * 100)
        conn.execute(
            "UPDATE course_enrollments SET progress = %s WHERE user_id = %s AND course_id = %s",
            (progress, identity.id, req.course_id),
        )

        bumped = []
        if course_complete and new_completion:
            # jsonb: psycopg already returns a list, so json.loads() would
            # raise TypeError and the old except turned that into skills = []
            # — a "completed" course that silently credited no competencies.
            skills = course_row["skills_covered"] or []
            for skill_name in skills:
                comp = conn.execute(
                    "SELECT * FROM competencies WHERE name = %s", (skill_name,)
                ).fetchone()
                if not comp:
                    continue
                comp_id = comp["id"]
                score_row = conn.execute(
                    "SELECT level FROM competency_scores WHERE user_id = %s AND competency_id = %s",
                    (identity.id, comp_id),
                ).fetchone()
                current = score_row["level"] if score_row else 2
                nxt = min(current + 1, 5)
                # Upsert the level only. INSERT OR REPLACE is a DELETE+INSERT,
                # which would reset source/accuracy/self_rated_level/tested_at
                # to their defaults and silently erase the learner's test
                # provenance the moment they completed a course.
                conn.execute(
                    "INSERT INTO competency_scores (user_id, competency_id, level) VALUES (%s, %s, %s) "
                    "ON CONFLICT(user_id, competency_id) DO UPDATE SET level = excluded.level",
                    (identity.id, comp_id, nxt),
                )
                if nxt > current:
                    bumped.append({
                        "id": comp_id,
                        "name": comp["name"],
                        "before": current,
                        "after": nxt,
                    })
                    # Audit trail: distinguishes a level earned by finishing a
                    # course from one earned by passing the competency test.
                    conn.execute(
                        "INSERT INTO score_update_log "
                        "(user_id, competency_id, previous_level, new_level, source, reference_id) "
                        "VALUES (%s, %s, %s, %s, 'course', %s)",
                        (identity.id, comp_id, current, nxt, req.course_id),
                    )

            conn.execute(
                "INSERT INTO activities (id, user_id, action, detail, date, icon) VALUES (%s, %s, %s, %s, %s, %s)",
                (
                    f"act-{uuid.uuid4().hex[:8]}",
                    identity.id,
                    "Completed Course",
                    f"{course['title']} - all modules completed",
                    time.strftime("%Y-%m-%d"),
                    "✅",
                ),
            )
            if bumped:
                conn.execute(
                    "INSERT INTO notifications (id, user_id, message, type, date, is_read) VALUES (%s, %s, %s, %s, %s, %s)",
                    (
                        f"ntr-{uuid.uuid4().hex[:8]}",
                        identity.id,
                        "Skill improved! " + ", ".join(
                            f"{b['name']}: Level {b['before']} → {b['after']}" for b in bumped
                        ),
                        "success",
                        time.strftime("%Y-%m-%d"),
                        False,
                    ),
                )

        # If module was a quiz, also record the quiz attempt — once, on the
        # first completion only (replay would keep punching fabricated
        # attempts into quiz history).
        if is_quiz and new_completion:
            quiz_id = f"quiz-{uuid.uuid4().hex[:8]}"
            conn.execute(
                "INSERT INTO quizzes (id, user_id, title, date, score, total_questions) VALUES (%s, %s, %s, %s, %s, %s)",
                (
                    quiz_id,
                    identity.id,
                    f"{course['title']} - {req.module_title}",
                    time.strftime("%Y-%m-%d"),
                    req.assessment_score,
                    5,
                ),
            )

        conn.commit()

        return {
            "ok": True,
            "courseComplete": course_complete,
            "progress": progress,
            "bumped": bumped,
        }
    finally:
        conn.close()


# Mock iGOT Karmayogi API — echoes the catalogue in a realistic "external API" shape
@router.get("/igot/courses")
def igot_courses():
    """Simulates an external iGOT Karmayogi API response."""
    conn = get_db_connection()
    try:
        rows = conn.execute("SELECT * FROM courses WHERE provider = 'iGOT Karmayogi'").fetchall()
        return {
            "source": "MOCK iGOT Karmayogi API",
            "count": len(rows),
            "courses": [row_to_course(r) for r in rows],
        }
    finally:
        conn.close()