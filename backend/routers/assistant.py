"""AI Virtual Assistant route.

A mock assistant that answers domain queries about official statistics, training,
and the SakshamAI platform using a curated knowledge base built from the course
catalogue and competency framework. Modular design leaves room for LLM integration.
"""

import re

import llm
from fastapi import APIRouter
from pydantic import BaseModel
from database import get_db_connection
from llm import LLMUnavailableError, llm_available, model_name
from routers.logic import row_to_course

router = APIRouter(prefix="/api/assistant", tags=["assistant"])


class ChatRequest(BaseModel):
    user_id: str = "learner-1"
    message: str

    # department hint used by the return-to-work planner
    dept: str = ""
    courses: list = []

    # trailing conversation context (role: "user" | "assistant")
    history: list = []


def _build_context(db, user_id: str) -> dict:
    """Live profile, competency snapshot, learning progress and matching courses
    to inject into the LLM prompt as a compact profile snapshot."""
    user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    user = dict(user) if user else {}

    target_role = user.get("current_role") or "Data Analyst"
    scores = {
        r["competency_id"]: r["level"]
        for r in db.execute(
            "SELECT competency_id, level FROM competency_scores WHERE user_id = ?", (user_id,)
        ).fetchall()
    }
    rows = db.execute(
        "SELECT competency_id, level FROM role_requirements WHERE role = ?", (target_role,)
    ).fetchall()
    gaps = []
    for r in rows:
        gap = max(0, r["level"] - scores.get(r["competency_id"], 0))
        if gap > 0:
            comp = db.execute(
                "SELECT name FROM competencies WHERE id = ?", (r["competency_id"],)
            ).fetchone()
            gaps.append({"competency": comp["name"], "current": scores.get(r["competency_id"], 0), "required": r["level"], "gap": gap})
    top = sorted(gaps, key=lambda g: -g["gap"])[:5]

    comp_rows = db.execute(
        "SELECT c.id, c.name, c.category, s.level FROM competencies c "
        "LEFT JOIN competency_scores s ON s.competency_id = c.id AND s.user_id = ? "
        "ORDER BY c.category, c.name", (user_id,)
    ).fetchall()
    competency_list = [
        {"name": r["name"], "category": r["category"], "level": r["level"] or 0}
        for r in comp_rows
    ]
    overall = round(sum(c["level"] for c in competency_list) / len(competency_list), 1) if competency_list else 0

    progress = []
    for e in db.execute(
        "SELECT course_id, progress FROM course_enrollments WHERE user_id = ? ORDER BY enrolled_at DESC", (user_id,)
    ).fetchall():
        c = db.execute("SELECT title, course_code FROM courses WHERE id = ?", (e["course_id"],)).fetchone()
        if c:
            progress.append(f"{c['title']} ({c['course_code']}): {e['progress']}%")
    modules_done = db.execute(
        "SELECT COUNT(*) AS n FROM module_progress WHERE user_id = ?", (user_id,)
    ).fetchone()["n"]
    recent_quizzes = [
        f"{q['title']} — {q['score']}/{q['total_questions']}"
        for q in db.execute(
            "SELECT title, score, total_questions FROM quizzes WHERE user_id = ? ORDER BY date DESC, rowid DESC LIMIT 3", (user_id,)
        ).fetchall()
    ]

    recs = []
    for r in db.execute(
        "SELECT * FROM courses WHERE provider IN ('iGOT Karmayogi', 'NSSTA')"
    ).fetchall():
        c = row_to_course(r)
        if any(g["competency"].lower() == s.lower() for g in top for s in c["skillsCovered"]):
            recs.append(f"{c['title']} ({c['courseCode']}, {c['provider']}) — {', '.join(c['skillsCovered'])}")
        if len(recs) >= 5:
            break

    return {
        "name": user.get("name") or "Learner",
        "designation": user.get("designation") or "",
        "department": user.get("department") or "",
        "education": user.get("education") or "",
        "experience": user.get("experience") or 0,
        "target_role": target_role,
        "career_goal": user.get("career_goal") or "",
        "language": user.get("preferred_language") or "English",
        "competencies": competency_list,
        "overall_level": overall,
        "gaps": top,
        "progress": progress,
        "modules_done": modules_done,
        "recent_quizzes": recent_quizzes,
        "courses": recs,
    }


