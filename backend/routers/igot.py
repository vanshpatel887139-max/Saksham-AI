"""Personalized iGOT Karmayogi Learning Plan.

Grafts the Karmayogi upskilling concept onto SakshamAI: given a learner's skill
gaps and the real course catalogue, generate a week-by-week career plan. Uses
the LLM when available and falls back to a deterministic plan built from the
same database rows so the feature always works.
"""

import json
from fastapi import APIRouter
from pydantic import BaseModel

from database import get_db_connection
from llm import LLMUnavailableError, llm_available, model_name, system, user, chat, extract_json
from routers.logic import row_to_course

router = APIRouter(prefix="/api/igot", tags=["igot"])

DEFAULT_WEEKS = 2
MAX_WEEKS = 8


class PlanRequest(BaseModel):
    user_id: str = "learner-1"
    target_role: str = ""
    weeks: int = DEFAULT_WEEKS
    language: str = "English"


def _gaps_and_courses(db, user_id: str, target_role: str):
    user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        return None, None, None
    role = target_role or user["current_role"] or "Data Analyst"

    scores = {
        r["competency_id"]: r["level"]
        for r in db.execute(
            "SELECT competency_id, level FROM competency_scores WHERE user_id = ?", (user_id,)
        ).fetchall()
    }
    rows = db.execute(
        "SELECT competency_id, level FROM role_requirements WHERE role = ?", (role,)
    ).fetchall()
    gaps = []
    for r in rows:
        gap = max(0, r["level"] - scores.get(r["competency_id"], 0))
        if gap > 0:
            comp = db.execute(
                "SELECT name FROM competencies WHERE id = ?", (r["competency_id"],)
            ).fetchone()
            gaps.append({
                "competency": comp["name"],
                "current": scores.get(r["competency_id"], 0),
                "required": r["level"],
                "gap": gap,
            })
    gaps.sort(key=lambda g: -g["gap"])

    courses = [row_to_course(r) for r in db.execute(
        "SELECT * FROM courses WHERE provider IN ('iGOT Karmayogi', 'NSSTA') ORDER BY title"
    ).fetchall()]
    return role, gaps, courses


def _catalogue_text(courses) -> str:
    return "\n".join(
        f"- {c['courseCode']} | {c['title']} | {c['provider']} | skills: {', '.join(c['skillsCovered'])} | modules: {len(c['modules'])}"
        for c in courses
    )


def _plan_from_llm(role: str, gaps: list, courses: list, weeks: int, language: str) -> dict:
    gaps_txt = "\n".join(
        f"- {g['competency']} (current {g['current']}, required {g['required']}, gap {g['gap']})"
        for g in gaps[:6]
    ) or "- none"
    schema_prompt = (
        'Respond ONLY with JSON, no prose. Schema:\n'
        '{"title":"...","summary":"...",'
        '"focusAreas":[{"competency":"...","gap":2,"recommendation":"..."}],'
        '"weeks":[{"week":1,"theme":"...","courses":[{"courseId":"...","title":"...","courseCode":"...",'
        '"provider":"iGOT Karmayogi","action":"Start modules 1-2"}],"practice":"...","assessment":"...",'
        '"outcome":"..."}],'
        '"certPath":["..."]}\n'
        f"Produce exactly {weeks} weeks. Use ONLY courseCode values from the catalogue; "
        "if a gap has no matching course, reference the app's Quiz Generator or Virtual Labs "
        "in practice/assessment instead of inventing a course."
    )
    messages = [
        system(
            "You are a Karmayogi career planner for India's official statistical system. "
            "You create grounded, week-by-week upskilling plans from real skill gaps and the "
            "real iGOT Karmayogi / NSSTA course catalogue. Be practical and specific."
        ),
        user(
            f"Target role: {role}\nSkill gaps:\n{gaps_txt}\n\n"
            f"Catalogue (ONLY these courses may be referenced):\n{_catalogue_text(courses)}\n\n"
            f"Plan duration: {weeks} week(s). Language of content: {language}.\n\nTASK:\n{schema_prompt}"
        ),
    ]
    raw = chat(messages, json_mode=True, temperature=0.4, max_tokens=3000)
    data = extract_json(raw)
    return _validate_plan(data, weeks)


