"""User model — learners, mentors, and institutions."""
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from app.db.database import Base


class UserRole(str, enum.Enum):
    LEARNER = "learner"
    MENTOR = "mentor"
    INSTITUTION = "institution"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=True)
    hashed_password = Column(String, nullable=False)
    role = Column(Enum(UserRole), default=UserRole.LEARNER, nullable=False)
    bio = Column(String, nullable=True)
    avatar_url = Column(String, nullable=True)
    is_public_profile = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Streak tracking
    current_streak = Column(Integer, default=0)
    longest_streak = Column(Integer, default=0)
    last_activity_date = Column(DateTime, nullable=True)
    total_xp = Column(Integer, default=0)

    # Relationships
    roadmaps = relationship("Roadmap", back_populates="user", cascade="all, delete-orphan")
    progress_logs = relationship("ProgressLog", back_populates="user", cascade="all, delete-orphan")