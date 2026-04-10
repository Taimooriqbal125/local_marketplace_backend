# app/core/decorator.py

"""
Reusable decorators for FastAPI project.

Key Features:
- Async-friendly decorators
- Cache decorator using Redis
- Logging decorator using structlog
- Easy to extend for rate-limiting or other enhancements
- Fully commented for agent/teammate understanding
"""

import functools
import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any, Callable

from app.core.cache import get_cache, set_cache
from app.core.logging import logger


def _to_jsonable(value: Any) -> Any:
    """Normalize values so cache key generation stays stable and serializable."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value

    if isinstance(value, Mapping):
        return {str(k): _to_jsonable(v) for k, v in sorted(value.items(), key=lambda item: str(item[0]))}

    if isinstance(value, set):
        return sorted(_to_jsonable(v) for v in value)

    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_to_jsonable(v) for v in value]

    # Fallback avoids unstable reprs like memory addresses in cache keys.
    return value.__class__.__name__


def _build_cache_key(func: Callable, args: tuple[Any, ...], kwargs: dict[str, Any], key_prefix: str) -> str:
    payload = {
        "args": _to_jsonable(args),
        "kwargs": _to_jsonable(kwargs),
    }
    canonical_payload = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()[:24]
    prefix = key_prefix.strip(":") or "cache"
    return f"{prefix}:{func.__module__}.{func.__qualname__}:{digest}"

# ---------------------------------------------------------------------
# Step 1: Cache decorator
# ---------------------------------------------------------------------
def cache(ttl: int = 60, key_prefix: str = ""):
    """
    Cache decorator for async functions (e.g., route handlers or services).
    
    Args:
        ttl (int): Time to live for cache (seconds)
        key_prefix (str): Prefix to namespace the cache key

    Usage:
        @cache(ttl=120, key_prefix="products")
        async def get_products():
            ...
    """
    if ttl <= 0:
        raise ValueError("ttl must be greater than 0")

    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            cache_key = _build_cache_key(func, args, kwargs, key_prefix)
            
            # Try fetching from cache
            try:
                cached_result = await get_cache(cache_key)
                if cached_result is not None:
                    logger.info("Decorator cache hit", cache_key=cache_key, func=func.__qualname__)
                    return cached_result
            except Exception as exc:
                logger.warning(
                    "Decorator cache read failed",
                    cache_key=cache_key,
                    func=func.__qualname__,
                    error=str(exc),
                )
            
            # Call the original function
            result = await func(*args, **kwargs)
            
            # Store result in cache
            try:
                await set_cache(cache_key, result, expire=ttl)
            except Exception as exc:
                logger.warning(
                    "Decorator cache write failed",
                    cache_key=cache_key,
                    func=func.__qualname__,
                    error=str(exc),
                )
            
            return result
        return wrapper
    return decorator

# ---------------------------------------------------------------------
# Step 2: Logging decorator
# ---------------------------------------------------------------------
def log_execution(func: Callable):
    """
    Decorator to log function execution with structlog.
    Useful for monitoring and debugging.
    
    Usage:
        @log_execution
        async def get_products():
            ...
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs) -> Any:
        logger.info("Function called", func=func.__qualname__)
        try:
            result = await func(*args, **kwargs)
            logger.info("Function completed", func=func.__qualname__)
            return result
        except Exception as e:
            logger.exception("Function failed", func=func.__qualname__, error=str(e))
            raise
    return wrapper

# ---------------------------------------------------------------------
# Step 3: Senior/Agent Notes
# ---------------------------------------------------------------------
# 1. Cache decorator:
#    - TTL controls freshness
#    - Key prefix helps avoid collisions
#    - Can be enhanced to include per-user keys or request IDs
#
# 2. Logging decorator:
#    - Logs function start, end, and errors
#    - Can bind context like user_id or request_id if needed
#
# 3. Combining decorators:
#    - @log_execution can wrap @cache or vice versa
#    - Order matters if you want to log cache hits separately
#
# 4. Production considerations:
#    - Avoid very large arguments in cache key (consider hashing)
#    - Monitor Redis memory usage for heavy caching
#    - Can extend with rate-limiting decorator if needed