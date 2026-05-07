# app/core/rate_limiter.py

"""
Rate limiting module for FastAPI using fastapi-limiter (supports both 0.1.x and 0.2.x).
This module provides setup and integration functions to apply
rate limits on API endpoints efficiently, automatically detecting
the active virtual environment syntax.
"""

import math
import inspect
from typing import Callable

from fastapi import HTTPException, Request, Response, status
from fastapi_limiter.depends import RateLimiter
from app.core.logging import logger
from app.core.redis import get_redis

# ---------------------------------------------------------------------
# Step 1: Initialize Redis connection
# ---------------------------------------------------------------------
redis = get_redis()

async def _http_rate_limit_callback(request: Request, response: Response, pexpire: int):
    """Custom callback that logs blocked requests and raises 429."""
    retry_after_seconds = max(1, math.ceil(pexpire / 1000))
    client_host = request.client.host if request.client else "unknown"

    logger.warning(
        "Rate limit exceeded",
        path=request.url.path,
        method=request.method,
        client=client_host,
        retry_after_seconds=retry_after_seconds,
    )

    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Rate limit exceeded. Please try again later.",
        headers={"Retry-After": str(retry_after_seconds)},
    )

# ---------------------------------------------------------------------
# Adaptive Syntax Detector (Supports 0.1.x AND 0.2.x simultaneously)
# ---------------------------------------------------------------------
_IS_V2 = "limiter" in inspect.signature(RateLimiter.__init__).parameters
_RATE_LIMITING_ENABLED = _IS_V2

# ---------------------------------------------------------------------
# Step 2: Initialize rate limiter
# ---------------------------------------------------------------------
async def init_rate_limiter():
    global _RATE_LIMITING_ENABLED

    if _IS_V2:
        _RATE_LIMITING_ENABLED = True
        logger.info("Rate limiter running in v0.2.0 (pyrate-limiter) syntax mode.")
    else:
        from fastapi_limiter import FastAPILimiter
        try:
            await FastAPILimiter.init(
                redis,
                prefix="local-marketplace",
                http_callback=_http_rate_limit_callback,
            )
            _RATE_LIMITING_ENABLED = True
            logger.info("Rate limiter initialized in v0.1.x (Redis) syntax mode.")
        except Exception as exc:
            _RATE_LIMITING_ENABLED = False
            logger.error(
                "Rate limiter disabled because Redis initialization failed",
                error=str(exc),
            )

# ---------------------------------------------------------------------
# Step 3: RateLimiter dependencies
# ---------------------------------------------------------------------
def create_limiter(times: int, seconds: int):
    """Create a dependency that no-ops when limiter backend is unavailable."""
    if _IS_V2:
        from pyrate_limiter import Duration, Limiter, Rate
        limiter = RateLimiter(limiter=Limiter(Rate(times, Duration.SECOND * seconds)))
    else:
        limiter = RateLimiter(times=times, seconds=seconds)

    async def dependency(request: Request, response: Response):
        if not _RATE_LIMITING_ENABLED:
            return None

        result = limiter(request=request, response=response)
        if inspect.isawaitable(result):
            await result
        return None

    return dependency

example_rate_limit = create_limiter(10, 60)
services_list_rate_limit = create_limiter(60, 60)
login_rate_limit = create_limiter(5, 60)
signup_rate_limit = create_limiter(4, 60)
refresh_issue_rate_limit = create_limiter(30, 60)
services_create_rate_limit = create_limiter(10, 60)
services_nearby_me_rate_limit = create_limiter(30, 60)
forgot_password_rate_limit = create_limiter(5, 60)

# ---------------------------------------------------------------------
# Step 4: Usage in FastAPI routes
# ---------------------------------------------------------------------
# Example route usage:
# @router.get("/products", dependencies=[Depends(example_rate_limit)])
# async def get_products(): ...