"""Quiz generation & management routes.

Supports REAL text extraction from uploaded files:
  - TXT   : direct read
  - PDF   : pdfplumber
  - DOCX  : python-docx
  - PPTX  : python-pptx
  - SRT/VTT : transcript parsing (strips timestamps) for video-based learning
"""

import os
import re
import time
import uuid
from io import BytesIO

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from psycopg.types.json import Json

from auth_tokens import Identity, current_identity, require_self_or_admin
from database import get_db_connection
from models import QuizGenerateRequest, QuizSubmitRequest
from llm import LLMUnavailableError, llm_available, model_name
from routers.logic import generate_quiz_questions, generate_quiz_questions_llm

router = APIRouter(prefix="/api/quiz", tags=["quiz"])

# Uploads are read in capped chunks rather than with a bare `await file.read()`.
# Without a bound, one signed-in user could send a multi-gigabyte body and take
# the process out with memory exhaustion. 20 MB is well above any real course
# handout.
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
UPLOAD_CHUNK = 1024 * 1024

# Extensions the upload endpoint will accept, enforced in extract_text().
_ALLOWED_UPLOAD_TYPES = {"pdf", "docx", "pptx", "ppt", "srt", "vtt", "txt"}


def _upload_limit() -> int:
    try:
        return max(1, int(os.environ.get("MAX_UPLOAD_BYTES") or MAX_UPLOAD_BYTES))
    except (TypeError, ValueError):
        return MAX_UPLOAD_BYTES


async def _read_capped(file: UploadFile, limit: int) -> bytes:
    """Read at most `limit` bytes, aborting as soon as the cap is passed.

    Reading in chunks matters: it is the streamed size that is checked, so an
    oversized upload is rejected early instead of after the whole body has
    already been buffered in memory.
    """
    buf = bytearray()
    while True:
        chunk = await file.read(UPLOAD_CHUNK)
        if not chunk:
            break
        buf.extend(chunk)
        if len(buf) > limit:
            raise HTTPException(
                status_code=413,
                detail=f"File too large (limit {limit // (1024 * 1024)} MB)",
            )
    return bytes(buf)


def _generate(content: str, count: int, difficulty: str) -> dict:
    """LLM-first MCQ generation with deterministic fallback."""
    if llm_available():
        try:
            questions = generate_quiz_questions_llm(content, count, difficulty)
            return {
                "questions": questions,
                "generatedBy": f"llm:{model_name()}",
            }
        except (LLMUnavailableError, ValueError):
            pass  # fall back to deterministic generator
    return {
        "questions": generate_quiz_questions(content, count, difficulty),
        "generatedBy": "mock",
    }


def extract_text_from_txt(data: bytes) -> str:
    return data.decode("utf-8", errors="ignore")


def extract_text_from_pdf(data: bytes) -> str:
    try:
        import pdfplumber
    except ImportError as e:
        raise HTTPException(status_code=500, detail="pdfplumber not installed") from e
    parts = []
    with pdfplumber.open(BytesIO(data)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            parts.append(text)
    return "\n".join(parts)


def extract_text_from_docx(data: bytes) -> str:
    try:
        import docx
    except ImportError as e:
        raise HTTPException(status_code=500, detail="python-docx not installed") from e
    document = docx.Document(BytesIO(data))
    return "\n".join(p.text for p in document.paragraphs)


def extract_text_from_pptx(data: bytes) -> str:
    try:
        from pptx import Presentation
    except ImportError as e:
        raise HTTPException(status_code=500, detail="python-pptx not installed") from e
    prs = Presentation(BytesIO(data))
    parts = []
    for slide in prs.slides:
        for shape in slide.shapes:
            if hasattr(shape, "text") and shape.text.strip():
                parts.append(shape.text)
    return "\n".join(parts)


def extract_text_from_transcript(data: bytes, is_vtt: bool) -> str:
    """Parse SRT/VTT subtitle/transcript files, removing timing and numbering."""
    raw = data.decode("utf-8", errors="ignore")
    if is_vtt:
        raw = re.sub(r"^WEBVTT.*?(\n\n|\n)", "", raw, count=1)
    raw = raw.replace("\ufeff", "")
    lines = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.isdigit() and len(line) <= 4:
            continue  # cue number
        if "-->" in line:
            continue  # timestamp
        if re.match(r"^\d{1,2}:\d{2}", line):
            continue
        # inline timestamps (VTT style) inside text
        line = re.sub(r"<[^>]+>", "", line)
        lines.append(line)
    return "\n".join(lines)


def extract_text(filename: str, data: bytes) -> str:
    # Strict allowlist, decided by extension and applied server-side. The
    # client's reported Content-Type is not trusted (it is attacker-supplied),
    # and there is no on-disk storage or serving, so there is nothing to scan
    # with — the lead control is simply refusing anything we have no extractor
    # for instead of silently parsing an unknown format as text. An .html or
    # .svg uploaded past this point could never execute (it is never written
    # to disk or returned with an HTML content type), but rejecting it keeps
    # the surface predictable.
    name = (filename or "").lower().rstrip("?")
    ext = name.rsplit(".", 1)[-1] if "." in name else ""
    if ext not in _ALLOWED_UPLOAD_TYPES:
        raise HTTPException(
            status_code=415,
            detail="Unsupported file type. Allowed: pdf, docx, pptx, ppt, srt, vtt, txt.",
        )
    if name.endswith(".pdf"):
        return extract_text_from_pdf(data)
    if name.endswith(".docx"):
        return extract_text_from_docx(data)
    if name.endswith(".pptx") or name.endswith(".ppt"):
        return extract_text_from_pptx(data)
    if name.endswith(".srt"):
        return extract_text_from_transcript(data, is_vtt=False)
    if name.endswith(".vtt"):
        return extract_text_from_transcript(data, is_vtt=True)
    return extract_text_from_txt(data)


@router.post("/generate")
def generate_quiz(
    req: QuizGenerateRequest, identity: Identity = Depends(current_identity)
):
    """LLM-assisted MCQ generation (falls back to deterministic logic)."""
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="No text provided")
    result = _generate(req.text, req.count, req.difficulty)
    return {
        "quizId": f"quiz-{int(time.time())}",
        "title": f"{req.difficulty} Quiz",
        "questions": result["questions"],
        "generatedBy": result["generatedBy"],
    }


