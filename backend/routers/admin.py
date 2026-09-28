"""Admin / analytics routes with organization-wide data."""

from fastapi import APIRouter, Depends

from auth_tokens import require_admin
from database import get_db_connection

# Applied to the whole router rather than per-route: this is organisation-wide
# data about every learner, so there is no sensible public member of it. A
# learner calling /api/admin/overview previously got a full staff roster back.
router = APIRouter(
    prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)]
)


def linear_forecast(points):
    """Least-squares linear extrapolation of (x, y) points."""
    n = len(points)
    if n < 2:
        return [p["y"] for p in points]
    xs = list(range(n))
    xs_bar = sum(xs) / n
    ys_bar = sum(p["y"] for p in points) / n
    num = sum((x - xs_bar) * (p["y"] - ys_bar) for x, p in zip(xs, points))
    den = sum((x - xs_bar) ** 2 for x in xs)
    slope = num / den if den else 0
    intercept = ys_bar - slope * xs_bar
    return [
        {"x": "forecast+1", "label": "Q1", "value": max(0, slope * n + intercept)},
        {"x": "forecast+2", "label": "Q2", "value": max(0, slope * (n + 1) + intercept)},
        {"x": "forecast+3", "label": "Q3", "value": max(0, slope * (n + 2) + intercept)},
    ]


@router.get("/overview")
def overview():
    """Organisation-wide totals, computed from real learner rows.

    Previously every number here was a literal (1240 hours, 68% completion)
    and the counts came from `org_learners`, a table of nine fictional
    officials that shared no rows with `users` — so the dashboard described an
    organisation that did not exist in the database.

    `learner_directory` derives the same shape from real learners, so this now
    agrees with the rest of the app. See /charts and /forecast below: those
    remain deliberately hardcoded sample series.
    """
    conn = get_db_connection()
    try:
        learners = conn.execute("SELECT * FROM learner_directory").fetchall()
        total = len(learners)
        active = sum(1 for l in learners if l["status"] == "Active")
        avg_comp = (
            round(sum(float(l["competency"] or 0) for l in learners) / total, 1)
            if total else 0
        )
        total_gaps = sum(int(l["gaps"] or 0) for l in learners)

        # Real learning hours: the declared duration of every module the
        # organisation has actually completed, via module_duration_hours().
        hours = conn.execute(
            "SELECT COALESCE(SUM(module_duration_hours(course_id, module_title)), 0) AS h "
            "FROM module_progress"
        ).fetchone()["h"]

        enroll = conn.execute(
            "SELECT COUNT(*) AS total, "
            "COUNT(*) FILTER (WHERE progress >= 100) AS done FROM course_enrollments"
        ).fetchone()
        completion_rate = (
            round((enroll["done"] / enroll["total"]) * 100) if enroll["total"] else 0
        )

        return {
            "totalOfficials": total,
            "activeLearners": active,
            "completionRate": completion_rate,
            "avgCompetency": avg_comp,
            "totalLearningHours": round(float(hours or 0), 1),
            "highPriorityGaps": total_gaps,
        }
    finally:
        conn.close()


@router.get("/learners")
def list_learners():
    conn = get_db_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM learner_directory ORDER BY competency DESC, name"
        ).fetchall()
        return [
            {
                "name": r["name"],
                "department": r["department"],
                "role": r["job_role"],
                "competency": r["competency"],
                "gaps": r["gaps"],
                "completed": r["completed"],
                "status": r["status"],
            }
            for r in rows
        ]
    finally:
        conn.close()


