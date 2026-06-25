"""SlowAPI rate-limiter singleton — import this in main.py (setup) and api/ routes (decorators)."""

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

# IP-based limiter — used for unauthenticated endpoints (auth routes).
limiter = Limiter(key_func=get_remote_address)


def get_user_id_key(request: Request) -> str:
    """Rate-limit key using user_id from JWT cookie; falls back to IP if no valid token.

    Use this key_func for authenticated endpoints so each user has their own
    rate limit bucket independent of shared IPs (NAT, proxies, etc.).
    """
    try:
        from app.services.auth_service import decode_token  # lazy import avoids circular dep

        token = request.cookies.get("access_token")
        if token:
            user_id = decode_token(token, expected_type="access")
            return f"user:{user_id}"
    except Exception:
        pass
    return get_remote_address(request)