def _validate_plan(data: dict, weeks: int) -> dict:
    if not isinstance(data, dict) or not isinstance(data.get("weeks"), list):
        raise LLMUnavailableError("Invalid plan JSON")
    out = {"title": str(data.get("title", "iGOT Karmayogi Learning Plan")),
           "summary": str(data.get("summary", "")),
           "focusAreas": data.get("focusAreas", []),
           "certPath": data.get("certPath", []),
           "weeks": []}
    for i, w in enumerate(data["weeks"][:weeks], start=1):
        if not isinstance(w, dict):
            continue
        course_list = []
        for c in w.get("courses", [])[:6]:
            if isinstance(c, dict) and c.get("courseCode"):
                course_list.append({
                    "courseId": str(c.get("courseId", "")),
                    "title": str(c.get("title", "")),
                    "courseCode": str(c.get("courseCode", "")),
                    "provider": str(c.get("provider", "iGOT Karmayogi")),
                    "action": str(c.get("action", "")),
                })
        out["weeks"].append({
            "week": i,
            "theme": str(w.get("theme", f"Week {i}")),
            "courses": course_list,
            "practice": str(w.get("practice", "")),
            "assessment": str(w.get("assessment", "")),
            "outcome": str(w.get("outcome", "")),
        })
    if len(out["weeks"]) != weeks:
        raise LLMUnavailableError("Plan week count mismatch")
    return out


def _plan_from_rules(role: str, gaps: list, courses: list, weeks: int) -> dict:
    """Deterministic fallback plan mapped over the real catalogue."""
    top = gaps[:weeks] or [{"competency": "Statistical Analysis", "gap": 1}]
    plan_weeks = []
    for i, g in enumerate(top, start=1):
        matches = [c for c in courses if g["competency"] in c["skillsCovered"]]
        course_list = [
            {
                "courseId": c["id"],
                "title": c["title"],
                "courseCode": c["courseCode"],
                "provider": c["provider"],
                "action": "Enroll and complete all modules",
            }
            for c in matches[:2]
        ]
        if not course_list:
            course_list = [{
                "courseId": "",
                "title": "Micro-learning via Quiz Generator + Virtual Labs",
                "courseCode": "APP-PRACTICE",
                "provider": "SakshamAI",
                "action": "Daily micro-assessments from uploaded material",
            }]
        plan_weeks.append({
            "week": i,
            "theme": f"Master {g['competency']}",
            "courses": course_list,
            "practice": f"45 min/day on {g['competency']} modules; use Virtual Labs sandboxes.",
            "assessment": "Complete 2 micro-assessments from the Quiz Generator.",
            "outcome": f"Close the {g['gap']}-level gap on {g['competency']}.",
        })
    return {
        "title": f"iGOT Karmayogi Learning Plan for {role}",
        "summary": f"A {weeks}-week plan built from your current skill gaps.",
        "focusAreas": [{"competency": g["competency"], "gap": g["gap"], "recommendation": "Prioritize iGOT/NSSTA modules covering this competency"} for g in top],
        "certPath": [f"iGOT module completion - {g['competency']}" for g in top],
        "weeks": plan_weeks,
    }


@router.post("/plan")
def generate_plan(req: PlanRequest):
    weeks = max(1, min(int(req.weeks or DEFAULT_WEEKS), MAX_WEEKS))
    db = get_db_connection()
    try:
        role, gaps, courses = _gaps_and_courses(db, req.user_id, req.target_role)
    finally:
        db.close()
    if not role:
        return {"title": "Plan unavailable", "summary": "User not found", "focusAreas": [], "weeks": [], "certPath": [], "source": "rule", "model": ""}

    source = "rule"
    model = ""
    plan = None
    if llm_available():
        try:
            plan = _plan_from_llm(role, gaps, courses, weeks, req.language)
            source = "llm"
            model = model_name()
        except (LLMUnavailableError, ValueError):
            plan = None
    if plan is None:
        plan = _plan_from_rules(role, gaps, courses, weeks)

    plan["source"] = source
    plan["model"] = model
    return plan