"""SlowAPI rate-limiter singleton — import this in main.py (setup) and api/ routes (decorators)."""

from slowapi import Limiter
from slowapi.util import get_remote_address

# Key function uses the client IP address.
# Behind a reverse proxy in production, configure TrustedHostMiddleware or
# use a custom key_func that reads X-Forwarded-For.
limiter = Limiter(key_func=get_remote_address)
