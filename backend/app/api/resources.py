"""Resource verification + feedback endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List

from app.db.database import get_db
from app.api.deps import get_current_user
from app.models import User, Lesson, Milestone, Roadmap, ResourceFeedback
from app.services.url_checker import verify_and_score, feedback_counts_for

router = APIRouter(prefix="/resources", tags=["resources"])


class VerifyRequest(BaseModel):
    lesson_id: int


class FeedbackRequest(BaseModel):
    lesson_id: int
    resource_url: str
    is_helpful: bool


def _verify_lesson_access(db: Session, lesson_id: int, user_id: int) -> Lesson:
    lesson = (
        db.query(Lesson).join(Milestone).join(Roadmap)
        .filter(Lesson.id == lesson_id, Roadmap.user_id == user_id)
        .first()
    )
    if not lesson:
        raise HTTPException(404, "Lesson not found")
    return lesson


@router.post("/verify")
async def verify_lesson_resources(
    req: VerifyRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Verify all URLs in a lesson + return scored results."""
    lesson = _verify_lesson_access(db, req.lesson_id, user.id)
    urls = [r.get("url") for r in (lesson.resources or []) if isinstance(r, dict) and r.get("url")]
    scored = await verify_and_score(db, urls, lesson_id=lesson.id)
    return {"lesson_id": lesson.id, "results": scored}


@router.post("/feedback")
def submit_feedback(
    req: FeedbackRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Submit or flip a 👍/👎 vote on a resource."""
    _verify_lesson_access(db, req.lesson_id, user.id)

    existing = (
        db.query(ResourceFeedback)
        .filter(ResourceFeedback.user_id == user.id,
                ResourceFeedback.lesson_id == req.lesson_id,
                ResourceFeedback.resource_url == req.resource_url)
        .first()
    )
    if existing:
        existing.is_helpful = req.is_helpful
    else:
        db.add(ResourceFeedback(
            user_id=user.id, lesson_id=req.lesson_id,
            resource_url=req.resource_url, is_helpful=req.is_helpful,
        ))
    db.commit()

    helpful, unhelpful = feedback_counts_for(db, req.lesson_id, req.resource_url)
    return {"ok": True, "helpful": helpful, "unhelpful": unhelpful, "your_vote": req.is_helpful}


@router.delete("/feedback")
def remove_feedback(
    lesson_id: int, resource_url: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    db.query(ResourceFeedback).filter(
        ResourceFeedback.user_id == user.id,
        ResourceFeedback.lesson_id == lesson_id,
        ResourceFeedback.resource_url == resource_url,
    ).delete()
    db.commit()
    helpful, unhelpful = feedback_counts_for(db, lesson_id, resource_url)
    return {"ok": True, "helpful": helpful, "unhelpful": unhelpful, "your_vote": None}