"""Shared business logic: skill-gap calculation, recommendations, MCQ generation."""

import json
import random
import re
from typing import List, Dict, Tuple

import llm


PRIORITY_COLORS = {"High": "red", "Medium": "amber", "Low": "blue", "No Gap": "green"}


def get_role_requirements(cursor, role: str) -> List[Tuple[str, int]]:
    rows = cursor.execute(
        "SELECT competency_id, level FROM role_requirements WHERE role = ?",
        (role,),
    ).fetchall()
    return [(r["competency_id"], r["level"]) for r in rows]


def calculate_skill_gaps(cursor, current_scores: List[Dict], target_role: str) -> List[Dict]:
    reqs = get_role_requirements(cursor, target_role)
    if not reqs:
        return []

    score_map = {s["competencyId"]: s["level"] for s in current_scores}
    result = []
    for cid, required in reqs:
        current = score_map.get(cid, 0)
        gap = max(0, required - current)
        if gap >= 3:
            priority = "High"
        elif gap == 2:
            priority = "Medium"
        elif gap == 1:
            priority = "Low"
        else:
            priority = "No Gap"

        comp = cursor.execute(
            "SELECT name, category, description FROM competencies WHERE id = ?",
            (cid,),
        ).fetchone()
        if not comp:
            continue
        result.append({
            "competencyId": cid,
            "competencyName": comp["name"],
            "category": comp["category"],
            "description": comp["description"],
            "currentLevel": current,
            "requiredLevel": required,
            "gap": gap,
            "priority": priority,
        })
    return result


def get_recommended_courses(cursor, gaps: List[Dict]) -> List[Dict]:
    high_skills = {g["competencyName"] for g in gaps if g["priority"] in ("High", "Medium")}
    rows = cursor.execute("SELECT * FROM courses").fetchall()
    result = []
    for r in rows:
        skills = json.loads(r["skills_covered"])
        if any(s in high_skills for s in skills):
            result.append(row_to_course(r))
    return result


def row_to_course(r) -> Dict:
    try:
        modules = json.loads(r["modules"]) if r["modules"] else []
    except (json.JSONDecodeError, TypeError):
        modules = []
    return {
        "id": r["id"],
        "courseCode": r["course_code"],
        "title": r["title"],
        "provider": r["provider"],
        "description": r["description"],
        "skillsCovered": json.loads(r["skills_covered"]),
        "difficulty": r["difficulty"],
        "duration": r["duration"],
        "language": r["language"],
        "rating": r["rating"],
        "thumbnail": r["thumbnail"],
        "category": r["category"],
        "modules": modules,
        "enrolled": False,
        "progress": 0,
    }


def generate_quiz_questions(text: str, count: int, difficulty: str) -> List[Dict]:
    sentences = [s.strip() for s in re.split(r"[.!?]+", text) if len(s.strip()) > 20]
    stopwords = {
        "involves", "through", "during", "after", "before", "between", "about",
        "along", "around", "behind", "their", "there", "these", "those",
        "which", "while", "whose", "within", "without", "analysis", "however",
    }
    words = [
        w.rstrip(",;:").lower() for w in re.findall(r"[A-Za-z-]+", text)
        if len(w) >= 6 and w.lower() not in stopwords
    ]
    if not sentences:
        sentences = [text[:80]] if text else []
    if not words:
        words = ["statistics", "data collection", "survey methodology"]

    templates = [
        lambda topic, detail: {
            "question": f"What is the primary purpose of {topic} in official statistics?",
            "options": [f"To ensure systematic and accurate {detail}", "To reduce operational costs only", "To automate all manual processes", "To replace human judgment entirely"],
            "correctAnswer": 0,
        },
        lambda topic, detail: {
            "question": f"Which of the following best describes {topic}?",
            "options": ["A technique used only in private sector", f"A methodology for {detail}", "An outdated practice in statistics", "A type of hardware component"],
            "correctAnswer": 1,
        },
        lambda topic, detail: {
            "question": f"In the context of government data, {topic} is important because:",
            "options": ["It reduces the need for data collection", "It only applies to financial data", f"It ensures {detail} in official records", "It eliminates all data errors"],
            "correctAnswer": 2,
        },
        lambda topic, detail: {
            "question": f"What is a key challenge when implementing {topic}?",
            "options": [f"Ensuring data quality and {detail}", "Lack of government interest", "Too much available funding", "Excess of qualified personnel"],
            "correctAnswer": 0,
        },
        lambda topic, detail: {
            "question": f"Which skill is most related to {topic}?",
            "options": ["Cooking and food preparation", "Mechanical engineering", "Agricultural science", f"Analytical thinking and {detail}"],
            "correctAnswer": 3,
        },
    ]

    questions = []
    used = set()
    random.seed()
    for i in range(count):
        sentence = sentences[i % len(sentences)] if sentences else " ".join(words[i * 3:i * 3 + 10])
        topic = words[i % len(words)] if words else "statistical methods"
        template = templates[i % len(templates)]
        if sentence in used and len(sentences) > count:
            continue
        used.add(sentence)
        detail = sentence[:60]
        generated = template(topic, detail)

        # Shuffle options while tracking the correct one
        opts = list(generated["options"])
        correct_text = opts[generated["correctAnswer"]]
        random.shuffle(opts)
        new_correct = opts.index(correct_text)

        questions.append({
            "id": f"q-{random.randint(100000, 999999)}-{i}",
            "question": generated["question"],
            "options": opts,
            "correctAnswer": new_correct,
            "explanation": f"Based on the provided content: \"{sentence[:100]}...\"",
            "difficulty": difficulty,
            "sourceExcerpt": sentence[:120],
        })
    return questions


