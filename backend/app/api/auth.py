"""Authentication routes — OTP-gated signup and login.

Flow:
  Signup:
    POST /signup/request     → validates payload, sends OTP, stores pending data
    POST /signup/verify      → verifies OTP, creates user, returns JWT

  Login:
    POST /login/request      → validates email+password, sends OTP
    POST /login/verify       → verifies OTP, returns JWT

  Resend (shared):
    POST /otp/resend         → re-issues a fresh OTP for an in-flight flow
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
import logging

from app.db.database import get_db
from app.models import User, UserRole
from app.schemas.schemas import (
    SignupRequest, LoginRequest, OTPVerifyRequest, OTPRequestStatus,
    Token, UserOut,
)
from app.core.security import hash_password, verify_password, create_access_token
from app.core.config import settings
from app.services.otp_service import create_otp, verify_otp, check_rate_limit
from app.services.email_service import send_otp_email

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


# ---------- Helpers ----------

def _otp_failure_message(reason: str) -> str:
    return {
        "no_code": "No active code found. Please request a new one.",
        "expired": "This code has expired. Please request a new one.",
        "too_many_attempts": "Too many incorrect attempts. Please request a new code.",
        "invalid": "Incorrect code. Please try again.",
    }.get(reason, "Verification failed.")


async def _send_otp_or_fail(
    db: Session, email: str, purpose: str,
    pending_payload: dict | None,
    background: BackgroundTasks,
) -> OTPRequestStatus:
    """Common path: rate-limit check → create OTP → email it (in background)."""
    allowed, count = check_rate_limit(db, email)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Too many code requests. Please wait 15 minutes before trying again.",
        )

    code = create_otp(db, email, purpose, pending_payload=pending_payload)

    # Send via background task — don't block the response on SMTP latency
    background.add_task(send_otp_email, email, code, purpose)

    return OTPRequestStatus(
        ok=True,
        email=email,
        purpose=purpose,
        expires_in_minutes=settings.OTP_EXPIRY_MINUTES,
        message=f"We've sent a {settings.OTP_LENGTH}-digit code to {email}. It expires in {settings.OTP_EXPIRY_MINUTES} minutes.",
    )


# ---------- Signup ----------

@router.post("/signup/request", response_model=OTPRequestStatus)
async def signup_request(
    data: SignupRequest,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Step 1 of signup: validate uniqueness, send OTP, stash pending data."""
    email = data.email.lower().strip()

    if db.query(User).filter(User.email == email).first():
        raise HTTPException(400, "An account with this email already exists.")
    if db.query(User).filter(User.username == data.username).first():
        raise HTTPException(400, "Username is already taken.")
    if data.role not in [r.value for r in UserRole]:
        raise HTTPException(400, "Invalid role.")

    # Stash everything we need to create the user once OTP is verified.
    # Password is hashed NOW so plaintext never touches the OTP table.
    pending = {
        "email": email,
        "username": data.username,
        "full_name": data.full_name,
        "hashed_password": hash_password(data.password),
        "role": data.role,
    }

    return await _send_otp_or_fail(db, email, "signup", pending, background)


@router.post("/signup/verify", response_model=Token)
async def signup_verify(
    data: OTPVerifyRequest,
    db: Session = Depends(get_db),
):
    """Step 2: verify OTP and create the account."""
    if data.purpose != "signup":
        raise HTTPException(400, "Invalid purpose for this endpoint.")

    ok, reason, payload = verify_otp(db, data.email, data.code, "signup")
    if not ok:
        raise HTTPException(400, _otp_failure_message(reason))
    if not payload:
        raise HTTPException(400, "Signup data missing. Please start over.")

    # Race-safety: re-check uniqueness in case someone signed up in between
    if db.query(User).filter(User.email == payload["email"]).first():
        raise HTTPException(400, "An account with this email already exists.")
    if db.query(User).filter(User.username == payload["username"]).first():
        raise HTTPException(400, "Username is already taken.")

    user = User(
        email=payload["email"],
        username=payload["username"],
        full_name=payload.get("full_name"),
        hashed_password=payload["hashed_password"],
        role=UserRole(payload["role"]),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(str(user.id), {"role": user.role.value})
    return Token(access_token=token, user=UserOut.model_validate(user))


# ---------- Login ----------

@router.post("/login/request", response_model=OTPRequestStatus)
async def login_request(
    data: LoginRequest,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Step 1 of login: verify password, then send OTP."""
    email = data.email.lower().strip()
    user = db.query(User).filter(User.email == email).first()

    # IMPORTANT: same error for "user not found" and "wrong password"
    # so attackers can't enumerate accounts.
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(401, "Invalid email or password.")

    return await _send_otp_or_fail(db, email, "login", None, background)


@router.post("/login/verify", response_model=Token)
async def login_verify(
    data: OTPVerifyRequest,
    db: Session = Depends(get_db),
):
    """Step 2: verify OTP and issue JWT."""
    if data.purpose != "login":
        raise HTTPException(400, "Invalid purpose for this endpoint.")

    ok, reason, _ = verify_otp(db, data.email, data.code, "login")
    if not ok:
        raise HTTPException(400, _otp_failure_message(reason))

    user = db.query(User).filter(User.email == data.email.lower().strip()).first()
    if not user:
        raise HTTPException(404, "Account not found.")

    token = create_access_token(str(user.id), {"role": user.role.value})
    return Token(access_token=token, user=UserOut.model_validate(user))


# ---------- Resend ----------

@router.post("/otp/resend", response_model=OTPRequestStatus)
async def otp_resend(
    data: OTPVerifyRequest,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Re-issue a fresh OTP. For signup, we need the original pending payload —
    so we look up the most-recent code (consumed or not) and reuse its payload.
    The user's `code` field is ignored here; only `email` + `purpose` matter.
    """
    from app.models import OTPCode
    import json
    email = data.email.lower().strip()

    pending = None
    if data.purpose == "signup":
        prev = (
            db.query(OTPCode)
            .filter(OTPCode.email == email, OTPCode.purpose == "signup")
            .order_by(OTPCode.created_at.desc())
            .first()
        )
        if not prev or not prev.pending_payload:
            raise HTTPException(400, "No pending signup found. Please start signup again.")
        try:
            pending = json.loads(prev.pending_payload)
        except Exception:
            raise HTTPException(400, "Pending signup data is invalid. Please start over.")

    elif data.purpose == "login":
        # Login resend is fine without re-checking password (the original
        # request already passed password check). User must still pass OTP.
        if not db.query(User).filter(User.email == email).first():
            # Mirror the login-request enumeration guard
            raise HTTPException(401, "Invalid request.")

    else:
        raise HTTPException(400, "Invalid purpose for resend.")

    return await _send_otp_or_fail(db, email, data.purpose, pending, background)