@router.get("/forecast")
def forecast():
    """Predictive analytics: extrapolate skill demand and readiness trends.

    NOTE: the six-month `engagement` series below is hardcoded sample data, not
    a query. It was left as-is deliberately when the rest of this router was
    moved onto real aggregates — the regression maths is real, but it is
    regressing a fixed series. Wire it to dated activity data before treating
    any number on this endpoint as meaningful. `/overview` and `/learners` are
    NOT in that category; those are computed from real learner rows.
    """
    conn = get_db_connection()
    try:
        engagement = [
            {"month": "Apr", "hours": 120, "completions": 8},
            {"month": "May", "hours": 145, "completions": 11},
            {"month": "Jun", "hours": 160, "completions": 15},
            {"month": "Jul", "hours": 180, "completions": 18},
            {"month": "Aug", "hours": 210, "completions": 22},
            {"month": "Sep", "hours": 195, "completions": 24},
        ]
        total = conn.execute("SELECT COUNT(*) AS c FROM learner_directory").fetchone()["c"] or 1
        avg_requested = max(1, len(engagement))
        readiness = [completions / max(total, 1) for completions in (8, 11, 15, 18, 22, 24)]
        hours_pts = [{"y": e["hours"]} for e in engagement]
        readiness_pts = [{"y": v} for v in readiness]

        # Forecast each series on its own. Concatenating hours and completions
        # into a single regression looked reasonable but is not: the two are
        # different units an order of magnitude apart, so the joined series is
        # bimodal -- six points near 200, then six near 20 -- and the fitted
        # slope is dominated by the step between the blocks rather than by
        # either trend. The "hours" figure it produced was the average of two
        # unrelated quantities. `completions` is derived from the readiness
        # trend instead, which is on a per-learner scale and is multiplied
        # back up by headcount.
        future_trend = linear_forecast(hours_pts)
        readiness_trend = linear_forecast(readiness_pts)

        return {
            "method": "linear-regression",
            "forecastPeriods": [
                {"label": "Current", "hours": sum(e["hours"] for e in engagement) / avg_requested,
                 "completions": sum(e["completions"] for e in engagement) / avg_requested},
            ],
            "future": [
                {"label": p["label"], "hours": p["value"],
                 "completions": readiness_trend[i]["value"] * total}
                for i, p in enumerate(future_trend)
            ],
            "readinessTrend": [
                {"label": e["month"], "value": round(score, 3)} for score, e in zip(readiness, engagement)
            ] + [
                {"label": p["label"], "value": round(p["value"], 3)} for p in readiness_trend
            ],
            "insights": [
                "Overall learner engagement is trending upward ~15% per quarter.",
                "Projected workforce readiness (+2 levels on core competencies) within 2 quarters.",
                "Focus training on Data Science & AI/ML — highest forecasted demand growth.",
            ],
        }
    finally:
        conn.close()


@router.get("/charts")
def charts():
    """Static mock data matching the frontend charts.

    Deliberately hardcoded and deliberately left that way: these series are
    illustrative chart filler for the demo, not measurements. Unlike
    /overview and /learners, nothing here is derived from the database. Treat
    every value below as sample data.
    """
    return {
        "gapDistribution": [
            {"name": "High", "value": 34},
            {"name": "Medium", "value": 48},
            {"name": "Low", "value": 62},
            {"name": "No Gap", "value": 124},
        ],
        "deptScores": [
            {"dept": "NSSO", "avgCompetency": 2.7},
            {"dept": "Census", "avgCompetency": 2.6},
            {"dept": "DGCIS", "avgCompetency": 3.3},
            {"dept": "NSSTA", "avgCompetency": 3.9},
        ],
        "completionTrend": [
            {"month": "Jul", "completions": 12},
            {"month": "Aug", "completions": 18},
            {"month": "Sep", "completions": 24},
        ],
        "topMissing": [
            {"skill": "Python", "count": 7},
            {"skill": "AI/ML", "count": 8},
            {"skill": "Data Viz", "count": 5},
            {"skill": "SQL", "count": 4},
            {"skill": "Leadership", "count": 3},
        ],
        "trainingEffectiveness": [
            {"course": "Python", "before": 1.5, "after": 3.2},
            {"course": "Data Viz", "before": 2.0, "after": 3.5},
            {"course": "SQL", "before": 2.0, "after": 3.0},
            {"course": "Survey", "before": 3.0, "after": 3.8},
        ],
        "engagement": [
            {"month": "Apr", "hours": 120, "completions": 8},
            {"month": "May", "hours": 145, "completions": 11},
            {"month": "Jun", "hours": 160, "completions": 15},
            {"month": "Jul", "hours": 180, "completions": 18},
            {"month": "Aug", "hours": 210, "completions": 22},
            {"month": "Sep", "hours": 195, "completions": 24},
        ],
        "emergingSkills": [
            {"skill": "AI/ML in Statistics", "demand": 85},
            {"skill": "Cloud Data Platforms", "demand": 72},
            {"skill": "Real-time Analytics", "demand": 68},
            {"skill": "Geospatial Analysis", "demand": 55},
        ],
    }