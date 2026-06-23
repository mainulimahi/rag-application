"""Email service — sends transactional emails via the Resend API.

All send functions are async (they run the synchronous Resend SDK in a thread pool
so they don't block the event loop). Failures are logged and re-raised so callers
can decide whether to surface them to the user.
"""

import asyncio
import logging

import resend

from app.core.config import settings

logger = logging.getLogger(__name__)

resend.api_key = settings.RESEND_API_KEY

_APP_NAME = "RAG Application"
_BASE_URL = "http://localhost:3000"

_BUTTON_STYLE = (
    "display:inline-block;padding:12px 24px;background:#2563eb;color:#ffffff;"
    "border-radius:6px;text-decoration:none;font-weight:600;font-size:15px"
)


def _html(title: str, body_html: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>{title}</title>
</head>
<body style="margin:0;padding:0;background:#f3f4f6;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif">
  <table width="100%" cellpadding="0" cellspacing="0">
    <tr><td align="center" style="padding:40px 16px">
      <table width="580" cellpadding="0" cellspacing="0"
             style="background:#fff;border-radius:10px;box-shadow:0 1px 3px rgba(0,0,0,.08)">
        <tr>
          <td style="padding:32px 40px 0">
            <p style="margin:0;font-size:22px;font-weight:700;color:#111827">{_APP_NAME}</p>
          </td>
        </tr>
        <tr>
          <td style="padding:24px 40px 40px">
            {body_html}
            <hr style="margin:32px 0;border:none;border-top:1px solid #e5e7eb"/>
            <p style="margin:0;font-size:13px;color:#9ca3af">
              You're receiving this because an account was created or a request was made
              for this email address on {_APP_NAME}. If you didn't request this, ignore it.
            </p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


async def send_verification_email(to_email: str, name: str, token: str) -> None:
    """Send an email verification link to a newly registered user."""
    verify_url = f"{_BASE_URL}/verify-email?token={token}"
    body = f"""
<h2 style="margin:0 0 8px;font-size:20px;color:#111827">Verify your email address</h2>
<p style="margin:0 0 24px;font-size:15px;color:#4b5563">
  Hi {name}, welcome to {_APP_NAME}! Click the button below to verify your email address
  and activate your account.
</p>
<p style="margin:0 0 24px">
  <a href="{verify_url}" style="{_BUTTON_STYLE}">Verify email address</a>
</p>
<p style="margin:0;font-size:13px;color:#6b7280">
  This link expires in 24 hours. If the button doesn't work, copy this URL:<br/>
  <a href="{verify_url}" style="color:#2563eb;word-break:break-all">{verify_url}</a>
</p>"""

    params = {
        "from": settings.EMAIL_FROM,
        "to": [to_email],
        "subject": f"Verify your {_APP_NAME} account",
        "html": _html(f"Verify your {_APP_NAME} account", body),
    }
    try:
        await asyncio.to_thread(resend.Emails.send, params)
        logger.info("Verification email sent to %s", to_email)
    except Exception as exc:
        logger.error("Failed to send verification email to %s: %s", to_email, exc)
        raise


async def send_password_reset_email(to_email: str, name: str, token: str) -> None:
    """Send a password reset link to a user who requested it."""
    reset_url = f"{_BASE_URL}/reset-password?token={token}"
    body = f"""
<h2 style="margin:0 0 8px;font-size:20px;color:#111827">Reset your password</h2>
<p style="margin:0 0 24px;font-size:15px;color:#4b5563">
  Hi {name}, we received a request to reset the password for your {_APP_NAME} account.
  Click the button below to choose a new password.
</p>
<p style="margin:0 0 24px">
  <a href="{reset_url}" style="{_BUTTON_STYLE}">Reset password</a>
</p>
<p style="margin:0;font-size:13px;color:#6b7280">
  This link expires in 1 hour. If you didn't request a password reset, you can safely
  ignore this email — your password won't change.<br/><br/>
  If the button doesn't work, copy this URL:<br/>
  <a href="{reset_url}" style="color:#2563eb;word-break:break-all">{reset_url}</a>
</p>"""

    params = {
        "from": settings.EMAIL_FROM,
        "to": [to_email],
        "subject": f"Reset your {_APP_NAME} password",
        "html": _html(f"Reset your {_APP_NAME} password", body),
    }
    try:
        await asyncio.to_thread(resend.Emails.send, params)
        logger.info("Password reset email sent to %s", to_email)
    except Exception as exc:
        logger.error("Failed to send password reset email to %s: %s", to_email, exc)
        raise
