"""Public profile & mentor dashboard endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.db.database import get_db
from app.api.deps import get_current_user
from app.models import User, Roadmap, Lesson, Milestone, UserRole
from app.schemas.schemas import (
    UserOut, UserPublicProfile, RoadmapSummary, LearnerSummary,
)
from app.services.roadmap_service import compute_progress_percent


router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("/me", response_model=UserOut)
def get_me(user: User = Depends(get_current_user)):
    return user


@router.patch("/me", response_model=UserOut)
def update_me(
    full_name: str = None,
    bio: str = None,
    avatar_url: str = None,
    is_public_profile: bool = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if full_name is not None:
        user.full_name = full_name
    if bio is not None:
        user.bio = bio
    if avatar_url is not None:
        user.avatar_url = avatar_url
    if is_public_profile is not None:
        user.is_public_profile = is_public_profile
    db.commit()
    db.refresh(user)
    return user


@router.get("/u/{username}", response_model=UserPublicProfile)
def public_profile(username: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(404, "User not found")
    if not user.is_public_profile:
        raise HTTPException(403, "This profile is private")

    roadmaps_count = db.query(Roadmap).filter(Roadmap.user_id == user.id).count()
    completed_lessons = (
        db.query(Lesson)
        .join(Milestone).join(Roadmap)
        .filter(Roadmap.user_id == user.id, Lesson.is_completed == True)  # noqa
        .count()
    )

    return UserPublicProfile(
        username=user.username,
        full_name=user.full_name,
        bio=user.bio,
        avatar_url=user.avatar_url,
        current_streak=user.current_streak,
        longest_streak=user.longest_streak,
        total_xp=user.total_xp,
        roadmaps_count=roadmaps_count,
        completed_lessons=completed_lessons,
    )


@router.get("/u/{username}/roadmaps", response_model=List[RoadmapSummary])
def public_roadmaps(username: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == username).first()
    if not user or not user.is_public_profile:
        raise HTTPException(404, "Not found")
    rms = db.query(Roadmap).filter(
        Roadmap.user_id == user.id, Roadmap.is_public == True  # noqa
    ).order_by(Roadmap.created_at.desc()).all()
    out = []
    for rm in rms:
        s = RoadmapSummary.model_validate(rm)
        s.progress_percent = compute_progress_percent(db, rm.id)
        out.append(s)
    return out


# ---------- Mentor / Institution view ----------

@router.get("/mentor/learners", response_model=List[LearnerSummary])
def list_learners(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mentors and institutions can see all public learner profiles."""
    if user.role not in (UserRole.MENTOR, UserRole.INSTITUTION):
        raise HTTPException(403, "Mentor or institution role required")

    learners = db.query(User).filter(
        User.role == UserRole.LEARNER, User.is_public_profile == True  # noqa
    ).all()

    out = []
    for l in learners:
        active_rm = db.query(Roadmap).filter(
            Roadmap.user_id == l.id, Roadmap.is_active == True  # noqa
        ).order_by(Roadmap.created_at.desc()).first()

        progress = compute_progress_percent(db, active_rm.id) if active_rm else 0.0
        out.append(LearnerSummary(
            id=l.id,
            username=l.username,
            full_name=l.full_name,
            current_streak=l.current_streak,
            total_xp=l.total_xp,
            active_roadmap_title=active_rm.title if active_rm else None,
            progress_percent=progress,
        ))
    return out
