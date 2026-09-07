"""Competency framework & skill-gap routes."""

from fastapi import APIRouter
from database import get_db_connection
from models import GapRequest
from routers.logic import calculate_skill_gaps, get_recommended_courses

router = APIRouter(prefix="/api", tags=["competency"])


@router.get("/competencies")
def list_competencies():
    conn = get_db_connection()
    try:
        rows = conn.execute("SELECT * FROM competencies").fetchall()
        return [
            {"id": r["id"], "name": r["name"], "category": r["category"], "description": r["description"]}
            for r in rows
        ]
    finally:
        conn.close()


@router.get("/roles")
def list_roles():
    conn = get_db_connection()
    try:
        rows = conn.execute("SELECT DISTINCT role FROM role_requirements").fetchall()
        return [{"role": r["role"]} for r in rows]
    finally:
        conn.close()


@router.get("/roles/{role}/requirements")
def role_requirements(role: str):
    conn = get_db_connection()
    try:
        rows = conn.execute(
            "SELECT rr.competency_id, rr.level, c.name, c.category "
            "FROM role_requirements rr JOIN competencies c ON c.id = rr.competency_id WHERE rr.role = ?",
            (role,),
        ).fetchall()
        return {
            "role": role,
            "requirements": [
                {"competencyId": r["competency_id"], "level": r["level"],
                 "name": r["name"], "category": r["category"]}
                for r in rows
            ],
        }
    finally:
        conn.close()


@router.post("/assessment/gaps")
def assess_gaps(req: GapRequest):
    conn = get_db_connection()
    try:
        gaps = calculate_skill_gaps(conn.cursor(), [c.model_dump() for c in req.competencies], req.role)
        courses = get_recommended_courses(conn.cursor(), gaps)
        top_gaps = [g for g in gaps if g["priority"] in ("High", "Medium")][:3]
        return {
            "role": req.role,
            "gaps": gaps,
            "topGaps": top_gaps,
            "recommendedCourses": courses,
        }
    finally:
        conn.close()