"""Shared validation helpers — imported by multiple schema modules to avoid circular imports."""

import re


def validate_password_strength(v: str) -> str:
    """
    Enforce minimum password requirements.

    Rules: at least 8 characters, one uppercase letter, one lowercase letter, one digit.
    Raises ValueError with a specific message for each failing rule so the client
    can display targeted feedback.
    """
    if len(v) < 8:
        raise ValueError("Password must be at least 8 characters")
    if not re.search(r"[A-Z]", v):
        raise ValueError("Password must contain at least one uppercase letter")
    if not re.search(r"[a-z]", v):
        raise ValueError("Password must contain at least one lowercase letter")
    if not re.search(r"\d", v):
        raise ValueError("Password must contain at least one number")
    return v
