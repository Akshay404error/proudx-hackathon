"""Service: persist AI-generated roadmaps and compute progress."""
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta, date
from app.models import Roadmap, Milestone, Lesson, Project, ProgressLog, User


def _is_safe_url(url: str) -> bool:
    """Filter out hallucinated / junk URLs before persisting them.

    Rules:
      - Must start with http:// or https://
      - Block YouTube /watch and youtu.be (most-hallucinated by local LLMs).
        Channel pages (@username) and playlists are still allowed.
      - Block javascript:, mailto:, anchor-only, etc.
    """
    if not url or not isinstance(url, str):
        return False
    url = url.strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        return False
    lower = url.lower()
    # Block hallucinated YouTube watch URLs (the main offender)
    if "youtube.com/watch" in lower:
        return False
    if lower.startswith("https://youtu.be/") or lower.startswith("http://youtu.be/"):
        return False
    return True


def create_roadmap_from_ai(
    db: Session,
    user_id: int,
    ai_output: Dict[str, Any],
    goal: str,
    skill_level: str,
    duration_weeks: int,
) -> Roadmap:
    """Persist an AI-generated roadmap dict into DB rows."""
    rm = Roadmap(
        user_id=user_id,
        title=ai_output.get("title", f"Path: {goal[:50]}"),
        goal=goal,
        description=ai_output.get("description", ""),
        duration_weeks=duration_weeks,
        skill_level=skill_level,
    )
    db.add(rm)
    db.flush()

    for m_idx, m_data in enumerate(ai_output.get("milestones", [])):
        ms = Milestone(
            roadmap_id=rm.id,
            title=m_data.get("title", f"Milestone {m_idx + 1}"),
            description=m_data.get("description", ""),
            order_index=m_idx,
            estimated_hours=int(m_data.get("estimated_hours", 10) or 10),
        )
        db.add(ms)
        db.flush()

        for l_idx, l_data in enumerate(m_data.get("lessons", [])):
            resources = l_data.get("resources", []) or []
            # Normalize resource list + filter hallucinated URLs
            clean_res = []
            for r in resources:
                if not isinstance(r, dict) or not r.get("url"):
                    continue
                url = r["url"].strip()
                if not _is_safe_url(url):
                    continue
                clean_res.append({
                    "title": r.get("title", "Resource"),
                    "url": url,
                    "type": r.get("type", "article"),
                })

            lesson = Lesson(
                milestone_id=ms.id,
                title=l_data.get("title", f"Lesson {l_idx + 1}"),
                summary=l_data.get("summary", ""),
                content_type=l_data.get("content_type", "article"),
                resources=clean_res,
                order_index=l_idx,
                estimated_minutes=int(l_data.get("estimated_minutes", 30) or 30),
                xp_reward=10,
            )
            db.add(lesson)

        for p_data in m_data.get("projects", []):
            proj = Project(
                milestone_id=ms.id,
                title=p_data.get("title", "Capstone Project"),
                description=p_data.get("description", ""),
                requirements=p_data.get("requirements", []) or [],
                xp_reward=100,
            )
            db.add(proj)

    db.commit()
    db.refresh(rm)
    return rm


def compute_progress_percent(db: Session, roadmap_id: int) -> float:
    total = db.query(Lesson).join(Milestone).filter(Milestone.roadmap_id == roadmap_id).count()
    if total == 0:
        return 0.0
    done = (
        db.query(Lesson)
        .join(Milestone)
        .filter(Milestone.roadmap_id == roadmap_id, Lesson.is_completed == True)  # noqa: E712
        .count()
    )
    return round((done / total) * 100, 1)


def update_streak(db: Session, user: User) -> None:
    """Update streak based on activity_date logic.
    Streak rules: contiguous days of activity. Misses one day → reset to 1 today.
    """
    today = datetime.utcnow().date()
    last = user.last_activity_date.date() if user.last_activity_date else None

    if last == today:
        return  # already counted today
    if last == today - timedelta(days=1):
        user.current_streak += 1
    else:
        user.current_streak = 1

    user.longest_streak = max(user.longest_streak, user.current_streak)
    user.last_activity_date = datetime.utcnow()


def log_activity(
    db: Session,
    user: User,
    activity_type: str,
    reference_id: int = None,
    xp: int = 0,
    note: str = None,
) -> None:
    log = ProgressLog(
        user_id=user.id,
        activity_date=datetime.utcnow().date(),
        activity_type=activity_type,
        reference_id=reference_id,
        xp_earned=xp,
        note=note,
    )
    db.add(log)
    user.total_xp = (user.total_xp or 0) + xp
    update_streak(db, user)
    db.commit()


def get_weekly_activity(db: Session, user_id: int, days: int = 30) -> List[dict]:
    """Return per-day activity counts for the last N days (heatmap data)."""
    start = datetime.utcnow().date() - timedelta(days=days - 1)
    rows = (
        db.query(
            ProgressLog.activity_date,
            func.count(ProgressLog.id).label("count"),
            func.coalesce(func.sum(ProgressLog.xp_earned), 0).label("xp"),
        )
        .filter(ProgressLog.user_id == user_id, ProgressLog.activity_date >= start)
        .group_by(ProgressLog.activity_date)
        .all()
    )
    activity_map = {r.activity_date: (r.count, r.xp) for r in rows}
    out = []
    for i in range(days):
        d = start + timedelta(days=i)
        count, xp = activity_map.get(d, (0, 0))
        out.append({"activity_date": d, "count": count, "xp_earned": int(xp)})
    return out