def _llm_reply(db, req: ChatRequest) -> str:
    ctx = _build_context(db, req.user_id)
    hindi = bool(re.search(r"[\u0900-\u097F]", req.message))

    gaps_txt = "\n".join(
        f"- {g['competency']}: level {g['current']} → required {g['required']} (gap {g['gap']})"
        for g in ctx["gaps"]
    ) or "- (no outstanding gaps)"
    courses_txt = "\n".join(f"- {c}" for c in ctx["courses"]) or "- (see catalogue)"
    competencies_txt = "; ".join(
        f"{c['name']} L{c['level']}" for c in ctx["competencies"]
    )
    progress_txt = "\n".join(f"- {p}" for p in ctx["progress"]) or "- (no enrollments yet)"
    quizzes_txt = "; ".join(ctx["recent_quizzes"]) or "- (no quiz attempts yet)"

    snapshot = (
        f"NAME: {ctx['name']} ({ctx['designation'] or 'designation not set'}, {ctx['department'] or 'department unknown'})\n"
        f"PROFILE: Education: {ctx['education'] or 'n/a'} | Experience: {ctx['experience'] or 0} yrs | "
        f"Preferred language: {ctx['language']}\n"
        f"TARGET ROLE: {ctx['target_role']} | Overall competency level (1-5): {ctx['overall_level']} "
        f"({ctx['modules_done']} modules completed)\n"
        f"FULL COMPETENCY LEVELS: {competencies_txt}\n"
        f"CAREER GOAL: {ctx['career_goal'] or 'not set'}"
    )

    system_prompt = (
        "You are SakshamAI, the official AI career advisor of the Karmayogi skill platform for "
        "India's official statistical system (NSO / NSSTA, delivered through iGOT Karmayogi). "
        "You serve a Government of India officer and must communicate with the decorum, precision "
        "and confidentiality expected of the statistical service.\n\n"
        "CONFIDENTIAL OFFICER PROFILE (use exactly; never invent or assume profile data):\n"
        + snapshot + "\n\n"
        "TARGET ROLE SKILL GAPS (the competencies the officer must raise to qualify):\n"
        + gaps_txt + "\n\n"
        "AVAILABLE iGOT KARMAYOGI / NSSTA COURSES (cite only these real course codes):\n"
        + courses_txt + "\n\n"
        "LEARNING PROGRESS (enrolments, latest first):\n"
        + progress_txt + "\n"
        "RECENT QUIZ RESULTS (last 3): " + quizzes_txt + "\n\n"
        "COMMUNICATION STANDARDS:\n"
        "- Address the officer politely (e.g. 'Respected Madam/Sir' once at the start, then their designation or name).\n"
        "- Answer directly first, ground every recommendation in the officer's own gaps and course codes above.\n"
        "- Be concise and structured: short bullets or a compact table. A table is fine only when it compares at most "
        "a handful of items and you are certain you can COMPLETE every row — never leave a table, bullet or "
        "sentence unfinished.\n"
        "- End with the single most valuable next step (start a specific course, take a quiz, try a Virtual Lab) "
        "and offer to keep assisting.\n"
        "- Use precise statistical-system terminology; do not invent policies, salaries, personal data, or "
        "superscript figures. If exact official figures are required, state they must be verified with NSO / NSSTA.\n"
        "- AI-generated guidance must be reviewed by an authorised trainer before any official use.\n"
        "- Always finish your answer completely, even if brief."
    )
    if hindi:
        system_prompt += (
            "\n\nThe officer is writing in Hindi. Reply in formal Hindi (Hinglish where natural), using "
            "respectful address ('आप'), while keeping course codes and technical terms in English."
        )

    messages = [{"role": "system", "content": system_prompt}]
    for h in req.history[-8:]:
        if isinstance(h, dict) and h.get("role") in ("user", "assistant") and h.get("content"):
            messages.append({"role": h["role"], "content": str(h["content"])})
    messages.append({"role": "user", "content": req.message})

    return llm.chat(messages, temperature=0.3, max_tokens=1200)


