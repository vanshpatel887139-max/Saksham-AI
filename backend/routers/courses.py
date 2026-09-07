"""Course catalogue, enrollment, module completion and competency auto-update routes.

Simulates the mock iGOT Karmayogi + NSSTA APIs. Completing a course module bumps the
linked competencies on the learner profile, which re-runs gap analysis automatically.
"""

import json
import time
import uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from database import get_db_connection
from models import EnrollRequest
from routers.logic import row_to_course

router = APIRouter(prefix="/api", tags=["courses"])


@router.get("/courses")
def list_courses(user_id: str = ""):
    conn = get_db_connection()
    try:
        rows = conn.execute("SELECT * FROM courses").fetchall()
        enrolled = {}
        if user_id:
            rows_e = conn.execute(
                "SELECT course_id, progress FROM course_enrollments WHERE user_id = ?",
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
def course_detail(course_id: str, user_id: str = ""):
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT * FROM courses WHERE id = ?", (course_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Course not found")
        course = row_to_course(row)
        if user_id:
            completed = {
                r["module_title"]
                for r in conn.execute(
                    "SELECT module_title FROM module_progress WHERE user_id = ? AND course_id = ?",
                    (user_id, course_id),
                ).fetchall()
            }
            for m in course.get("modules", []):
                m["completed"] = m["title"] in completed
            e = conn.execute(
                "SELECT progress FROM course_enrollments WHERE user_id = ? AND course_id = ?",
                (user_id, course_id),
            ).fetchone()
            if e:
                course["enrolled"] = True
                course["progress"] = e["progress"]
        return course
    finally:
        conn.close()


@router.post("/courses/enroll")
def enroll(req: EnrollRequest):
    conn = get_db_connection()
    try:
        user = conn.execute("SELECT id FROM users WHERE id = ?", (req.user_id,)).fetchone()
        course = conn.execute("SELECT id FROM courses WHERE id = ?", (req.course_id,)).fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")

        conn.execute(
            "INSERT OR IGNORE INTO course_enrollments (user_id, course_id, progress) VALUES (?, ?, 0)",
            (req.user_id, req.course_id),
        )
        conn.commit()
        return {"ok": True, "courseId": req.course_id, "user_id": req.user_id}
    finally:
        conn.close()


class ModuleCompleteRequest(BaseModel):
    user_id: str
    course_id: str
    module_title: str
    assessment_score: int = 0


@router.post("/courses/module-complete")
def complete_module(req: ModuleCompleteRequest):
    """Mark a module complete; for quiz-type modules, use the assessment score.

    When all modules are done, bumps each linked competency by +1 (max 5),
    updates enrollment progress and logs activity + notification.
    """
    conn = get_db_connection()
    try:
        user = conn.execute("SELECT id FROM users WHERE id = ?", (req.user_id,)).fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        course_row = conn.execute(
            "SELECT * FROM courses WHERE id = ?", (req.course_id,)
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

        # Record module completion
        conn.execute(
            "INSERT OR IGNORE INTO module_progress (user_id, course_id, module_title, completed_at) VALUES (?, ?, ?, ?)",
            (req.user_id, req.course_id, req.module_title, time.strftime("%Y-%m-%d")),
        )

        completed_titles = {
            r["module_title"]
            for r in conn.execute(
                "SELECT module_title FROM module_progress WHERE user_id = ? AND course_id = ?",
                (req.user_id, req.course_id),
            ).fetchall()
        }
        course_complete = all(m["title"] in completed_titles for m in modules)

        # progress
        total_mods = max(len(modules), 1)
        progress = int((len(completed_titles) / total_mods) * 100)
        conn.execute(
            "UPDATE course_enrollments SET progress = ? WHERE user_id = ? AND course_id = ?",
            (progress, req.user_id, req.course_id),
        )

        bumped = []
        if course_complete:
            try:
                skills = json.loads(course_row["skills_covered"])
            except (json.JSONDecodeError, TypeError):
                skills = []
            for skill_name in skills:
                comp = conn.execute(
                    "SELECT * FROM competencies WHERE name = ?", (skill_name,)
                ).fetchone()
                if not comp:
                    continue
                comp_id = comp["id"]
                score_row = conn.execute(
                    "SELECT level FROM competency_scores WHERE user_id = ? AND competency_id = ?",
                    (req.user_id, comp_id),
                ).fetchone()
                current = score_row["level"] if score_row else 2
                nxt = min(current + 1, 5)
                conn.execute(
                    "INSERT OR REPLACE INTO competency_scores (user_id, competency_id, level) VALUES (?, ?, ?)",
                    (req.user_id, comp_id, nxt),
                )
                if nxt > current:
                    bumped.append({
                        "id": comp_id,
                        "name": comp["name"],
                        "before": current,
                        "after": nxt,
                    })

            conn.execute(
                "INSERT INTO activities (id, user_id, action, detail, date, icon) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    f"act-{uuid.uuid4().hex[:8]}",
                    req.user_id,
                    "Completed Course",
                    f"{course['title']} - all modules completed",
                    time.strftime("%Y-%m-%d"),
                    "✅",
                ),
            )
            if bumped:
                conn.execute(
                    "INSERT INTO notifications (id, user_id, message, type, date, is_read) VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        f"ntr-{uuid.uuid4().hex[:8]}",
                        req.user_id,
                        "Skill improved! " + ", ".join(
                            f"{b['name']}: Level {b['before']} → {b['after']}" for b in bumped
                        ),
                        "success",
                        time.strftime("%Y-%m-%d"),
                        0,
                    ),
                )

        # If module was a quiz, also record the quiz attempt
        if is_quiz:
            quiz_id = f"quiz-{uuid.uuid4().hex[:8]}"
            conn.execute(
                "INSERT INTO quizzes (id, user_id, title, date, score, total_questions) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    quiz_id,
                    req.user_id,
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