@router.post("/generate/file")
async def generate_from_file(
    identity: Identity = Depends(current_identity),
    file: UploadFile = File(...),
    count: int = Form(5),
    difficulty: str = Form("Medium"),
):
    """Generate a quiz from an uploaded learning material (real text extraction)."""
    data = await _read_capped(file, _upload_limit())
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    filename = file.filename or "material.txt"
    content = extract_text(filename, data)
    if not content.strip():
        raise HTTPException(status_code=400, detail="Could not extract text from file")
    result = _generate(content, count, difficulty)
    return {
        "quizId": f"quiz-{int(time.time())}",
        "title": f"{difficulty} Quiz from {filename}",
        "questions": result["questions"],
        "generatedBy": result["generatedBy"],
    }


@router.post("/submit")
def submit_quiz(req: QuizSubmitRequest, identity: Identity = Depends(current_identity)):
    # Overwrite rather than read: everything below is about "who is this quiz
    # for", and the only defensible answer to that is the verified session.
    req.user_id = identity.id
    conn = get_db_connection()
    try:
        user = conn.execute("SELECT id FROM users WHERE id = %s", (req.user_id,)).fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        score = 0
        for i, q in enumerate(req.questions):
            if i < len(req.answers) and req.answers[i] == q.get("correctAnswer"):
                score += 1

        quiz_id = f"quiz-{uuid.uuid4().hex[:8]}"
        conn.execute(
            "INSERT INTO quizzes (id, user_id, title, date, score, total_questions) VALUES (%s, %s, %s, %s, %s, %s)",
            (quiz_id, req.user_id, req.title, time.strftime("%Y-%m-%d"), score, len(req.questions)),
        )
        for i, q in enumerate(req.questions):
            qid = f"qq-{uuid.uuid4().hex[:8]}"
            conn.execute(
                "INSERT INTO quiz_questions (id, quiz_id, question, options, correct_answer, user_answer, explanation, difficulty, source_excerpt) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    qid, quiz_id,                     q.get("question", ""),
                    # `options` is a jsonb column. Passing the bare Python list
                    # made psycopg send it as Postgres array syntax ("{a,b}"),
                    # which jsonb rejects with "invalid input syntax for type
                    # json" — so every quiz submission 500'd and `quizzes` was
                    # permanently empty, which is exactly why the dashboard's
                    # quiz average could never populate from the database.
                    # Json() sends real JSON instead.
                    Json(q.get("options") or []),
                    q.get("correctAnswer", 0),
                    req.answers[i] if i < len(req.answers) else None,
                    q.get("explanation", ""),
                    q.get("difficulty", ""),
                    q.get("sourceExcerpt", ""),
                ),
            )
        # The activity feed is what the dashboard's "Recent Activity" card
        # renders, and quiz.py wrote to `quizzes` without writing here — so
        # taking a quiz left no trace in the feed. `enroll` does write one
        # (courses.py), which is why enrolments appeared and attempts did not.
        conn.execute(
            "INSERT INTO activities (id, user_id, action, detail, date, icon) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (
                f"act-{uuid.uuid4().hex[:8]}",
                req.user_id,
                "Completed Quiz",
                f"{req.title} - Score: {round(score / len(req.questions) * 100) if req.questions else 0}%",
                time.strftime("%Y-%m-%d"),
                "📝",
            ),
        )
        conn.commit()
        return {"quizId": quiz_id, "score": score, "total": len(req.questions)}
    finally:
        conn.close()


@router.get("/history/{user_id}")
def quiz_history(user_id: str, identity: Identity = Depends(current_identity)):
    # Any learner could previously read any other learner's quiz history,
    # including their scores, just by changing the id in the path.
    require_self_or_admin(user_id, identity)
    conn = get_db_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM quizzes WHERE user_id = %s ORDER BY date DESC",
            (user_id,),
        ).fetchall()
        return [
            {
                "id": r["id"],
                "title": r["title"],
                "date": r["date"],
                "score": r["score"],
                "totalQuestions": r["total_questions"],
            }
            for r in rows
        ]
    finally:
        conn.close()