"""Pydantic models for SakshamAI API."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel


class CompetencyScore(BaseModel):
    competencyId: str
    level: int
    # Provenance for the test-derived results view. All optional so older
    # clients that send only {competencyId, level} keep working.
    source: Optional[str] = "default"
    accuracy: Optional[float] = None
    selfRatedLevel: Optional[int] = None
    testedAt: Optional[str] = None


class UserProfile(BaseModel):
    id: str
    name: str
    employeeId: Optional[str] = ""
    designation: Optional[str] = ""
    department: Optional[str] = ""
    role: str = "learner"
    currentRole: Optional[str] = ""
    education: Optional[str] = ""
    experience: Optional[int] = 0
    careerGoal: Optional[str] = ""
    previousTraining: Optional[str] = ""
    preferredLanguage: Optional[str] = "English"
    profileCompleted: Optional[bool] = False
    competencies: List[CompetencyScore] = []


class LoginRequest(BaseModel):
    """Credentials for a real sign-in.

    Was `role: str`, which let the caller pick who they became. The role is now
    resolved from the database row the verified token maps to, so it is not and
    must not be an input here.
    """

    email: str
    password: str


class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    employeeId: Optional[str] = None
    designation: Optional[str] = None
    department: Optional[str] = None
    currentRole: Optional[str] = None
    education: Optional[str] = None
    experience: Optional[int] = None
    careerGoal: Optional[str] = None
    previousTraining: Optional[str] = None
    preferredLanguage: Optional[str] = None
    profileCompleted: Optional[bool] = None


class CompetencyUpdate(BaseModel):
    competencies: List[CompetencyScore]


class GapRequest(BaseModel):
    role: str
    competencies: List[CompetencyScore]


class QuizGenerateRequest(BaseModel):
    text: str
    count: int = 5
    difficulty: str = "Medium"


class QuizSubmitRequest(BaseModel):
    user_id: str
    title: str
    questions: List[dict]
    answers: List[Optional[int]]


class EnrollRequest(BaseModel):
    user_id: str
    course_id: str

class AssessmentGenerateRequest(BaseModel):
    role: str
    roleLabel: str
    competencyIds: List[str]
    maxQuestions: int = 18
    questionsPerCompetency: int = 3


class AssessmentSubmitRequest(BaseModel):
    testId: Optional[str] = None
    role: str
    roleLabel: str
    questions: List[Dict[str, Any]]
    answers: List[Optional[int]] = []
    userId: Optional[str] = None
    selfRatings: Optional[Dict[str, int]] = None


class DeleteAccountRequest(BaseModel):
    """Confirmation for the destructive account-erasure call.

    Erasure cannot be undone, so the caller has to send the exact text
    `DELETE` rather than relying on a stray or replayed request. The endpoint
    also re-checks ownership server-side, so this guards against accidents and
    confused clients, not against a determined attacker who already holds a
    valid token for the account.
    """

    confirmation: str = ""
