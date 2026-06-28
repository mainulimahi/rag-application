"""Redis cache service — async get/set/delete with graceful fallback on connection failure.

Never raises: all public functions swallow exceptions and log a WARNING so Redis
unavailability never crashes the app.
"""

from __future__ import annotations

import hashlib
import json
import logging

logger = logging.getLogger(__name__)

_redis_client = None


async def _get_client():
    """Lazy-initialize the Redis client. Returns None if Redis is unavailable."""
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    try:
        import redis.asyncio as aioredis

        from app.core.config import settings

        client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        await client.ping()
        _redis_client = client
        logger.info("Redis connection established: %s", settings.REDIS_URL)
        return _redis_client
    except Exception as exc:
        logger.warning("Redis unavailable, caching disabled: %s", exc)
        return None


async def get_cached(key: str) -> dict | None:
    """Return the cached dict for key, or None on miss or error."""
    try:
        client = await _get_client()
        if client is None:
            return None
        raw = await client.get(key)
        if raw is None:
            return None
        return json.loads(raw)
    except Exception as exc:
        logger.warning("Cache get failed for key=%r: %s", key, exc)
        return None


async def set_cached(key: str, val: dict, ttl: int = 300) -> None:
    """Store val as JSON under key with ttl seconds expiry. Silently ignores errors."""
    try:
        client = await _get_client()
        if client is None:
            return
        await client.setex(key, ttl, json.dumps(val))
    except Exception as exc:
        logger.warning("Cache set failed for key=%r: %s", key, exc)


async def delete_cached(key: str) -> None:
    """Delete a single cache key. Silently ignores errors."""
    try:
        client = await _get_client()
        if client is None:
            return
        await client.delete(key)
    except Exception as exc:
        logger.warning("Cache delete failed for key=%r: %s", key, exc)


async def delete_pattern(pattern: str) -> None:
    """Delete all keys matching pattern via SCAN+DEL. Silently ignores errors."""
    try:
        client = await _get_client()
        if client is None:
            return
        cursor = 0
        deleted = 0
        while True:
            cursor, keys = await client.scan(cursor=cursor, match=pattern, count=100)
            if keys:
                await client.delete(*keys)
                deleted += len(keys)
            if cursor == 0:
                break
        if deleted:
            logger.debug("Deleted %d key(s) matching pattern=%r", deleted, pattern)
    except Exception as exc:
        logger.warning("Cache delete_pattern failed for pattern=%r: %s", pattern, exc)


def cache_key(prefix: str, *parts: object) -> str:
    """Build a cache key as prefix:first_part:MD5(remaining_parts).

    Keeping first_part (e.g. file_id) literal in the key enables
    delete_pattern(f"{prefix}:{first_part}:*") for targeted invalidation.
    """
    if not parts:
        return prefix
    first = str(parts[0])
    rest = ":".join(str(p) for p in parts[1:])
    digest = hashlib.md5(rest.encode("utf-8")).hexdigest()
    return f"{prefix}:{first}:{digest}"
