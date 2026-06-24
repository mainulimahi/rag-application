"""Fernet symmetric encryption helpers for sensitive config values stored in the DB.

Uses FERNET_SECRET_KEY from settings. Call encrypt() before writing connection_config
to data_sources; call decrypt() after reading it back.
"""

from cryptography.fernet import Fernet

from app.core.config import settings


def _fernet() -> Fernet:
    return Fernet(settings.FERNET_SECRET_KEY.encode())


def encrypt(plaintext: str) -> str:
    """Encrypt a plaintext string; returns a URL-safe base64 token."""
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    """Decrypt a Fernet token back to the original plaintext string."""
    return _fernet().decrypt(ciphertext.encode()).decode()