# ---------------- LLM-assisted MCQ generation ----------------

_QUIZ_SYSTEM = (
    "You are an examiner for India's Official Statistical System (NSO/NSSTA/iGOT Karmayogi). "
    "Given a passage of learning material, create high-quality multiple choice questions that test "
    "understanding of the content, not trivia. Each question MUST be grounded in the material."
)


def generate_quiz_questions_llm(text: str, count: int, difficulty: str, retries: int = 1) -> List[Dict]:
    """Generate MCQs with the LLM. Raises llm.LLMUnavailableError on any failure
    so the caller can fall back to the deterministic generator."""
    excerpt = text[:12000].strip()
    if not excerpt:
        raise llm.LLMUnavailableError("No text to generate from")

    schema_prompt = (
        "Respond ONLY with a JSON object, no prose. Schema:\n"
        '{"questions":[{"question":"...","options":["a","b","c","d"],'
        '"correctAnswer":0,"explanation":"brief, grounded in the material",'
        '"difficulty":"Easy|Medium|Hard","sourceExcerpt":"short quote from the material"}]}\n'
        f"Produce exactly {count} questions. correctAnswer is the 0-based index of the correct option. "
        "Exactly 4 options per question. difficulty should be the requested difficulty unless the "
        "content clearly warrants otherwise."
    )

    messages = [
        llm.system(_QUIZ_SYSTEM),
        llm.user(
            f"Requested difficulty: {difficulty}.\n\n"
            f"--- LEARNING MATERIAL ---\n{excerpt}\n\n--- TASK ---\n{schema_prompt}"
        ),
    ]

    for attempt in range(retries + 1):
        raw = llm.chat(messages, json_mode=True, temperature=0.3, max_tokens=4096)
        data = llm.extract_json(raw)
        questions = _validate_questions(data, count, difficulty)
        if questions is not None:
            return questions
        if attempt < retries:
            messages.append(llm.assistant(raw))
            messages.append(llm.user(
                "Your previous response did not match the required schema "
                "(4 options each, correctAnswer as a 0-3 integer, exactly the requested count). "
                "Return only corrected JSON in the exact schema."
            ))

    raise llm.LLMUnavailableError("LLM returned invalid quiz JSON")


def _validate_questions(data: dict, count: int, difficulty: str) -> List[Dict] | None:
    qs = data.get("questions") if isinstance(data, dict) else None
    if not isinstance(qs, list) or not qs:
        return None
    out = []
    for i, q in enumerate(qs[:count]):
        if not isinstance(q, dict):
            return None
        question = str(q.get("question", "")).strip()
        options = q.get("options")
        if not question or not isinstance(options, list) or len(options) != 4:
            return None
        options = [str(o).strip() for o in options]
        if any(not o for o in options):
            return None
        correct = q.get("correctAnswer")
        if not isinstance(correct, int) or not (0 <= correct < 4):
            return None
        out.append({
            "id": f"q-{random.randint(100000, 999999)}-{i}",
            "question": question,
            "options": options,
            "correctAnswer": correct,
            "explanation": str(q.get("explanation", "")).strip(),
            "difficulty": difficulty,
            "sourceExcerpt": str(q.get("sourceExcerpt", "")).strip()[:200],
        })
    return out if len(out) == count else None