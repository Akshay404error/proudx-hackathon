"""Progress activity log for streak tracking and analytics."""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Date
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.database import Base


class ProgressLog(Base):
    __tablename__ = "progress_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    activity_date = Column(Date, default=datetime.utcnow().date, index=True)
    activity_type = Column(String, nullable=False)  # lesson_completed, project_submitted, chat
    reference_id = Column(Integer, nullable=True)  # lesson/project id
    xp_earned = Column(Integer, default=0)
    note = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="progress_logs")
