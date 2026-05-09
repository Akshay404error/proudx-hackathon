"""Roadmap structure: Roadmap → Milestones → Lessons + Projects."""
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.database import Base


class Roadmap(Base):
    __tablename__ = "roadmaps"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String, nullable=False)
    goal = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    duration_weeks = Column(Integer, default=12)
    skill_level = Column(String, default="beginner")
    is_public = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="roadmaps")
    milestones = relationship(
        "Milestone", back_populates="roadmap",
        cascade="all, delete-orphan", order_by="Milestone.order_index"
    )


class Milestone(Base):
    __tablename__ = "milestones"

    id = Column(Integer, primary_key=True, index=True)
    roadmap_id = Column(Integer, ForeignKey("roadmaps.id", ondelete="CASCADE"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    order_index = Column(Integer, default=0)
    estimated_hours = Column(Integer, default=10)
    is_completed = Column(Boolean, default=False)

    roadmap = relationship("Roadmap", back_populates="milestones")
    lessons = relationship(
        "Lesson", back_populates="milestone",
        cascade="all, delete-orphan", order_by="Lesson.order_index"
    )
    projects = relationship(
        "Project", back_populates="milestone",
        cascade="all, delete-orphan"
    )


class Lesson(Base):
    __tablename__ = "lessons"

    id = Column(Integer, primary_key=True, index=True)
    milestone_id = Column(Integer, ForeignKey("milestones.id", ondelete="CASCADE"), nullable=False)
    title = Column(String, nullable=False)
    summary = Column(Text, nullable=True)
    content_type = Column(String, default="article")
    resources = Column(JSON, default=list)
    order_index = Column(Integer, default=0)
    estimated_minutes = Column(Integer, default=30)
    xp_reward = Column(Integer, default=10)
    is_completed = Column(Boolean, default=False)
    completed_at = Column(DateTime, nullable=True)

    milestone = relationship("Milestone", back_populates="lessons")


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    milestone_id = Column(Integer, ForeignKey("milestones.id", ondelete="CASCADE"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    requirements = Column(JSON, default=list)
    submission_url = Column(String, nullable=True)
    is_completed = Column(Boolean, default=False)
    xp_reward = Column(Integer, default=100)

    milestone = relationship("Milestone", back_populates="projects")