"""URL verification + quality scoring service."""
from __future__ import annotations
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Iterable
import httpx
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models import ResourceCheck, ResourceFeedback
from app.services.curator import (
    base_score_for_url, adjust_for_alive, adjust_for_feedback, domain_of
)

logger = logging.getLogger(__name__)

USER_AGENT = "PathForge/1.0 (resource-verifier)"
CACHE_TTL_DAYS = 7
HTTP_TIMEOUT = 8.0


def _is_cache_fresh(check: ResourceCheck) -> bool:
    return (datetime.utcnow() - check.last_checked) < timedelta(days=CACHE_TTL_DAYS)


async def _fetch_one(client: httpx.AsyncClient, url: str) -> dict:
    info = {"url": url, "is_alive": False, "status_code": None, "final_url": url}
    try:
        r = await client.head(url, follow_redirects=True, timeout=HTTP_TIMEOUT)
        if r.status_code in (405, 403, 400):
            r = await client.get(url, follow_redirects=True, timeout=HTTP_TIMEOUT)
        info["status_code"] = r.status_code
        info["final_url"] = str(r.url)
        info["is_alive"] = 200 <= r.status_code < 400
    except Exception as e:
        logger.info(f"URL check failed for {url}: {e}")
    return info


async def verify_urls_async(urls: Iterable[str]) -> dict[str, dict]:
    urls = list({u for u in urls if u})
    if not urls:
        return {}
    async with httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT},
        limits=httpx.Limits(max_connections=10),
    ) as client:
        results = await asyncio.gather(
            *[_fetch_one(client, u) for u in urls], return_exceptions=True
        )
    return {r["url"]: r for r in results if not isinstance(r, Exception)}


def feedback_counts_for(db: Session, lesson_id: int, url: str) -> tuple[int, int]:
    helpful = (
        db.query(func.count(ResourceFeedback.id))
        .filter(ResourceFeedback.lesson_id == lesson_id,
                ResourceFeedback.resource_url == url,
                ResourceFeedback.is_helpful == True)  # noqa
        .scalar() or 0
    )
    unhelpful = (
        db.query(func.count(ResourceFeedback.id))
        .filter(ResourceFeedback.lesson_id == lesson_id,
                ResourceFeedback.resource_url == url,
                ResourceFeedback.is_helpful == False)  # noqa
        .scalar() or 0
    )
    return helpful, unhelpful


async def verify_and_score(
    db: Session, urls: list[str], lesson_id: int | None = None
) -> dict[str, dict]:
    """For each URL: load cache or fetch, compute quality_score, return enriched dict."""
    urls = list({u for u in urls if u})
    if not urls:
        return {}

    # Pull existing cache rows
    existing = {
        r.url: r for r in db.query(ResourceCheck).filter(ResourceCheck.url.in_(urls)).all()
    }

    to_fetch = [u for u in urls if u not in existing or not _is_cache_fresh(existing[u])]
    if to_fetch:
        fetched = await verify_urls_async(to_fetch)
        for u, info in fetched.items():
            base, is_curated = base_score_for_url(u)
            score = adjust_for_alive(base, info["is_alive"])
            row = existing.get(u)
            if row is None:
                row = ResourceCheck(url=u)
                db.add(row)
                existing[u] = row
            row.is_alive = info["is_alive"]
            row.status_code = info["status_code"]
            row.final_url = info["final_url"]
            row.domain = domain_of(u)
            row.quality_score = score
            row.is_curated_source = is_curated
            row.last_checked = datetime.utcnow()
        db.commit()

    # Build response with feedback adjustments
    out = {}
    for u in urls:
        row = existing.get(u)
        if not row:
            base, is_curated = base_score_for_url(u)
            out[u] = {
                "url": u, "is_alive": False, "quality_score": adjust_for_alive(base, False),
                "is_curated_source": is_curated, "domain": domain_of(u),
                "status_code": None, "helpful": 0, "unhelpful": 0,
            }
            continue
        helpful, unhelpful = (0, 0)
        if lesson_id:
            helpful, unhelpful = feedback_counts_for(db, lesson_id, u)
        final_score = adjust_for_feedback(row.quality_score, helpful, unhelpful)
        out[u] = {
            "url": u,
            "is_alive": row.is_alive,
            "status_code": row.status_code,
            "domain": row.domain,
            "quality_score": round(final_score, 1),
            "is_curated_source": row.is_curated_source,
            "helpful": helpful,
            "unhelpful": unhelpful,
        }
    return out