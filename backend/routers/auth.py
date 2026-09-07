"""Authentication routes (simulated)."""

from fastapi import APIRouter, HTTPException
from database import get_db_connection
from models import LoginRequest

router = APIRouter(prefix="/api/auth", tags=["auth"])


def user_to_dict(row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "employeeId": row["employee_id"],
        "designation": row["designation"],
        "department": row["department"],
        "role": row["role"],
        "currentRole": row["current_role"],
        "education": row["education"],
        "experience": row["experience"],
        "careerGoal": row["career_goal"],
        "previousTraining": row["previous_training"],
        "preferredLanguage": row["preferred_language"],
        "profileCompleted": bool(row["profile_completed"]),
    }


@router.post("/login")
def login(req: LoginRequest):
    """Simulated login: returns the demo user for the requested role."""
    conn = get_db_connection()
    try:
        user_id = "learner-1" if req.role == "learner" else "admin-1"
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="User not found")

        # load competencies
        scores = conn.execute(
            "SELECT cs.competency_id, cs.level, c.name, c.category, c.description FROM competency_scores cs "
            "JOIN competencies c ON c.id = cs.competency_id WHERE cs.user_id = ?",
            (user_id,),
        ).fetchall()
        user = user_to_dict(row)
        user["competencies"] = [
            {"competencyId": s["competency_id"], "level": s["level"],
             "name": s["name"], "category": s["category"], "description": s["description"]}
            for s in scores
        ]
        return {"token": f"demo-token-{user_id}", "user": user}
    finally:
        conn.close()