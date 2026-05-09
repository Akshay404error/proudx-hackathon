"""Report generation + email delivery endpoints."""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
import io

from app.db.database import get_db
from app.api.deps import get_current_user
from app.models import User, Roadmap, Lesson, Milestone
from app.services.report_service import (
    generate_progress_report, generate_resource_bundle, generate_certificate,
)
from app.services.email_service import send_report_email

router = APIRouter(prefix="/reports", tags=["reports"])


class EmailReportRequest(BaseModel):
    report_type: str   # "progress" | "bundle" | "certificate"
    roadmap_id: int | None = None
    to_email: str | None = None


def _get_roadmap_or_404(db: Session, roadmap_id: int, user_id: int) -> Roadmap:
    rm = db.query(Roadmap).filter(Roadmap.id == roadmap_id, Roadmap.user_id == user_id).first()
    if not rm:
        raise HTTPException(404, "Roadmap not found")
    return rm


def _check_certificate_eligible(rm: Roadmap):
    total = sum(len(m.lessons) for m in rm.milestones)
    done = sum(1 for m in rm.milestones for l in m.lessons if l.is_completed)
    if total == 0 or done < total:
        raise HTTPException(400, f"Roadmap not yet complete ({done}/{total} lessons done). "
                                 f"Finish all lessons to unlock the certificate.")


@router.get("/progress.pdf")
def progress_report_pdf(
    roadmap_id: int | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rm = None
    if roadmap_id:
        rm = _get_roadmap_or_404(db, roadmap_id, user.id)
    pdf_bytes = generate_progress_report(db, user, rm)
    return StreamingResponse(
        io.BytesIO(pdf_bytes), media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="pathforge_progress_{user.username}.pdf"'},
    )


@router.get("/bundle.pdf")
def resource_bundle_pdf(
    roadmap_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rm = _get_roadmap_or_404(db, roadmap_id, user.id)
    pdf_bytes = generate_resource_bundle(db, user, rm)
    return StreamingResponse(
        io.BytesIO(pdf_bytes), media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="pathforge_bundle_{rm.id}.pdf"'},
    )


@router.get("/certificate.pdf")
def certificate_pdf(
    roadmap_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rm = _get_roadmap_or_404(db, roadmap_id, user.id)
    _check_certificate_eligible(rm)
    pdf_bytes = generate_certificate(user, rm)
    return StreamingResponse(
        io.BytesIO(pdf_bytes), media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="pathforge_certificate_{rm.id}.pdf"'},
    )


@router.post("/email")
async def email_report(
    req: EmailReportRequest,
    background: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    target_email = req.to_email or user.email
    rm = None
    if req.roadmap_id:
        rm = _get_roadmap_or_404(db, req.roadmap_id, user.id)

    if req.report_type == "progress":
        pdf = generate_progress_report(db, user, rm)
        filename = f"pathforge_progress_{user.username}.pdf"
        subject = "Your PathForge progress report"
    elif req.report_type == "bundle":
        if not rm:
            raise HTTPException(400, "roadmap_id is required for bundle reports")
        pdf = generate_resource_bundle(db, user, rm)
        filename = f"pathforge_bundle_{rm.id}.pdf"
        subject = f"PathForge Resources: {rm.title}"
    elif req.report_type == "certificate":
        if not rm:
            raise HTTPException(400, "roadmap_id is required for certificates")
        _check_certificate_eligible(rm)
        pdf = generate_certificate(user, rm)
        filename = f"pathforge_certificate_{rm.id}.pdf"
        subject = f"🏆 Your PathForge Certificate: {rm.title}"
    else:
        raise HTTPException(400, "Invalid report_type")

    background.add_task(
        send_report_email, target_email, subject, filename, pdf,
        user.full_name or user.username,
    )
    return {"ok": True, "message": f"Report will be emailed to {target_email}", "filename": filename}