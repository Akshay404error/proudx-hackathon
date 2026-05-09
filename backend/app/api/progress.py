"""Progress tracking — lesson completion, streaks, heatmap."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from app.db.database import get_db
from app.api.deps import get_current_user
from app.models import User, Lesson, Project, Milestone, Roadmap
from app.schemas.schemas import (
    CompleteLessonRequest, StreakInfo, ProgressDayCount,
)
from app.services.roadmap_service import log_activity, get_weekly_activity


router = APIRouter(prefix="/progress", tags=["progress"])


def _verify_lesson_ownership(db: Session, lesson_id: int, user_id: int) -> Lesson:
    lesson = (
        db.query(Lesson)
        .join(Milestone)
        .join(Roadmap)
        .filter(Lesson.id == lesson_id, Roadmap.user_id == user_id)
        .first()
    )
    if not lesson:
        raise HTTPException(404, "Lesson not found")
    return lesson


@router.post("/lesson/complete")
def complete_lesson(
    req: CompleteLessonRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    lesson = _verify_lesson_ownership(db, req.lesson_id, user.id)
    if lesson.is_completed:
        return {"already_completed": True, "lesson_id": lesson.id}

    lesson.is_completed = True
    lesson.completed_at = datetime.utcnow()
    db.flush()

    log_activity(
        db, user, "lesson_completed",
        reference_id=lesson.id, xp=lesson.xp_reward,
        note=lesson.title,
    )

    # Auto-complete milestone if all its lessons done
    milestone = db.query(Milestone).filter(Milestone.id == lesson.milestone_id).first()
    if milestone and all(l.is_completed for l in milestone.lessons):
        milestone.is_completed = True
        db.commit()

    return {
        "ok": True,
        "lesson_id": lesson.id,
        "xp_earned": lesson.xp_reward,
        "current_streak": user.current_streak,
        "total_xp": user.total_xp,
    }


@router.post("/lesson/uncomplete")
def uncomplete_lesson(
    req: CompleteLessonRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    lesson = _verify_lesson_ownership(db, req.lesson_id, user.id)
    if not lesson.is_completed:
        return {"ok": True}
    lesson.is_completed = False
    lesson.completed_at = None
    # Reverse XP
    user.total_xp = max(0, (user.total_xp or 0) - lesson.xp_reward)
    # Mark milestone incomplete too
    milestone = db.query(Milestone).filter(Milestone.id == lesson.milestone_id).first()
    if milestone:
        milestone.is_completed = False
    db.commit()
    return {"ok": True, "total_xp": user.total_xp}


@router.get("/streak", response_model=StreakInfo)
def get_streak(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    weekly = get_weekly_activity(db, user.id, days=30)
    return StreakInfo(
        current_streak=user.current_streak,
        longest_streak=user.longest_streak,
        total_xp=user.total_xp,
        last_active=user.last_activity_date,
        weekly_activity=[ProgressDayCount(**d) for d in weekly],
    )
