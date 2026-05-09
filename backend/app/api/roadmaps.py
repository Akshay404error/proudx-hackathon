"""Roadmap CRUD + AI-powered generation."""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
from app.db.database import get_db
from app.api.deps import get_current_user
from app.models import User, Roadmap
from app.schemas.schemas import (
    GenerateRoadmapRequest, RoadmapOut, RoadmapSummary,
)
from app.services.ai_service import ollama_service
from app.services.roadmap_service import (
    create_roadmap_from_ai, compute_progress_percent,
)


router = APIRouter(prefix="/roadmaps", tags=["roadmaps"])


@router.post("/generate", response_model=RoadmapOut)
async def generate_roadmap(
    req: GenerateRoadmapRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Call Ollama to produce a structured roadmap, persist, return it."""
    ai_output = await ollama_service.generate_roadmap(
        goal=req.goal,
        skill_level=req.skill_level,
        duration_weeks=req.duration_weeks,
        hours_per_week=req.hours_per_week,
        extra_context=req.extra_context or "",
    )
    rm = create_roadmap_from_ai(
        db,
        user_id=user.id,
        ai_output=ai_output,
        goal=req.goal,
        skill_level=req.skill_level,
        duration_weeks=req.duration_weeks,
    )
    return rm


@router.get("/", response_model=List[RoadmapSummary])
def list_my_roadmaps(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rms = db.query(Roadmap).filter(Roadmap.user_id == user.id).order_by(Roadmap.created_at.desc()).all()
    out = []
    for rm in rms:
        summary = RoadmapSummary.model_validate(rm)
        summary.progress_percent = compute_progress_percent(db, rm.id)
        out.append(summary)
    return out


@router.get("/{roadmap_id}", response_model=RoadmapOut)
def get_roadmap(
    roadmap_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rm = db.query(Roadmap).filter(Roadmap.id == roadmap_id).first()
    if not rm:
        raise HTTPException(404, "Roadmap not found")
    if rm.user_id != user.id and not rm.is_public:
        raise HTTPException(403, "This roadmap is private")
    return rm


@router.delete("/{roadmap_id}")
def delete_roadmap(
    roadmap_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rm = db.query(Roadmap).filter(Roadmap.id == roadmap_id, Roadmap.user_id == user.id).first()
    if not rm:
        raise HTTPException(404, "Roadmap not found")
    db.delete(rm)
    db.commit()
    return {"ok": True}


@router.patch("/{roadmap_id}/visibility")
def toggle_visibility(
    roadmap_id: int,
    is_public: bool,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rm = db.query(Roadmap).filter(Roadmap.id == roadmap_id, Roadmap.user_id == user.id).first()
    if not rm:
        raise HTTPException(404, "Roadmap not found")
    rm.is_public = is_public
    db.commit()
    return {"is_public": rm.is_public}
