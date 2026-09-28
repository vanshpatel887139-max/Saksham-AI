"""Pydantic models for SakshamAI API."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class CompetencyScore(BaseModel):
    competencyId: str = Field(max_length=64)
    level: int = Field(ge=1, le=5)
    # Provenance for the test-derived results view. All optional so older
    # clients that send only {competencyId, level} keep working.
    source: Optional[str] = Field(default="default", max_length=40)
    accuracy: Optional[float] = None
    selfRatedLevel: Optional[int] = Field(default=None, ge=1, le=5)
    testedAt: Optional[str] = Field(default=None, max_length=64)


class UserProfile(BaseModel):
    id: str = Field(max_length=64)
    name: str = Field(max_length=200)
    employeeId: Optional[str] = Field(default="", max_length=100)
    designation: Optional[str] = Field(default="", max_length=200)
    department: Optional[str] = Field(default="", max_length=200)
    role: str = Field(default="learner", max_length=32)
    currentRole: Optional[str] = Field(default="", max_length=200)
    education: Optional[str] = Field(default="", max_length=200)
    experience: Optional[int] = Field(default=0, ge=0, le=100)
    careerGoal: Optional[str] = Field(default="", max_length=1000)
    previousTraining: Optional[str] = Field(default="", max_length=1000)
    preferredLanguage: Optional[str] = Field(default="English", max_length=64)
    profileCompleted: Optional[bool] = False
    competencies: List[CompetencyScore] = Field(default=[])


class LoginRequest(BaseModel):
    """Credentials for a real sign-in.

    Was `role: str`, which let the caller pick who they became. The role is now
    resolved from the database row the verified token maps to, so it is not and
    must not be an input here.
    """

    # RFC 5321 caps the address itself at 254 and the password at whatever
    # Supabase enforces; bounding both also keeps the parsed body small.
    email: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=1, max_length=200)


class ProfileUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=200)
    employeeId: Optional[str] = Field(default=None, max_length=100)
    designation: Optional[str] = Field(default=None, max_length=200)
    department: Optional[str] = Field(default=None, max_length=200)
    currentRole: Optional[str] = Field(default=None, max_length=200)
    education: Optional[str] = Field(default=None, max_length=200)
    experience: Optional[int] = Field(default=None, ge=0, le=100)
    careerGoal: Optional[str] = Field(default=None, max_length=1000)
    previousTraining: Optional[str] = Field(default=None, max_length=1000)
    preferredLanguage: Optional[str] = Field(default=None, max_length=64)
    profileCompleted: Optional[bool] = None


class CompetencyUpdate(BaseModel):
    competencies: List[CompetencyScore] = Field(default=[])


class GapRequest(BaseModel):
    role: str = Field(min_length=1, max_length=100)
    competencies: List[CompetencyScore] = Field(default=[])


class QuizGenerateRequest(BaseModel):
    text: str = Field(min_length=1, max_length=200000)
    count: int = Field(default=5, ge=1, le=50)
    difficulty: str = Field(default="Medium", max_length=20)


class QuizSubmitRequest(BaseModel):
    user_id: str = Field(max_length=64)
    title: str = Field(min_length=1, max_length=200)
    questions: List[dict] = Field(default=[])
    answers: List[Optional[int]] = Field(default=[])


class EnrollRequest(BaseModel):
    user_id: str = Field(max_length=64)
    course_id: str = Field(min_length=1, max_length=100)


class AssessmentGenerateRequest(BaseModel):
    role: str = Field(min_length=1, max_length=100)
    roleLabel: str = Field(default="", max_length=200)
    competencyIds: List[str] = Field(default=[], max_length=200)
    maxQuestions: int = Field(default=18, ge=1, le=100)
    questionsPerCompetency: int = Field(default=3, ge=1, le=20)


class AssessmentSubmitRequest(BaseModel):
    testId: Optional[str] = Field(default=None, max_length=64)
    role: str = Field(min_length=1, max_length=100)
    roleLabel: str = Field(default="", max_length=200)
    questions: List[Dict[str, Any]] = Field(default=[])
    answers: List[Optional[int]] = Field(default=[], max_length=500)
    userId: Optional[str] = Field(default=None, max_length=64)
    selfRatings: Optional[Dict[str, int]] = None


class DeleteAccountRequest(BaseModel):
    """Confirmation for the destructive account-erasure call.

    Erasure cannot be undone, so the caller has to send the exact text
    `DELETE` rather than relying on a stray or replayed request. The endpoint
    also re-checks ownership server-side, so this guards against accidents and
    confused clients, not against a determined attacker who already holds a
    valid token for the account.
    """

    confirmation: str = Field(default="", max_length=16)
