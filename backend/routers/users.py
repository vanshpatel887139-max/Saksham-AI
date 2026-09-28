"""User profile routes."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from auth_tokens import (
    Identity,
    current_identity,
    delete_auth_account,
    invalidate_auth_cache,
    require_self_or_admin,
)
from database import get_db_connection
from models import DeleteAccountRequest, ProfileUpdate, CompetencyUpdate

router = APIRouter(prefix="/api/users", tags=["users"])

# Every table that holds data about a specific person. Deletion walks this list
# explicitly rather than relying only on ON DELETE CASCADE, because an erasure
# guarantee should not depend on a foreign key definition staying correct in a
# future migration. Anything added to the schema without a CASCADE and without
# being listed here would silently survive deletion, so this list is asserted
# against the live schema by the privacy test suite.
_USER_SCOPED_TABLES = (
    "advisor_messages",
    "score_update_log",
    "activities",
    "notifications",
    "module_progress",
    "course_enrollments",
    "assessment_questions",
    "competency_scores",
    "quizzes",  # quiz_questions cascade from this
)


# The exact columns this module is allowed to read out of `users`, and the only
# set that should be passed to user_to_dict().
#
# `users` also holds `email`, `auth_id` and `status`. Those are excluded on
# purpose. A `SELECT *` here would fetch all three and rely on the serializer
# below remembering to drop them, so any future column added to the table
# (a phone number, a date of birth, a device id) would start flowing straight
# into an API response the moment this query was used. Naming the columns
# makes that a compile-time-visible decision instead: new PII is not published
# until someone adds it here.
#
# The serializer is a second, independent allowlist; a caller must satisfy both.
USER_PROFILE_COLUMNS = (
    "id, name, employee_id, designation, department, role, target_role, "
    "education, experience, career_goal, previous_training, "
    "preferred_language, profile_completed"
)


def fetch_user(conn, user_id: str):
    """Load one user by id, restricted to USER_PROFILE_COLUMNS."""
    return conn.execute(
        f"SELECT {USER_PROFILE_COLUMNS} FROM users WHERE id = %s", (user_id,)
    ).fetchone()


def user_to_dict(row, conn) -> dict:
    user = {
        "id": row["id"],
        "name": row["name"],
        "employeeId": row["employee_id"],
        "designation": row["designation"],
        "department": row["department"],
        "role": row["role"],
        "currentRole": row["target_role"],
        "education": row["education"],
        "experience": row["experience"],
        "careerGoal": row["career_goal"],
        "previousTraining": row["previous_training"],
        "preferredLanguage": row["preferred_language"],
        "profileCompleted": bool(row["profile_completed"]),
    }
    scores = conn.execute(
        "SELECT cs.competency_id, cs.level, cs.source, cs.accuracy, cs.self_rated_level, cs.tested_at, "
        "c.name, c.category, c.description FROM competency_scores cs "
        "JOIN competencies c ON c.id = cs.competency_id WHERE cs.user_id = %s",
        (row["id"],),
    ).fetchall()
    user["competencies"] = [
        {"competencyId": s["competency_id"], "level": s["level"],
         "source": s["source"] or "default",
         "accuracy": s["accuracy"],
         "selfRatedLevel": s["self_rated_level"],
         "testedAt": s["tested_at"],
         "name": s["name"], "category": s["category"], "description": s["description"]}
        for s in scores
    ]
    # Provenance for the most recent automated test, so the results view can
    # show "Last assessed on ..." and the per-question breakdown.
    # Only the latest test is kept per user, so taken_at alone is the ordering key.
    latest = conn.execute(
        "SELECT test_id, MAX(taken_at) AS taken_at FROM assessment_questions "
        "WHERE user_id = %s GROUP BY test_id ORDER BY taken_at DESC LIMIT 1",
        (row["id"],),
    ).fetchone()
    if latest:
        user["testMeta"] = {
            "testId": latest["test_id"],
            "takenAt": latest["taken_at"],
        }
        user["assessmentQuestions"] = [
            {
                "position": q["position"],
                "questionId": q["question_id"],
                "competencyId": q["competency_id"],
                "competencyName": q["competency_name"] or q["competency_id"],
                "prompt": q["prompt"],
                "options": q["options"] or [],
                "correctIndex": q["correct_index"],
                "chosenIndex": q["chosen_index"],
                "difficulty": q["difficulty"],
                "explanation": q["explanation"] or "",
            }
            for q in conn.execute(
                "SELECT * FROM assessment_questions WHERE user_id = %s AND test_id = %s ORDER BY position",
                (row["id"], latest["test_id"]),
            ).fetchall()
        ]
    return user


@router.get("/{user_id}")
def get_user(user_id: str, identity: Identity = Depends(current_identity)):
    # Without this, GET /api/users/admin-1 returned the administrator's full
    # profile — competency levels, assessment history, everything — to an
    # anonymous caller, and GET /api/users/learner-2 to any learner.
    require_self_or_admin(user_id, identity)
    conn = get_db_connection()
    try:
        row = fetch_user(conn, user_id)
        if not row:
            raise HTTPException(status_code=404, detail="User not found")
        return user_to_dict(row, conn)
    finally:
        conn.close()


@router.put("/{user_id}")
def update_user(
    user_id: str,
    updates: ProfileUpdate,
    identity: Identity = Depends(current_identity),
):
    require_self_or_admin(user_id, identity)
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT id FROM users WHERE id = %s", (user_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="User not found")

        fields = {
            "name": updates.name, "employee_id": updates.employeeId,
            "designation": updates.designation, "department": updates.department,
            "target_role": updates.currentRole, "education": updates.education,
            "experience": updates.experience, "career_goal": updates.careerGoal,
            "previous_training": updates.previousTraining,
            "preferred_language": updates.preferredLanguage,
            "profile_completed": updates.profileCompleted,
        }
        sets = []
        params = []
        for col, val in fields.items():
            if val is not None:
                sets.append(f"{col} = %s")
                params.append(val)

        if not sets:
            # Nothing to change. Without this the statement below assembles to
            # "UPDATE users SET  WHERE id = %s", which is a syntax error rather
            # than a no-op, so a save with no edited fields 500s instead of
            # quietly succeeding. `ProfileUpdate` marks every field optional, so
            # an empty body is a legitimate request, not a malformed one.
            return user_to_dict(fetch_user(conn, user_id), conn)

        params.append(user_id)
        conn.execute(f"UPDATE users SET {', '.join(sets)} WHERE id = %s", params)
        conn.commit()

        return user_to_dict(fetch_user(conn, user_id), conn)
    finally:
        conn.close()


@router.put("/{user_id}/competencies")
def update_competencies(
    user_id: str,
    payload: CompetencyUpdate,
    identity: Identity = Depends(current_identity),
):
    require_self_or_admin(user_id, identity)
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT id FROM users WHERE id = %s", (user_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="User not found")

        # Upsert only, never a blanket delete: a retake covers a subset of
        # competencies, so anything the caller omits must keep its level *and*
        # its provenance. Competencies are static reference data seeded at
        # init, so there is no legitimate need to remove a row here.
        known = {
            r["id"]
            for r in conn.execute("SELECT id FROM competencies").fetchall()
        }
        skipped: List[str] = []
        for cs in payload.competencies:
            # competency_id is a foreign key. A stale or hand-made payload can
            # name an id that is not in the reference table; skip it rather
            # than letting the constraint abort the whole request.
            if cs.competencyId not in known:
                skipped.append(cs.competencyId)
                continue
            conn.execute(
                "INSERT INTO competency_scores "
                "(user_id, competency_id, level, source, accuracy, self_rated_level, tested_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (user_id, competency_id) DO UPDATE SET "
                "level = EXCLUDED.level, source = EXCLUDED.source, "
                "accuracy = EXCLUDED.accuracy, self_rated_level = EXCLUDED.self_rated_level, "
                "tested_at = EXCLUDED.tested_at",
                (
                    user_id,
                    cs.competencyId,
                    cs.level,
                    cs.source or "default",
                    cs.accuracy,
                    cs.selfRatedLevel,
                    cs.testedAt,
                ),
            )
        conn.commit()

        payload_out = user_to_dict(fetch_user(conn, user_id), conn)
        if skipped:
            payload_out["skippedCompetencyIds"] = skipped
        return payload_out
    finally:
        conn.close()


def _count_user_rows(conn, user_id: str) -> dict:
    """Rows held about this person, per table, before anything is removed.

    Returned to the caller as a receipt. An erasure request that answers
    "here is exactly what was removed" is verifiable by the person making it,
    which is the point of a right-to-erasure flow.
    """
    counts = {}
    for table in _USER_SCOPED_TABLES:
        counts[table] = conn.execute(
            f"SELECT COUNT(*) AS n FROM {table} WHERE user_id = %s", (user_id,)
        ).fetchone()["n"]
    return counts


def _erase_user(conn, user_id: str) -> dict:
    """Delete every row about one person. Returns the per-table receipt.

    Child rows are removed before the parent, inside the caller's transaction,
    so a failure part-way through rolls back rather than leaving a half-erased
    profile. No tombstone row is kept: retaining an anonymised shell would
    still be personal data, and the user asked for removal.
    """
    receipt = _count_user_rows(conn, user_id)
    for table in _USER_SCOPED_TABLES:
        conn.execute(f"DELETE FROM {table} WHERE user_id = %s", (user_id,))
    conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
    return receipt


def _delete_account(
    user_id: str, identity: Identity, payload: DeleteAccountRequest
) -> dict:
    """Shared implementation for self-service and admin-initiated erasure."""
    if (payload.confirmation or "").strip().upper() != "DELETE":
        raise HTTPException(
            status_code=400,
            detail=(
                "This permanently erases the account and all associated data. "
                "Send confirmation='DELETE' to proceed."
            ),
        )

    # Guard against the last administrator being removed, which would lock
    # everyone out of the admin dashboard with no way back in through the UI.
    # This must consider self-deletion too: an admin using the self-service
    # route is the most likely way the last admin disappears, so scoping this
    # to "admin deleting somebody else" would miss the common case entirely.
    conn = get_db_connection()
    try:
        target = conn.execute(
            "SELECT role FROM users WHERE id = %s", (user_id,)
        ).fetchone()
        if not target:
            raise HTTPException(status_code=404, detail="User not found")
        if target["role"] == "admin":
            remaining = conn.execute(
                "SELECT COUNT(*) AS n FROM users WHERE role = 'admin' AND id <> %s",
                (user_id,),
            ).fetchone()["n"]
            if remaining == 0:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "Refusing to delete the only remaining administrator. "
                        "Promote another account to admin first."
                    ),
                )
    finally:
        conn.close()

    # Read auth_id before the row goes away. The Supabase Auth identity is a
    # separate record; deleting only the application row would leave a live
    # credential that can still sign in.
    conn = get_db_connection()
    try:
        row = conn.execute(
            "SELECT auth_id FROM users WHERE id = %s", (user_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="User not found")
        auth_id = row["auth_id"]
        receipt = _erase_user(conn, user_id)
        conn.commit()
    finally:
        conn.close()

    # The auth_id -> learner row mapping is cached for 30s; without this the
    # next request from a just-deleted session would still resolve.
    invalidate_auth_cache()

    auth_result, auth_detail = (True, "not linked")
    if auth_id:
        auth_result, auth_detail = delete_auth_account(str(auth_id))
    else:
        auth_detail = "account was not linked to Supabase Auth"

    return {
        "deleted": True,
        "userId": user_id,
        "rowsRemoved": receipt,
        "totalRowsRemoved": sum(receipt.values()) + 1,  # +1 for the users row
        "authAccountRemoved": auth_result,
        "authAccountDetail": auth_detail,
        "note": (
            "All learning records, assessment history, quiz attempts, progress, "
            "notifications and advisor chat for this account have been deleted. "
            "This cannot be undone."
        ),
    }


@router.delete("/me")
def delete_my_account(
    payload: DeleteAccountRequest,
    identity: Identity = Depends(current_identity),
):
    """Erase the caller's own account and every row held about them.

    Self-service right to erasure. Ownership is taken from the verified token,
    not from the request, so this can only ever delete the caller's own data.
    """
    return _delete_account(identity.id, identity, payload)


@router.delete("/{user_id}")
def delete_user(
    user_id: str,
    payload: DeleteAccountRequest,
    identity: Identity = Depends(current_identity),
):
    """Administrator-initiated erasure of another account."""
    require_self_or_admin(user_id, identity)
    return _delete_account(user_id, identity, payload)