def _kb_intro(req: ChatRequest = None) -> str:
    db = get_db_connection()
    try:
        salute = "Respected Officer"
        ctx = None
        if req is not None:
            user = db.execute("SELECT * FROM users WHERE id = ?", (req.user_id,)).fetchone()
            if user:
                ctx = user
                salute = f"Respected {user['name']}" + (f", {user['designation']}" if user["designation"] else "")
        return (
            f"{salute},\n\n"
            "Welcome to SakshamAI — the Karmayogi skill assistant for India's official statistical system. "
            "I support your competency development through:-\n"
            "1. **Skill-gap analysis** against your target role and progress recommendations\n"
            "2. **Course recommendations** mapped to real iGOT Karmayogi and NSSTA courses\n"
            "3. **Structured study plans**, interview preparation and certification guidance\n"
            "4. **Statistics concepts** — sampling, CPI/WPI, national accounts, labour statistics and SDG indicators\n"
            "5. **Mentors and leads** within the department for guidance and coordination\n\n"
            "Suggested prompts: 'Which courses do I need?' • 'Create a study plan for me' • "
            "'How do I prepare for the next assessment?'\n\n"
            "Please note that AI-generated guidance should be reviewed by an authorised trainer before official use."
        )
    finally:
        db.close()


def _match_help(message: str) -> bool:
    if any(k in message for k in ["help", "what can you do", "namaste", "hello", "how are you"]):
        return True
    return bool(re.search(r"\bhi\b|\bhey\b", message))


def _match_gap(message: str) -> bool:
    return any(k in message for k in ["gap", "need", "improve", "courses", "recommend", "training", "study plan", "study"])


def _match_interview(message: str) -> bool:
    return any(k in message for k in ["interview", "prepare", "certification", "exam", "assessment"])


def _match_stat(message: str) -> bool:
    return any(k in message for k in ["statistic", "sample", "survey", "cpi", "gdp", "national account", "inflation", "labour", "sdg", "index"])


def _match_lead(message: str) -> bool:
    return any(k in message for k in ["lead", "mentor", "coordinator", "helper", "contact", "find someone"])


def _gap_response(db, user_id: str) -> str:
    user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        return "I couldn't find your profile. Please log in again."
    target_role = user["current_role"] or "Data Analyst"

    scores = {
        r["competency_id"]: r["level"]
        for r in db.execute(
            "SELECT competency_id, level FROM competency_scores WHERE user_id = ?", (user_id,)
        ).fetchall()
    }
    rows = db.execute(
        "SELECT competency_id, level FROM role_requirements WHERE role = ?", (target_role,)
    ).fetchall()

    gaps = []
    for r in rows:
        req = r["level"]
        cur = scores.get(r["competency_id"], 0)
        gap = max(0, req - cur)
        if gap > 0:
            comp = db.execute(
                "SELECT name FROM competencies WHERE id = ?", (r["competency_id"],)
            ).fetchone()
            gaps.append((comp["name"], cur, req, gap))

    if not gaps:
        return ("Respected officer, you already meet every competency requirement for the target role "
                f"**{target_role}**. I would recommend focusing on professional development and mentorship "
                "to sustain this level of readiness.")

    top = sorted(gaps, key=lambda g: -g[3])[:4]
    lines = [
        f"Based on your target role **{target_role}**, the following competency areas require attention:"
    ]
    for name, cur, req, gap in top:
        lines.append(f"- **{name}**: current level {cur} of {req} (gap of {gap})")
    lines.append("\n**Recommended next steps (real course catalogue):**")
    recs = db.execute(
        "SELECT * FROM courses WHERE provider IN ('iGOT Karmayogi', 'NSSTA')"
    ).fetchall()
    seen = set()
    for r in recs:
        c = row_to_course(r)
        for s in c["skillsCovered"]:
            if any(g[0].lower() == s.lower() for g in top) and s not in seen:
                lines.append(f"- {c['title']} ({c['courseCode']}, {c['provider']}) — covers {s}")
                seen.add(s)
                break
        if len(seen) >= 3:
            break
    lines.append("\nKindly confirm, and I can prepare a study plan for these courses.")
    return "\n".join(lines)


