"""OTP model — stores hashed one-time passwords for email verification."""
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Index
from datetime import datetime
from app.db.database import Base


class OTPCode(Base):
    """One-time password for email verification.

    Code itself is stored as a bcrypt hash (never plaintext).
    Purpose distinguishes signup vs login flows so codes can't be cross-used.
    """
    __tablename__ = "otp_codes"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, index=True, nullable=False)
    code_hash = Column(String, nullable=False)           # bcrypt hash of the OTP
    purpose = Column(String, nullable=False)             # "signup" | "login" | "reset"
    expires_at = Column(DateTime, nullable=False)
    attempts = Column(Integer, default=0)                # increment on each verify try
    consumed = Column(Boolean, default=False)            # set True once verified
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # For signup, we stash the would-be user data here (JSON-serialized)
    # so the verify step can finalize account creation atomically.
    pending_payload = Column(String, nullable=True)


# Index for the rate-limit query (email + created_at)
Index("ix_otp_email_created", OTPCode.email, OTPCode.created_at)
