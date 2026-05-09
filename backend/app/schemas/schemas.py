"""Pydantic schemas — request/response validation."""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime, date


# ---------- User ----------
class UserCreate(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=30)
    password: str = Field(..., min_length=6)
    full_name: Optional[str] = None
    role: str = "learner"


class UserLogin(BaseModel):
    email: EmailStr
    password: str


# ---------- OTP flow ----------
class SignupRequest(BaseModel):
    """Step 1: collect signup info, send OTP to email."""
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=30)
    password: str = Field(..., min_length=6)
    full_name: Optional[str] = None
    role: str = "learner"


class LoginRequest(BaseModel):
    """Step 1: verify password, send OTP to email."""
    email: EmailStr
    password: str


class OTPVerifyRequest(BaseModel):
    """Step 2: submit OTP to finalize signup or login."""
    email: EmailStr
    code: str = Field(..., min_length=4, max_length=10)
    purpose: str = Field(..., pattern="^(signup|login)$")


class OTPRequestStatus(BaseModel):
    """Generic 'we sent you an OTP' response."""
    ok: bool = True
    email: str
    purpose: str
    expires_in_minutes: int
    message: str


class UserOut(BaseModel):
    id: int
    email: str
    username: str
    full_name: Optional[str]
    role: str
    bio: Optional[str]
    avatar_url: Optional[str]
    current_streak: int
    longest_streak: int
    total_xp: int
    is_public_profile: bool
    created_at: datetime

    class Config:
        from_attributes = True


class UserPublicProfile(BaseModel):
    username: str
    full_name: Optional[str]
    bio: Optional[str]
    avatar_url: Optional[str]
    current_streak: int
    longest_streak: int
    total_xp: int
    roadmaps_count: int
    completed_lessons: int

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ---------- Roadmap ----------
class ResourceItem(BaseModel):
    title: str
    url: str
    type: str = "article"  # video / article / docs / interactive


class LessonOut(BaseModel):
    id: int
    title: str
    summary: Optional[str]
    content_type: str
    resources: List[ResourceItem] = []
    order_index: int
    estimated_minutes: int
    xp_reward: int
    is_completed: bool
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


class ProjectOut(BaseModel):
    id: int
    title: str
    description: str
    requirements: List[str] = []
    submission_url: Optional[str]
    is_completed: bool
    xp_reward: int

    class Config:
        from_attributes = True


class MilestoneOut(BaseModel):
    id: int
    title: str
    description: Optional[str]
    order_index: int
    estimated_hours: int
    is_completed: bool
    lessons: List[LessonOut] = []
    projects: List[ProjectOut] = []

    class Config:
        from_attributes = True


class RoadmapOut(BaseModel):
    id: int
    user_id: int
    title: str
    goal: str
    description: Optional[str]
    duration_weeks: int
    skill_level: str
    is_public: bool
    is_active: bool
    created_at: datetime
    milestones: List[MilestoneOut] = []

    class Config:
        from_attributes = True


class RoadmapSummary(BaseModel):
    id: int
    title: str
    goal: str
    duration_weeks: int
    skill_level: str
    created_at: datetime
    progress_percent: float = 0.0

    class Config:
        from_attributes = True


# ---------- Chat / Generation ----------
class ChatMessage(BaseModel):
    message: str
    conversation_id: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    suggest_roadmap: bool = False
    extracted_goal: Optional[str] = None


class GenerateRoadmapRequest(BaseModel):
    goal: str = Field(..., min_length=5)
    skill_level: str = "beginner"
    duration_weeks: int = Field(default=12, ge=2, le=52)
    hours_per_week: int = Field(default=10, ge=1, le=60)
    extra_context: Optional[str] = None


# ---------- Progress ----------
class CompleteLessonRequest(BaseModel):
    lesson_id: int


class ProgressDayCount(BaseModel):
    activity_date: date
    count: int
    xp_earned: int


class StreakInfo(BaseModel):
    current_streak: int
    longest_streak: int
    total_xp: int
    last_active: Optional[datetime]
    weekly_activity: List[ProgressDayCount]


# ---------- Mentor view ----------
class LearnerSummary(BaseModel):
    id: int
    username: str
    full_name: Optional[str]
    current_streak: int
    total_xp: int
    active_roadmap_title: Optional[str]
    progress_percent: float

    class Config:
        from_attributes = True
