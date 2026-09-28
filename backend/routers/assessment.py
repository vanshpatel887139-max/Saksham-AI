"""Role-based competency test generation & scoring.

Mirrors the frontend assessment pipeline (buildRoleCompetencyTest /
deriveCompetencyTestLevels / applyCompetencyTestToProfile) server-side:

  * LLM-first: when Groq is reachable, question stems for the requested
    competencies are authored by the model via the same `llm` seam used by
    logic.py (chat in JSON mode, strict schema).
  * Deterministic fallback: a hand-written bank per competency plus a
    generic stub generator guarantee the endpoint always answers — matching
    the app's "works offline, LLM when available" contract.

Every response conforms to the frontend `CompetencyTest` interface
(src/types/index.ts): questions carry competencyId/competencyName/category and
use `correctIndex` (not `correct`), so grading agrees on both sides.

REST:
  POST /api/assessment/generate  { role, roleLabel, competencyIds, maxQuestions }
  POST /api/assessment/submit    { role, roleLabel, questions, answers }
"""

import random
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from psycopg.types.json import Json

from fastapi import APIRouter, Depends, HTTPException

from auth_tokens import Identity, current_identity
from database import get_db_connection
from models import AssessmentGenerateRequest, AssessmentSubmitRequest

try:
    import llm
    from llm import LLMUnavailableError

    LLM_IMPORT_OK = True
except Exception:  # pragma: no cover - llm module always present in this repo
    LLM_IMPORT_OK = False

router = APIRouter(prefix="/api/assessment", tags=["assessment"])

# ---------------------------------------------------------------------------
# Deterministic question bank (same competency ids as the frontend bank)
# ---------------------------------------------------------------------------
_COMPETENCY_META: Dict[str, Tuple[str, str]] = {
    "python": ("Python", "Technical"),
    "sampling": ("Sampling", "Statistical"),
    "data-visualization": ("Data Visualization", "Technical"),
    "communication": ("Communication", "Behavioural"),
    "ai-ml": ("AI & Machine Learning", "Technical"),
}

_meta_cache: Optional[Dict[str, Tuple[str, str]]] = None


def _competency_meta(competency_id: str) -> Tuple[str, str]:
    """Resolve the (name, category) shown on a question.

    The `competencies` table is the single source of truth for names and
    categories, so questions always agree with the rest of the app. The static
    map is only a fallback for when the database cannot be read: it covers just
    five competencies, and without a fallback everything else used to render as
    its raw slug (e.g. "labour-statistics") mislabelled as "Technical".
    """
    global _meta_cache
    if _meta_cache is None:
        conn = None
        try:
            conn = get_db_connection()
            rows = conn.execute(
                "SELECT id, name, category FROM competencies"
            ).fetchall()
            _meta_cache = {r["id"]: (r["name"], r["category"]) for r in rows}
        except Exception:
            _meta_cache = {}
        finally:
            # Must return the connection to the pool. Leaving it checked out
            # here leaked one pooled connection per process for the lifetime of
            # the cache, and after DB_POOL_MAX requests every endpoint in the
            # app started failing with PoolTimeout.
            if conn is not None:
                conn.close()
    if competency_id in _meta_cache:
        return _meta_cache[competency_id]
    return _COMPETENCY_META.get(competency_id, (competency_id, "Technical"))


def _q(
    qid: str,
    competency_id: str,
    difficulty: int,
    prompt: str,
    options: List[str],
    correct_index: int,
    explanation: str,
) -> Dict[str, Any]:
    """Build a bank entry tagged with its competency, matching AssessmentQuestion."""
    name, category = _competency_meta(competency_id)
    return {
        "id": qid,
        "competencyId": competency_id,
        "competencyName": name,
        "category": category,
        "difficulty": difficulty,
        "prompt": prompt,
        "options": options,
        "correctIndex": correct_index,
        "explanation": explanation,
        "stemSource": "bank",
    }


