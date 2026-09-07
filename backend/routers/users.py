"""User profile routes."""

from fastapi import APIRouter, HTTPException
from database import get_db_connection
from models import ProfileUpdate, CompetencyUpdate

router = APIRouter(prefix="/api/users", tags=["users"])


def user_to_dict(row, conn) -> dict:
    user = {
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
    scores = conn.execute(
        "SELECT cs.competency_id, cs.level, c.name, c.category, c.description FROM competency_scores cs "
        "JOIN competencies c ON c.id = cs.competency_id WHERE cs.user_id = ?",
        (row["id"],),
    ).fetchall()
    user["competencies"] = [
        {"competencyId": s["competency_id"], "level": s["level"],
         "name": s["name"], "category": s["category"], "description": s["description"]}
        for s in scores
    ]
    return user


@router.get("/{user_id}")
def get_user(user_id: str):
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="User not found")
        return user_to_dict(row, conn)
    finally:
        conn.close()


@router.put("/{user_id}")
def update_user(user_id: str, updates: ProfileUpdate):
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="User not found")

        fields = {
            "name": updates.name, "employee_id": updates.employeeId,
            "designation": updates.designation, "department": updates.department,
            "current_role": updates.currentRole, "education": updates.education,
            "experience": updates.experience, "career_goal": updates.careerGoal,
            "previous_training": updates.previousTraining,
            "preferred_language": updates.preferredLanguage,
            "profile_completed": updates.profileCompleted,
        }
        sets = []
        params = []
        for col, val in fields.items():
            if val is not None:
                sets.append(f"{col} = ?")
                # SQLite doesn't have native booleans; store as 0/1
                if isinstance(val, bool):
                    val = 1 if val else 0
                params.append(val)
        params.append(user_id)
        conn.execute(f"UPDATE users SET {', '.join(sets)} WHERE id = ?", params)
        conn.commit()

        updated = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return user_to_dict(updated, conn)
    finally:
        conn.close()


@router.put("/{user_id}/competencies")
def update_competencies(user_id: str, payload: CompetencyUpdate):
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="User not found")

        # reset existing scores for this user
        conn.execute("DELETE FROM competency_scores WHERE user_id = ?", (user_id,))
        for cs in payload.competencies:
            conn.execute(
                "INSERT OR REPLACE INTO competency_scores (user_id, competency_id, level) VALUES (?, ?, ?)",
                (user_id, cs.competencyId, cs.level),
            )
        conn.commit()

        updated = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return user_to_dict(updated, conn)
    finally:
        conn.close()