def _plan_response(db, user_id: str, weeks: int = 2) -> str:
    user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        return "I couldn't find your profile."
    target_role = user["current_role"] or "Data Analyst"
    scores = {
        r["competency_id"]: r["level"]
        for r in db.execute(
            "SELECT competency_id, level FROM competency_scores WHERE user_id = ?", (user_id,)
        ).fetchall()
    }
    rows = db.execute(
        "SELECT competency_id, level FROM role_requirements WHERE role = ?", (target_role,)
    ).fetchall()
    gaps = []
    for r in rows:
        gap = max(0, r["level"] - scores.get(r["competency_id"], 0))
        if gap > 0:
            comp = db.execute(
                "SELECT name FROM competencies WHERE id = ?", (r["competency_id"],)
            ).fetchone()
            gaps.append((comp["name"], gap))
    top3 = sorted(gaps, key=lambda g: -g[1])[:3]
    if not top3:
        return ("Respected officer, your profile currently shows no pending skill gaps for target role "
                f"**{target_role}**")
    weeks = max(1, min(weeks, 8))
    plan = [
        f"Here is your {weeks}-week study plan for target role **{target_role}**:\n"
    ]
    lines = []
    period = max(1, weeks // len(top3)) if top3 else 1
    for i, (name, gap) in enumerate(top3):
        w_start = i * period + 1
        w_end = min((i + 1) * period, weeks)
        seq = f"{w_start}–{w_end}" if w_start != w_end else str(w_start)
        lines.append(f"- **Week {seq}**: develop **{name}** (gap {gap}) — 30–45 minutes daily on the "
                     "recommended iGOT Karmayogi / NSSTA modules, followed by reflective quizzes")
    plan += lines
    if weeks > 1:
        plan.append(f"- **Week {weeks}**: consolidation — micro-assessments, Virtual Lab practice and "
                    "interview rehearsal on all covered topics")
    plan.append("\nWould you like me to expand any week into a day-wise schedule?")
    return "\n".join(plan)


def _stat_response(message: str) -> str:
    m = message.lower()
    if "sample" in m or "sampling" in m:
        return ("**Sampling** is the practice of selecting a subset of a population to estimate "
                "population characteristics. Common designs: Simple Random, Stratified, Cluster, "
                "Systematic. The key is a well-built sampling frame and minimizing non-sampling errors.\n\n"
                "Recommended course: *Survey Design and Sampling* (NSSTA-TPAC-202) on your Learning Path.")
    if "cpi" in m or "inflation" in m or "price" in m:
        return ("**CPI/WPI** measure price changes over time. CPI reflects household consumption; "
                "WPI reflects trade in commodities. Both use Laspeyres index formulas with item baskets "
                "and weights updated periodically.\n\n"
                "Recommended course: *Price Statistics and CPI/WPI* (NSSTA-TPAC-204).")
    if "gdp" in m or "national account" in m:
        return ("**National Accounts** compile GDP via three approaches: Production, Income and Expenditure. "
                "India follows the SNA framework; the CSO/NSO compiles estimates that feed fiscal and monetary policy.\n\n"
                "Recommended course: *National Accounts Compilation* (NSSTA-TPAC-203).")
    if "sdg" in m:
        return ("India monitors the **17 SDGs** with 169 targets; NSO coordinates national indicators, "
                "metadata and data reporting. Localisation of indicators to district level is a key initiative.\n\n"
                "Recommended course: *SDG Indicators and Metadata* (NSSTA-TPAC-206).")
    return ("Official statistics support evidence-based decisions across the statistical system. "
            "I can elaborate on sampling, CPI/WPI, national accounts, labour statistics or SDG indicators — "
            "just ask!")


def _lead_response(db, dept: str = "") -> str:
    if dept:
        peeps = db.execute(
            "SELECT * FROM org_learners WHERE department = ?", (dept,)
        ).fetchall()
    else:
        peeps = db.execute(
            "SELECT * FROM org_learners WHERE status = 'Active' ORDER BY competency DESC LIMIT 5"
        ).fetchall()
    if not peeps:
        return "I couldn't find colleagues in that department."
    lines = ["Here are officers who may be approached for mentoring and coordination:"]
    for p in peeps:
        lines.append(
            f"- {p['name']} — {p['job_role']} ({p['department']}), average competency {p['competency']}/5, "
            f"completed {p['completed']} courses"
        )
    return "\n".join(lines)


def _interview_response(db, user_id: str) -> str:
    user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    target = (user["current_role"] if user else None) or "Statistical Investigator"
    return (f"To prepare for a **{target}** interview, focus on:\n"
            "1. Key competencies for that role (see Skill Gap analysis)\n"
            "2. Core statistics concepts — sampling, surveys, CPI/WPI, national accounts\n"
            "3. Ethics & governance dimensions of official statistics\n\n"
            "I suggest completing 2–3 micro-assessments a day from the Quiz Generator and reviewing "
            "the course modules on your Learning Path. Want me to create a study plan?")


@router.post("/chat")
def chat(req: ChatRequest):
    message = (req.message or "").strip()
    if not message:
        return {"reply": _kb_intro(req), "exact": False, "source": "rule"}

    conn = get_db_connection()
    try:
        if llm_available():
            try:
                return {
                    "reply": _llm_reply(conn, req),
                    "exact": True,
                    "source": "llm",
                    "model": model_name(),
                }
            except LLMUnavailableError:
                pass  # fall back to the keyword engine
    finally:
        conn.close()

    return _rule_chat(req)


def _rule_chat(req: ChatRequest):
    message = (req.message or "").strip()
    text = message.lower()
    text = re.sub(r"[?!.,]+", "", text)

    if _match_help(text):
        return {"reply": _kb_intro(req), "exact": False, "source": "rule"}

    if any(k in text for k in ["good", "thanks", "thank", "great", "awesome"]):
        return {"reply": ("You are most welcome. I remain available to support your learning journey. "
                          "You may also use the Interview Prep mock or ask about statistics concepts at any time."),
                "exact": False, "source": "rule"}

    if any(k in text for k in ["course"]):
        from routers.logic import get_recommended_courses
        conn = get_db_connection()
        try:
            rows = conn.execute(
                "SELECT competency_id, level FROM role_requirements WHERE role = (SELECT current_role FROM users WHERE id = ?)",
                (req.user_id,),
            ).fetchall()
            gaps = []
            for r in rows:
                gap = max(0, r["level"] - 2)
                if gap > 0:
                    gaps.append({"competencyName": conn.execute(
                        "SELECT name FROM competencies WHERE id = ?", (r["competency_id"],)
                    ).fetchone()["name"], "priority": "High" if gap >= 3 else "Medium"})
            recs = get_recommended_courses(conn, gaps)
            lines = ["Here are the most relevant courses for your profile:"]
            for c in recs[:5]:
                skill = c["skillsCovered"][0]
                lines.append(f"📚 {c['title']} — {skill} ({c['courseCode']}, {c['provider']})")
            return {"reply": "\n".join(lines), "exact": True, "source": "rule"}
        finally:
            conn.close()

    if any(k in text for k in ["study plan", "schedule", "plan", "organize"]):
        conn = get_db_connection()
        try:
            return {"reply": _plan_response(conn, req.user_id), "exact": True, "source": "rule"}
        finally:
            conn.close()

    if _match_gap(text):
        conn = get_db_connection()
        try:
            return {"reply": _gap_response(conn, req.user_id), "exact": True, "source": "rule"}
        finally:
            conn.close()

    if _match_interview(text):
        conn = get_db_connection()
        try:
            return {"reply": _interview_response(conn, req.user_id), "exact": True, "source": "rule"}
        finally:
            conn.close()

    if _match_stat(text):
        return {"reply": _stat_response(text), "exact": True, "source": "rule"}

    if _match_lead(text):
        conn = get_db_connection()
        try:
            return {"reply": _lead_response(conn, req.dept), "exact": True, "source": "rule"}
        finally:
            conn.close()

    return {
        "reply": ("I understand this question is outside my current scope. I can assist with skill gap "
                  "analysis, course recommendations, study plans, interview preparation, statistics "
                  "concepts and finding mentors within the department. Kindly rephrase your question, "
                  "or try one of the suggested prompts above."),
        "exact": False,
        "source": "rule",
    }