_QUESTION_BANK: Dict[str, List[Dict[str, Any]]] = {
    "python": [
        _q("q-python-1", "python", 1, "Which Python function returns the number of items in a list?",
           ["len()", "size()", "count()", "length()"], 0, "len() is the built-in function for length."),
        _q("q-python-2", "python", 2, "In pandas, which method returns the first few rows of a DataFrame?",
           ["head()", "first()", "top()", "begin()"], 0, "df.head(n) returns the first n rows."),
        _q("q-python-3", "python", 3, "Which pandas method summarizes a DataFrame by groups?",
           ["groupby()", "pivot_pick()", "split()", "filter()"], 0, "df.groupby('col').agg() summarizes by group."),
    ],
    "sampling": [
        _q("q-sampling-1", "sampling", 1, "What is the main purpose of sampling?",
           ["Infer about a population from a subset", "Count every member",
            "Replace the population", "Reduce cost by guessing"], 0,
           "A representative subset lets you estimate population parameters."),
        _q("q-sampling-2", "sampling", 2, "Which method divides the population into homogeneous groups and samples each?",
           ["Stratified sample", "Simple random sample", "Convenience sample", "Snowball sample"], 0,
           "Stratified sampling splits into strata and samples within each."),
        _q("q-sampling-3", "sampling", 3, "The standard error of the mean primarily measures:",
           ["Sampling variability of the estimate", "Bias of the estimator",
            "Non-response", "Coverage error"], 0,
           "Standard error expresses how much the estimate varies around the true mean."),
    ],
    "data-visualization": [
        _q("q-dv-1", "data-visualization", 1, "Which chart best shows a trend over time?",
           ["Line chart", "Pie chart", "Scatterplot", "Treemap"], 0,
           "Line charts connect points in time to reveal trends."),
        _q("q-dv-2", "data-visualization", 2, "When comparing parts of a whole, which chart is most appropriate?",
           ["Pie or stacked bar chart", "Scatterplot", "Box plot", "Histogram"], 0,
           "Part-to-whole relationships map well to pie or stacked bars."),
        _q("q-dv-3", "data-visualization", 3, "Which practice improves chart readability?",
           ["Start the y-axis at zero unless there is a reason", "Use rainbow gradients by default",
            "Add non-data ink", "Skip axis labels"], 0,
           "Truncated axes distort comparison; zero-based axes keep proportions honest."),
    ],
    "communication": [
        _q("q-comm-1", "communication", 1, "What is the clearest way to structure an official report?",
           ["Executive summary, findings, methodology, annexes", "Methodology last, findings first",
            "Raw data only", "Conclusions without context"], 0,
           "A logical flow from summary to findings to methods serves varied readers."),
        _q("q-comm-2", "communication", 2, "When presenting statistical findings to policymakers, you should:",
           ["Emphasize insights and uncertainty, not jargon", "Use maximum technical jargon",
            "Hide margins of error", "Avoid visuals"], 0,
           "Non-specialist audiences need clear, quantified messages."),
        _q("q-comm-3", "communication", 4, "A table footnoted as 'data may not sum to 100% due to rounding' is:",
           ["Transparent metadata communication", "A data fabrication",
            "A random error", "A coverage gap"], 0,
           "Documenting rounding and limitations is transparent metadata practice."),
    ],
    "ai-ml": [
        _q("q-aiml-1", "ai-ml", 2, "What is the distinguishing trait of supervised learning?",
           ["Labels are provided during training", "No output data exists",
            "It clusters unlabeled data", "It only runs in the cloud"], 0,
           "Supervised learning trains on labeled examples."),
        _q("q-aiml-2", "ai-ml", 3, "Which metric best evaluates an imbalanced classification model?",
           ["F1-score", "Raw accuracy", "Number of epochs", "Learning rate"], 0,
           "Accuracy misleads on imbalanced data; F1 balances precision and recall."),
        _q("q-aiml-3", "ai-ml", 4, "A model that performs well on training data but poorly on unseen data is said to be:",
           ["Overfitting", "Underfitting", "Converged", "Regularized"], 0,
           "Overfitting memorizes training noise and fails to generalize."),
    ],
}

