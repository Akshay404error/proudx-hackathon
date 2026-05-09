"""Email service — Gmail SMTP or console (dev) mode.

Switchable via EMAIL_MODE in .env:
  - console : prints OTP to terminal (great for hackathon demos)
  - gmail   : sends real emails via Gmail SMTP (needs app password)
"""
from __future__ import annotations
import logging
from email.message import EmailMessage
import aiosmtplib
from app.core.config import settings

logger = logging.getLogger(__name__)


HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#0a0a0f;font-family:-apple-system,Segoe UI,Roboto,sans-serif;">
  <div style="max-width:520px;margin:40px auto;background:#12121a;border:1px solid #24243a;border-radius:16px;overflow:hidden;">

    <!-- header -->
    <div style="background:linear-gradient(135deg,#6366f1,#8b5cf6,#f59e0b);padding:32px 32px 28px;text-align:center;">
      <div style="color:#fff;font-size:28px;font-weight:800;letter-spacing:-0.02em;">PathForge</div>
      <div style="color:rgba(255,255,255,0.85);font-size:13px;margin-top:4px;">AI Learning Roadmap Platform</div>
    </div>

    <!-- body -->
    <div style="padding:36px 32px;color:#f5f5fa;">
      <h2 style="margin:0 0 12px;font-size:22px;font-weight:700;">{heading}</h2>
      <p style="color:#8b8ba8;line-height:1.6;font-size:14px;margin:0 0 28px;">{intro}</p>

      <!-- OTP box -->
      <div style="background:#1a1a25;border:1px solid #33334d;border-radius:12px;padding:24px;text-align:center;margin:0 0 28px;">
        <div style="color:#8b8ba8;font-size:11px;font-weight:700;letter-spacing:0.15em;margin-bottom:10px;">YOUR VERIFICATION CODE</div>
        <div style="font-size:42px;font-weight:800;color:#f59e0b;letter-spacing:0.25em;font-family:'Courier New',monospace;">{code}</div>
        <div style="color:#5a5a78;font-size:12px;margin-top:10px;">Expires in {expiry_min} minutes</div>
      </div>

      <p style="color:#8b8ba8;line-height:1.6;font-size:13px;margin:0 0 8px;">
        If you didn't request this code, you can safely ignore this email.
        Someone may have entered your email address by mistake.
      </p>
    </div>

    <!-- footer -->
    <div style="background:#0a0a0f;padding:18px 32px;text-align:center;border-top:1px solid #24243a;">
      <div style="color:#5a5a78;font-size:11px;">
        © 2026 PathForge · Built with ❤️ in Bengaluru
      </div>
    </div>
  </div>
