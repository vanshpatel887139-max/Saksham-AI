"""One round trip for everything the dashboard draws.

    GET /api/dashboard

WHY THIS EXISTS
The dashboard previously showed a mixture of real and invented numbers, and
the invented ones were the ones a reviewer notices. Learning hours was the
literal 24. The streak was the literal "7 days". The learning-pathway bars
were 33/0/0. The activity feed was `mockActivities` even though the database
had a populated `activities` table, and the notification banner was a
hardcoded sentence that happened to be a copy of notification n1.

The underlying rows all existed. Nothing read them. This route reads them, so
the dashboard has a single source of truth and adding a column to a table
changes what the card shows without a second edit in the frontend.

WHAT IS COMPUTED RATHER THAN STORED
`streak` and the pathway percentages are derived here instead of being written
back, because a stored aggregate is a claim that stops being true the moment
an activity is inserted. Deriving on read costs three small indexed queries.

STREAK SEMANTICS, AND WHY `streakAsOf` EXISTS
A streak is consecutive calendar days with at least one recorded event, ending
today. The seeded rows carry 2025 dates, so a prototype that has not been
touched since seeding reports a streak of 0 — which is the correct answer, and
is exactly why the honest response is to return `streakAsOf` alongside it. The
UI can then say "no activity since 2025-09-01" instead of implying the learner
has been inactive today when in fact the data is simply stale. Suppressing the
zero to make the demo look better would be the same bug as the literal it
replaces.

AUTHORISATION
The caller's own row is the only row read: the user id comes from the verified
session via `current_identity` and is never taken from the query string, so
there is no way to ask for someone else's feed. Reads never commit, so this
route has no write path.
"""

import datetime
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from fastapi import APIRouter, Depends

from auth_tokens import Identity, current_identity
from database import get_db_connection

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

# The three pathway bands, keyed by the level `role_requirements` demands.
# Naming them after the required level rather than a hand-picked list of
# competencies means a role added to `role_requirements` gets a sensible
# pathway with no code change here.
PATHWAY_BANDS = [
    ("Foundation", 1, 2),
    ("Role-Specific Skills", 3, 3),
    ("Advanced & Future", 4, 5),
]

# How many items the dashboard actually renders. The tables are unbounded in
# principle — `activities` grows with every enrolment — so the route caps the
# feed instead of shipping a learner's whole history to render five rows.
FEED_LIMIT = 8


def _parse_date(value: Optional[str]):
    """Parse a stored `YYYY-MM-DD` date, tolerating None and junk.

    `activities.date` and `module_progress.completed_at` are TEXT columns, so
    a malformed value is a real possibility rather than a hypothetical one. A
    bad row is skipped instead of taking the whole dashboard down with a 500.
    """
    if not value:
        return None
    try:
        parsed = time.strptime(str(value)[:10], "%Y-%m-%d")
    except ValueError:
        return None
    # A (year, month, day) tuple rather than the struct_time itself: the caller
    # formats this straight into a date string, and iterating a struct_time
    # would splice all nine of its fields into the output.
    return (parsed.tm_year, parsed.tm_mon, parsed.tm_mday)


def _streak(dates: set[tuple[int, int, int]], today: tuple[int, int, int]) -> int:
    """Consecutive days of activity ending today, 0 if today is inactive."""
    if today not in dates:
        return 0
    streak = 0
    day = datetime.date(*today)
    while (day.year, day.month, day.day) in dates:
        streak += 1
        day -= datetime.timedelta(days=1)
    return streak


def _pathway(role: Optional[str], meets: Optional[set[str]], reqs) -> list[dict]:
    """Per-band progress toward the target role's required levels.

    Each band's progress is the share of that band's competencies where the
    learner already meets or beats the level the role asks for. An empty band
    (a role with no level-4 requirements) reports 0 rather than being dropped,
    so the card keeps its three rows and the layout does not shift.
    """
    if not role:
        return [{"stage": name, "progress": 0, "met": 0, "total": 0} for name, _, _ in PATHWAY_BANDS]

    total_by_competency: dict[str, int] = {}
    for row in reqs:
        total_by_competency[row["competency_id"]] = max(
            total_by_competency.get(row["competency_id"], 0), row["level"]
        )

    stages = []
    for name, lo, hi in PATHWAY_BANDS:
        band = {cid: lvl for cid, lvl in total_by_competency.items() if lo <= lvl <= hi}
        met = sum(1 for cid, lvl in band.items() if cid in (meets or set()))
        stages.append(
            {
                "stage": name,
                "progress": round(met / len(band) * 100) if band else 0,
                "met": met,
                "total": len(band),
            }
        )
    return stages


# The dashboard's reads are split into four independent groups that run on
# their own pooled connection and finish concurrently. Issuing all nine
# round-trips back-to-back on a single connection made the endpoint pay a full
# network RTT per query, which across a far-away Supabase host (Mumbai) summed
# to ~3s. These are pure SELECTs — idempotent, nothing committed — so the
# concurrency is safe, and the pool's default `max_size` of 10 leaves headroom
# after the four slots this route occupies.
def _on_connection(fn, user_id):
    conn = get_db_connection()
    try:
        return fn(conn, user_id)
    finally:
        conn.close()