_TEST_SYSTEM = (
    "You are SakshamAI's competency-test setter for Indian official statistics. "
    "Author short, concrete multiple-choice questions that measure real applied skill. "
    "Respond ONLY with a JSON object, no prose."
)

_TEST_SCHEMA = (
    '\nSchema:\n{"questions":[{"id":"...","competencyId":"...","difficulty":1,'
    '"prompt":"...","options":["a","b","c","d"],"correctIndex":0,"explanation":"..."}]}\n'
    "Each question: 4 options exactly, difficulty 1-5 integer, competencyId must be one of the "
    "requested ids, correctIndex is the 0-based index of the correct option. "
    "Do NOT always place the correct answer first — vary it. "
    "Return at most the requested number of questions, spread across the requested competencies."
)


def _safe_int(value: Any, default: int) -> int:
    """Coerce to int without raising — LLM output and client input are both untrusted."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _shuffle_options(q: Dict[str, Any], rng: random.Random) -> Dict[str, Any]:
    """Reorder options and remap correctIndex so the answer isn't always option A.

    Mirrors shuffleQuestionOptions in src/data/mockData.ts.
    """
    options = list(q.get("options") or [])
    correct_index = _safe_int(q.get("correctIndex"), -1)
    if len(options) < 2 or not (0 <= correct_index < len(options)):
        return q
    correct = options[correct_index]
    distractors = [o for i, o in enumerate(options) if i != correct_index]
    rng.shuffle(distractors)
    new_index = rng.randrange(len(distractors) + 1)
    distractors.insert(new_index, correct)
    out = dict(q)
    out["options"] = distractors
    out["correctIndex"] = new_index
    return out


def _stub_questions(competency_id: str, count: int = 3) -> List[Dict[str, Any]]:
    """Deterministic generic questions for any competency — mirrors generateStubCompetencyQuestions."""
    name, category = _competency_meta(competency_id)
    base = [
        (1, f"In the context of {name} ({category}), the first task is to define the objective clearly.",
         ["Define scope before collecting", "Skip planning", "Copy a template", "Ask to postpone"]),
        (2, f"Which practice most improves the reliability of a {name} deliverable?",
         ["Document every assumption and source", "Work without notes", "Trust gut feel", "Finalize only once"]),
        (3, f"A senior official asks how {name} results were validated. The best response:",
         ["Walk through method and checks", "Say it came from software", "Send the raw data", "Change the subject"]),
    ]
    return [
        _q(f"stub-{competency_id}-{i + 1}", competency_id, difficulty, prompt, opts, 0,
           "Deterministic stub question for offline availability.")
        for i, (difficulty, prompt, opts) in enumerate(base[:count])
    ]


def _normalize_llm_question(raw: Any, fallback_competency_id: str) -> Optional[Dict[str, Any]]:
    """Validate one LLM question into an AssessmentQuestion, or return None to drop it."""
    if not isinstance(raw, dict):
        return None
    prompt = raw.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        return None
    options = raw.get("options")
    if not isinstance(options, list):
        return None
    options = [str(o) for o in options]
    if len(options) != 4:
        return None

    competency_id = raw.get("competencyId")
    if not isinstance(competency_id, str) or not competency_id.strip():
        competency_id = fallback_competency_id
    name, category = _competency_meta(competency_id)

    difficulty = _safe_int(raw.get("difficulty"), 1)
    correct_index = _safe_int(raw.get("correctIndex", raw.get("correct")), 0)
    if not (0 <= correct_index < len(options)):
        correct_index = 0

    qid = raw.get("id")
    return {
        "id": qid if isinstance(qid, str) and qid else f"llm-{uuid.uuid4().hex[:8]}",
        "competencyId": competency_id,
        "competencyName": str(raw.get("competencyName") or name),
        "category": str(raw.get("category") or category),
        "difficulty": max(1, min(5, difficulty)),
        "prompt": prompt.strip(),
        "options": options,
        "correctIndex": correct_index,
        "explanation": str(raw.get("explanation") or ""),
        "stemSource": "llm",
    }


def _llm_generate_questions(competency_ids: List[str], max_questions: int) -> List[Dict[str, Any]]:
    """LLM-authored stems for the requested competencies (Groq seam, same as logic.py).

    Raises LLMUnavailableError on any failure so the caller can fall back to
    the deterministic bank. Malformed LLM output must not surface as a 500.
    """
    if not LLM_IMPORT_OK:
        raise LLMUnavailableError("llm module unavailable")
    if not competency_ids:
        raise LLMUnavailableError("no competencies requested")

    per_comp = max(1, max_questions // len(competency_ids))
    targets = [
        {"id": cid, "name": _competency_meta(cid)[0], "category": _competency_meta(cid)[1]}
        for cid in competency_ids
    ]
    messages = [
        llm.system(_TEST_SYSTEM),
        llm.user(
            f"Produce up to {per_comp} questions for EACH of these competencies: {targets}.\n{_TEST_SCHEMA}"
        ),
    ]
    try:
        raw = llm.chat(messages, json_mode=True, temperature=0.3, max_tokens=4096)
        data = llm.extract_json(raw)
    except (LLMUnavailableError, ValueError, TypeError, KeyError) as e:
        raise LLMUnavailableError(f"LLM question generation failed: {e}") from e

    if not isinstance(data, dict):
        raise LLMUnavailableError("LLM returned a non-object payload")
    candidates = data.get("questions")
    if not isinstance(candidates, list) or not candidates:
        raise LLMUnavailableError("LLM returned no assessment questions")

    out: List[Dict[str, Any]] = []
    for i, raw_q in enumerate(candidates[:max_questions]):
        fallback = competency_ids[i % len(competency_ids)]
        normalized = _normalize_llm_question(raw_q, fallback)
        if normalized is not None:
            out.append(normalized)
    if not out:
        raise LLMUnavailableError("LLM returned no valid assessment questions")
    return out


def _bank_questions(
    competency_ids: List[str], max_questions: int, rng: random.Random, per_competency: int = 3
) -> List[Dict[str, Any]]:
    """Deterministic bank/stub questions, dealt round-robin.

    Round-robin (rather than filling one competency at a time) keeps the
    per-competency question counts within one of each other when
    maxQuestions is not a multiple of len(competency_ids). `per_competency`
    caps how many questions any single competency can take, so a competency
    with a large bank cannot crowd the others out.
    """
    pools: Dict[str, List[Dict[str, Any]]] = {}
    for cid in competency_ids:
        pool = [dict(q) for q in (_QUESTION_BANK.get(cid) or _stub_questions(cid))]
        rng.shuffle(pool)
        pools[cid] = pool

    taken: Dict[str, int] = {cid: 0 for cid in competency_ids}
    questions: List[Dict[str, Any]] = []
    while len(questions) < max_questions:
        progressed = False
        for cid in competency_ids:
            if len(questions) >= max_questions:
                break
            if taken[cid] >= per_competency:
                continue
            pool = pools[cid]
            if pool:
                questions.append(_shuffle_options(pool.pop(), rng))
                taken[cid] += 1
                progressed = True
        if not progressed:
            break
    return questions


def _generate_questions(
    competency_ids: List[str], max_questions: int, per_competency: int = 3
) -> Tuple[List[Dict[str, Any]], str]:
    """LLM-first with a deterministic bank fallback.

    Returns (questions, source) so callers learn the provenance without relying
    on module-level state, which is not safe across concurrent requests.
    """
    if not competency_ids:
        return [], "mock"

    rng = random.Random(uuid.uuid4().hex)
    if LLM_IMPORT_OK and llm.llm_available():
        try:
            llm_questions = _llm_generate_questions(competency_ids, max_questions)
            questions = [_shuffle_options(q, rng) for q in llm_questions]
            # A thin LLM reply must not become a 1-question "test" that then
            # overwrites the user's profile — top up any uncovered competency
            # from the bank.
            covered = {q["competencyId"] for q in questions}
            missing = [cid for cid in competency_ids if cid not in covered]
            if missing and len(questions) < max_questions:
                seen = {q["id"] for q in questions}
                top_up = _bank_questions(
                    missing, max_questions - len(questions), rng, per_competency
                )
                questions.extend(q for q in top_up if q["id"] not in seen)
            if questions:
                return questions[:max_questions], "llm"
        except Exception:
            # This endpoint promises it always answers: any LLM-layer failure
            # (network, malformed JSON, unexpected payload) falls through to the bank.
            pass

    return _bank_questions(competency_ids, max_questions, rng, per_competency), "mock"


def _derive_levels(
    questions: List[Dict[str, Any]], answers: List[Optional[int]]
) -> List[Dict[str, Any]]:
    """Per-competency derived level 1-5 + accuracy — mirrors frontend deriveCompetencyTestLevels.

    Groups by competencyId while carrying each question's index into the *global*
    answers array; using the per-group position would misalign every competency
    after the first.
    """
    by_comp: Dict[str, List[Tuple[int, Dict[str, Any]]]] = {}
    for index, q in enumerate(questions):
        if not isinstance(q, dict):
            continue
        competency_id = q.get("competencyId")
        if not isinstance(competency_id, str) or not competency_id:
            competency_id = "unknown"
        by_comp.setdefault(competency_id, []).append((index, q))

    results: List[Dict[str, Any]] = []
    for competency_id, entries in by_comp.items():
        correct = 0
        max_correct_difficulty = 0
        for index, q in entries:
            answer = answers[index] if index < len(answers) else None
            expected = q.get("correctIndex", q.get("correct"))
            if answer is None or expected is None:
                continue
            if _safe_int(answer, -1) == _safe_int(expected, -2):
                correct += 1
                max_correct_difficulty = max(
                    max_correct_difficulty, _safe_int(q.get("difficulty"), 1)
                )
        accuracy = round((correct / len(entries)) * 100)
        derived = (
            5 if accuracy >= 90 else 4 if accuracy >= 75
            else 3 if accuracy >= 55 else 2 if accuracy >= 35 else 1
        )
        derived = min(derived, max(1, max_correct_difficulty))
        fallback_name, fallback_category = _competency_meta(competency_id)
        first = entries[0][1]
        results.append({
            "competencyId": competency_id,
            "competencyName": first.get("competencyName") or fallback_name,
            "category": first.get("category") or fallback_category,
            "derivedLevel": derived,
            "selfRatedLevel": None,
            "perceptionGap": None,
            "questionsAttempted": len(entries),
            "correctCount": correct,
            "accuracyPct": accuracy,
            "highestDifficultyCorrect": max_correct_difficulty,
        })
    return results


def _count_correct(questions: List[Dict[str, Any]], answers: List[Optional[int]]) -> int:
    total = 0
    for index, q in enumerate(questions):
        if not isinstance(q, dict) or index >= len(answers):
            continue
        answer = answers[index]
        expected = q.get("correctIndex", q.get("correct"))
        if answer is None or expected is None:
            continue
        if _safe_int(answer, -1) == _safe_int(expected, -2):
            total += 1
    return total


def _competency_names(competency_ids: List[str]) -> List[str]:
    return [_competency_meta(cid)[0] for cid in competency_ids]


@router.post("/generate")
def generate_test(
    req: AssessmentGenerateRequest, identity: Identity = Depends(current_identity)
):
    # Authenticated because this calls an LLM: leaving it open would let anyone
    # spend the project's API budget through your deployment.
    if not req.competencyIds:
        raise HTTPException(status_code=400, detail="competencyIds must not be empty")

    # Single generation pass — provenance comes back with the result.
    questions, source = _generate_questions(
        req.competencyIds, req.maxQuestions, req.questionsPerCompetency
    )
    if not questions:
        raise HTTPException(status_code=500, detail="no questions could be generated")

    return {
        "id": f"ct-{uuid.uuid4().hex[:12]}",
        "role": req.role,
        "roleLabel": req.roleLabel,
        "competencies": _competency_names(req.competencyIds),
        "questions": questions,
        "questionsAttempted": len(questions),
        "takenAt": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "locked": False,
        "generatedBy": source,
    }


def _persist_questions(
    user_id: str, test_id: str, taken_at: str, questions: List[Dict[str, Any]], answers: List[Optional[int]]
) -> None:
    """Store the graded paper so the breakdown view survives a refresh.

    Only the latest test is kept per user; a retake replaces it.
    """
    conn = get_db_connection()
    try:
        conn.execute("DELETE FROM assessment_questions WHERE user_id = %s", (user_id,))
        for position, q in enumerate(questions):
            options = q.get("options") or []
            conn.execute(
                "INSERT INTO assessment_questions "
                "(user_id, test_id, taken_at, position, question_id, competency_id, competency_name, "
                " prompt, options, correct_index, chosen_index, difficulty, explanation) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT DO NOTHING",
                (
                    user_id,
                    test_id,
                    taken_at,
                    position,
                    str(q.get("id") or f"q-{position}"),
                    str(q.get("competencyId") or "unknown"),
                    q.get("competencyName"),
                    str(q.get("prompt") or ""),
                    # jsonb column: needs a real JSON document, not Postgres
                    # array syntax. Same class of failure as quiz_questions.
                    Json(options),
                    _safe_int(q.get("correctIndex", q.get("correct")), 0),
                    answers[position] if position < len(answers) else None,
                    _safe_int(q.get("difficulty"), 1),
                    q.get("explanation") or "",
                ),
            )
        conn.commit()
    finally:
        conn.close()


@router.post("/submit")
def submit_test(
    req: AssessmentSubmitRequest, identity: Identity = Depends(current_identity)
):
    questions = [q for q in (req.questions or []) if isinstance(q, dict)]
    answers = list(req.answers or [])
    if not questions:
        raise HTTPException(status_code=400, detail="no questions to grade")
    if any(a is None for a in answers[: len(questions)]):
        raise HTTPException(status_code=400, detail="every question must be answered")

    self_ratings = req.selfRatings or {}
    results = _derive_levels(questions, answers)
    for r in results:
        rated = self_ratings.get(r["competencyId"])
        if rated is not None:
            r["selfRatedLevel"] = _safe_int(rated, r["derivedLevel"])
            r["perceptionGap"] = r["derivedLevel"] - r["selfRatedLevel"]

    total = len(questions)
    correct = _count_correct(questions, answers)
    test_id = req.testId or f"ct-{uuid.uuid4().hex[:12]}"
    taken_at = time.strftime("%Y-%m-%dT%H:%M:%SZ")

    if req.userId:
        # Grading must always be recorded against the verified session, never
        # against a userId in the body — otherwise anyone could write their own
        # results onto another learner's profile.
        if req.userId != identity.id:
            raise HTTPException(
                status_code=403, detail="You can only submit your own assessment"
            )
        try:
            _persist_questions(identity.id, test_id, taken_at, questions, answers)
        except Exception:
            # Persistence is best-effort: grading must still succeed offline or
            # against a read-only database.
            pass

    return {
        "id": test_id,
        "role": req.role,
        "roleLabel": req.roleLabel,
        "competencies": [r["competencyName"] for r in results],
        "questions": questions,
        "results": results,
        "questionsAttempted": total,
        "correctCount": correct,
        "accuracyPct": round((correct / total * 100) if total else 0),
        "takenAt": taken_at,
        "locked": True,
    }
