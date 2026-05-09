"""Resource feedback and URL verification cache."""
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Float, UniqueConstraint, Index
from datetime import datetime
from app.db.database import Base


class ResourceFeedback(Base):
    """User's 👍/👎 vote on a resource. Used to bubble up the most helpful links."""
    __tablename__ = "resource_feedback"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    lesson_id = Column(Integer, ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False)
    resource_url = Column(String, nullable=False)
    is_helpful = Column(Boolean, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "lesson_id", "resource_url", name="uq_user_lesson_resource"),
        Index("ix_feedback_lesson_url", "lesson_id", "resource_url"),
    )


class ResourceCheck(Base):
    """Cached HTTP verification status for a URL (fresh for 7 days)."""
    __tablename__ = "resource_checks"

    id = Column(Integer, primary_key=True, index=True)
    url = Column(String, unique=True, index=True, nullable=False)
    is_alive = Column(Boolean, default=False)
    status_code = Column(Integer, nullable=True)
    final_url = Column(String, nullable=True)
    title = Column(String, nullable=True)
    domain = Column(String, nullable=True)
    quality_score = Column(Float, default=0.0)
    is_curated_source = Column(Boolean, default=False)
    last_checked = Column(DateTime, default=datetime.utcnow)