def _profile(conn, user_id):
    """Target role plus the two role_requirements queries that follow from it.

    The pathway queries depend on the role, so they run here on the same
    connection after it is read rather than being split across parallel
    batches that would each have to guess it.
    """
    user = conn.execute(
        "SELECT target_role FROM users WHERE id = %s", (user_id,)
    ).fetchone()
    role = (user or {}).get("target_role")
    meets = None
    reqs = []
    if role:
        meets = {
            row["competency_id"]
            for row in conn.execute(
                "SELECT rr.competency_id FROM role_requirements rr "
                "JOIN competency_scores cs ON cs.user_id = %s AND cs.competency_id = rr.competency_id "
                "WHERE rr.role = %s AND cs.level >= rr.level",
                (user_id, role),
            ).fetchall()
        }
        reqs = conn.execute(
            "SELECT competency_id, level FROM role_requirements WHERE role = %s", (role,)
        ).fetchall()
    return role, meets, reqs


def _headlines(conn, user_id):
    """Learning hours and the raw enrolment counts behind the courses card."""
    hours = conn.execute(
        "SELECT COALESCE(SUM(module_duration_hours(course_id, module_title)), 0) AS h "
        "FROM module_progress WHERE user_id = %s",
        (user_id,),
    ).fetchone()["h"]
    enrollments = conn.execute(
        "SELECT COUNT(*) AS total, "
        "COUNT(*) FILTER (WHERE progress >= 100) AS done, "
        "COALESCE(SUM(progress), 0) AS progress_sum "
        "FROM course_enrollments WHERE user_id = %s",
        (user_id,),
    ).fetchone()
    return hours, enrollments


def _feed(conn, user_id):
    activities = conn.execute(
        "SELECT id, action, detail, date, icon FROM activities "
        "WHERE user_id = %s ORDER BY date DESC, id DESC LIMIT %s",
        (user_id, FEED_LIMIT),
    ).fetchall()
    notifications = conn.execute(
        "SELECT id, message, type, date, is_read FROM notifications "
        "WHERE user_id = %s ORDER BY date DESC, id DESC",
        (user_id,),
    ).fetchall()
    return activities, notifications


def _events(conn, user_id):
    """Quiz history plus every dated event, for the streak and quiz average."""
    quizzes = conn.execute(
        "SELECT id, title, date, score, total_questions FROM quizzes "
        "WHERE user_id = %s ORDER BY date DESC, created_at DESC",
        (user_id,),
    ).fetchall()
    day_rows = conn.execute(
        "SELECT date AS d FROM activities WHERE user_id = %s AND date IS NOT NULL "
        "UNION SELECT completed_at FROM module_progress WHERE user_id = %s AND completed_at IS NOT NULL "
        "UNION SELECT date FROM quizzes WHERE user_id = %s AND date IS NOT NULL",
        (user_id, user_id, user_id),
    ).fetchall()
    return quizzes, day_rows


@router.get("")
def dashboard(identity: Identity = Depends(current_identity)):
    user_id = identity.id

    with ThreadPoolExecutor(max_workers=4) as pool:
        profile_f = pool.submit(_on_connection, _profile, user_id)
        headlines_f = pool.submit(_on_connection, _headlines, user_id)
        feed_f = pool.submit(_on_connection, _feed, user_id)
        events_f = pool.submit(_on_connection, _events, user_id)

        role, meets, reqs = profile_f.result()
        hours, enrollments = headlines_f.result()
        activities, notifications = feed_f.result()
        quizzes, day_rows = events_f.result()

    active_days = {
        d for d in (_parse_date(r["d"]) for r in day_rows) if d is not None
    }
    today = time.localtime()
    today_key = (today.tm_year, today.tm_mon, today.tm_mday)

    latest = max(active_days) if active_days else None
    scored = [q for q in quizzes if (q["total_questions"] or 0) > 0]
    quiz_avg = (
        round(sum(q["score"] / q["total_questions"] for q in scored) / len(scored) * 100)
        if scored else None
    )

    return {
        "learningHours": round(float(hours or 0), 1),
        "streak": _streak(active_days, today_key),
        "streakAsOf": "-".join(f"{p:02d}" for p in latest) if latest else None,
        "activeDayCount": len(active_days),
        "activities": [dict(a) for a in activities],
        "notifications": [
            {
                "id": n["id"],
                "message": n["message"],
                "type": n["type"],
                "date": n["date"],
                # The column is `is_read`; the frontend type has always
                # been `read`, so map across the naming difference rather
                # than making every consumer remember it.
                "read": bool(n["is_read"]),
            }
            for n in notifications
        ],
        "unreadCount": sum(1 for n in notifications if not n["is_read"]),
        "quizzes": {
            "count": len(quizzes),
            "average": quiz_avg,
            "last": (
                {
                    "id": scored[0]["id"],
                    "title": scored[0]["title"],
                    "date": scored[0]["date"],
                    "score": scored[0]["score"],
                    "totalQuestions": scored[0]["total_questions"],
                }
                if scored else None
            ),
        },
        "courses": {
            "enrolled": int(enrollments["total"] or 0),
            "completed": int(enrollments["done"] or 0),
            "averageProgress": (
                round(int(enrollments["progress_sum"] or 0) / int(enrollments["total"]))
                if enrollments["total"] else 0
            ),
        },
        "pathway": _pathway(role, meets, reqs),
        "targetRole": role,
    }