</body>
</html>
"""

PURPOSE_COPY = {
    "signup": {
        "subject": "Verify your PathForge account",
        "heading": "Welcome to PathForge!",
        "intro": "You're almost in. Enter this code on the signup page to verify your email and finish creating your account.",
    },
    "login": {
        "subject": "Your PathForge login code",
        "heading": "Sign in to PathForge",
        "intro": "Enter this code on the login page to sign in to your account.",
    },
    "reset": {
        "subject": "Reset your PathForge password",
        "heading": "Reset your password",
        "intro": "Enter this code on the reset page to set a new password.",
    },
}


async def send_otp_email(to_email: str, code: str, purpose: str = "signup") -> None:
    """Send an OTP email via the configured provider."""
    copy = PURPOSE_COPY.get(purpose, PURPOSE_COPY["signup"])
    mode = (settings.EMAIL_MODE or "console").lower().strip()

    # Console mode: print to terminal — simplest for demos
    if mode == "console":
        _print_console(to_email, code, copy)
        return

    if mode == "gmail":
        await _send_gmail(to_email, code, copy)
        return

    # Unknown mode → fall back to console with a warning
    logger.warning(f"Unknown EMAIL_MODE='{mode}'. Falling back to console.")
    _print_console(to_email, code, copy)


def _print_console(to_email: str, code: str, copy: dict) -> None:
    """Pretty print to terminal — works great for live demos."""
    bar = "═" * 56
    block = (
        f"\n╔{bar}╗\n"
        f"║  📧  EMAIL OTP (console mode — no email sent)         ║\n"
        f"╠{bar}╣\n"
        f"║  To:      {to_email:<44} ║\n"
        f"║  Subject: {copy['subject']:<44} ║\n"
        f"║  Code:    {code:<44} ║\n"
        f"║  Expires: {settings.OTP_EXPIRY_MINUTES} minutes{' ':<35} ║\n"
        f"╚{bar}╝\n"
    )
    print(block, flush=True)


async def _send_gmail(to_email: str, code: str, copy: dict) -> None:
    """Send via Gmail SMTP using an app password."""
    if not settings.GMAIL_USER or not settings.GMAIL_APP_PASSWORD:
        logger.error(
            "EMAIL_MODE=gmail but GMAIL_USER or GMAIL_APP_PASSWORD is missing in .env. "
            "Falling back to console output."
        )
        _print_console(to_email, code, copy)
        return

    html = HTML_TEMPLATE.format(
        heading=copy["heading"],
        intro=copy["intro"],
        code=code,
        expiry_min=settings.OTP_EXPIRY_MINUTES,
    )
    plain = (
        f"{copy['heading']}\n\n"
        f"{copy['intro']}\n\n"
        f"YOUR CODE: {code}\n"
        f"Expires in {settings.OTP_EXPIRY_MINUTES} minutes.\n\n"
        f"If you didn't request this, ignore this email.\n\n"
        f"— PathForge"
    )

    msg = EmailMessage()
    msg["From"] = f"{settings.EMAIL_FROM_NAME} <{settings.GMAIL_USER}>"
    msg["To"] = to_email
    msg["Subject"] = copy["subject"]
    msg.set_content(plain)
    msg.add_alternative(html, subtype="html")

    try:
        await aiosmtplib.send(
            msg,
            hostname="smtp.gmail.com",
            port=587,
            start_tls=True,
            username=settings.GMAIL_USER,
            password=settings.GMAIL_APP_PASSWORD,
            timeout=20,
        )
        logger.info(f"OTP email sent to {to_email} (purpose: {copy['subject']})")
    except Exception as e:
        logger.error(f"Gmail SMTP failed for {to_email}: {e}. Falling back to console.")
        _print_console(to_email, code, copy)

# ---------- Email with PDF attachment (for reports) ----------
async def send_report_email(
    to_email: str, subject: str, filename: str, pdf_bytes: bytes,
    recipient_name: str = "there",
) -> None:
    """Send a PDF report as an email attachment."""
    mode = (settings.EMAIL_MODE or "console").lower().strip()

    if mode == "console":
        size_kb = len(pdf_bytes) / 1024
        bar = "═" * 56
        print(
            f"\n╔{bar}╗\n"
            f"║  📎  REPORT EMAIL (console mode — no email sent)      ║\n"
            f"╠{bar}╣\n"
            f"║  To:       {to_email:<43} ║\n"
            f"║  Subject:  {subject[:43]:<43} ║\n"
            f"║  Filename: {filename:<43} ║\n"
            f"║  Size:     {f'{size_kb:.1f} KB':<43} ║\n"
            f"╚{bar}╝\n",
            flush=True,
        )
        return

    if mode != "gmail":
        logger.warning(f"Unknown EMAIL_MODE='{mode}'. Falling back to console for report.")
        return

    if not settings.GMAIL_USER or not settings.GMAIL_APP_PASSWORD:
        logger.error("EMAIL_MODE=gmail but GMAIL_USER/GMAIL_APP_PASSWORD missing. Skipping report email.")
        return

    html = f"""<!DOCTYPE html>
<html><body style="margin:0;padding:0;background:#0a0a0f;font-family:-apple-system,Segoe UI,Roboto,sans-serif;">
<div style="max-width:520px;margin:40px auto;background:#12121a;border:1px solid #24243a;border-radius:16px;overflow:hidden;">
  <div style="background:linear-gradient(135deg,#6366f1,#8b5cf6,#f59e0b);padding:28px 32px;text-align:center;">
    <div style="color:#fff;font-size:24px;font-weight:800;">PathForge</div>
  </div>
  <div style="padding:32px;color:#f5f5fa;">
    <h2 style="margin:0 0 12px;font-size:20px;">Hi {recipient_name},</h2>
    <p style="color:#8b8ba8;line-height:1.6;font-size:14px;">
      Your PathForge report is attached as <b style="color:#fff;">{filename}</b>.
    </p>
    <p style="color:#8b8ba8;line-height:1.6;font-size:14px;">
      Keep up the great work on your learning journey!
    </p>
  </div>
  <div style="background:#0a0a0f;padding:16px;text-align:center;border-top:1px solid #24243a;">
    <div style="color:#5a5a78;font-size:11px;">© 2026 PathForge</div>
  </div>
</div></body></html>"""

    msg = EmailMessage()
    msg["From"] = f"{settings.EMAIL_FROM_NAME} <{settings.GMAIL_USER}>"
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(f"Hi {recipient_name}, your PathForge report is attached as {filename}.")
    msg.add_alternative(html, subtype="html")
    msg.add_attachment(pdf_bytes, maintype="application", subtype="pdf", filename=filename)

    try:
        await aiosmtplib.send(
            msg, hostname="smtp.gmail.com", port=587, start_tls=True,
            username=settings.GMAIL_USER, password=settings.GMAIL_APP_PASSWORD, timeout=30,
        )
        logger.info(f"Report '{filename}' emailed to {to_email}")
    except Exception as e:
        logger.error(f"Gmail SMTP failed for report to {to_email}: {e}")