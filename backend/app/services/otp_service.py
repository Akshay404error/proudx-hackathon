"""OTP service — generate, persist, validate one-time passwords.

Security properties:
  - Code stored as bcrypt hash (never plaintext)
  - 6-digit cryptographically random (secrets.randbelow)
  - 10-min expiry (configurable)
  - Max 5 verify attempts per code (then code is invalidated)
  - Max 3 OTPs per 15 min per email (rate limit)
  - Constant-time comparison via bcrypt.checkpw
"""
from __future__ import annotations
import secrets
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple
import bcrypt
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models import OTPCode
from app.core.config import settings

logger = logging.getLogger(__name__)


def _generate_code(length: int = 6) -> str:
    """Cryptographically random N-digit code, zero-padded."""
    upper = 10 ** length
    n = secrets.randbelow(upper)
    return str(n).zfill(length)


def _hash_code(code: str) -> str:
    return bcrypt.hashpw(code.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_code(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def check_rate_limit(db: Session, email: str) -> Tuple[bool, int]:
    """Return (allowed, recent_count). Caps OTPs per 15-min window per email."""
    cutoff = datetime.utcnow() - timedelta(minutes=15)
    count = (
        db.query(OTPCode)
        .filter(OTPCode.email == email.lower(), OTPCode.created_at >= cutoff)
        .count()
    )
    return count < settings.OTP_RATE_LIMIT_PER_15MIN, count


def create_otp(
    db: Session,
    email: str,
    purpose: str,
    pending_payload: Optional[dict] = None,
) -> str:
    """Generate, hash-store, return the plaintext code (to be emailed).

    Plaintext code lives only in memory long enough to be emailed.
    Caller must NOT log it or store it elsewhere.
    """
    email_norm = email.lower().strip()

    # Invalidate any prior un-consumed codes for the same (email, purpose)
    # so only the latest code is valid — common UX expectation.
    db.query(OTPCode).filter(
        OTPCode.email == email_norm,
        OTPCode.purpose == purpose,
        OTPCode.consumed == False,  # noqa: E712
    ).update({"consumed": True}, synchronize_session=False)

    code = _generate_code(settings.OTP_LENGTH)
    record = OTPCode(
        email=email_norm,
        code_hash=_hash_code(code),
        purpose=purpose,
        expires_at=datetime.utcnow() + timedelta(minutes=settings.OTP_EXPIRY_MINUTES),
        attempts=0,
        consumed=False,
        pending_payload=json.dumps(pending_payload) if pending_payload else None,
    )
    db.add(record)
    db.commit()
    return code


def verify_otp(
    db: Session,
    email: str,
    code: str,
    purpose: str,
) -> Tuple[bool, str, Optional[dict]]:
    """Validate the OTP. Returns (ok, reason, pending_payload).

    Reasons on failure (for user-facing messages):
      - "no_code"         : no active code for this email/purpose
      - "expired"         : code has expired
      - "too_many_attempts": more than OTP_MAX_ATTEMPTS guesses tried
      - "invalid"         : wrong code (attempts incremented)
    """
    email_norm = email.lower().strip()
    code_clean = (code or "").strip()

    # Latest unconsumed code for this email + purpose
    record = (
        db.query(OTPCode)
        .filter(
            OTPCode.email == email_norm,
            OTPCode.purpose == purpose,
            OTPCode.consumed == False,  # noqa: E712
        )
        .order_by(OTPCode.created_at.desc())
        .first()
    )

    if not record:
        return False, "no_code", None

    if record.expires_at < datetime.utcnow():
        record.consumed = True
        db.commit()
        return False, "expired", None

    if record.attempts >= settings.OTP_MAX_ATTEMPTS:
        record.consumed = True
        db.commit()
        return False, "too_many_attempts", None

    if not _verify_code(code_clean, record.code_hash):
        record.attempts += 1
        db.commit()
        # If this was the last allowed attempt, invalidate
        if record.attempts >= settings.OTP_MAX_ATTEMPTS:
            record.consumed = True
            db.commit()
            return False, "too_many_attempts", None
        return False, "invalid", None

    # Success
    record.consumed = True
    db.commit()
    payload = None
    if record.pending_payload:
        try:
            payload = json.loads(record.pending_payload)
        except Exception:
            payload = None
    return True, "ok", payload
