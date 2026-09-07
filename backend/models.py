"""Pydantic models for SakshamAI API."""

from typing import List, Optional
from pydantic import BaseModel


class CompetencyScore(BaseModel):
    competencyId: str
    level: int


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
    role: str  # "learner" | "admin"


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
