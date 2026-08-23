# app/core/cache.py

"""
Caching module for the project using Redis.
This file provides sync helpers for service-layer use and async wrappers for
decorator use.

Key Features:
- Sync Redis client for loop-safe cache access from sync services
- Async wrappers for async decorator use
- Cache get, set, delete operations
- TTL (Time To Live) support
- Manual invalidation
- Structured logging using structlog
- Fully commented for agent/teammate understanding
"""

import asyncio
import json
import anyio
from redis import Redis as SyncRedis

from app.core.logging import logger
from app.core.config import settings

# ---------------------------------------------------------------------
# Step 1: Initialize Redis connection
# ---------------------------------------------------------------------
# Use a dedicated sync Redis client here so sync service code never crosses
# async event-loop boundaries.
redis = SyncRedis.from_url(
    settings.REDIS_URL,
    encoding="utf-8",
    decode_responses=True,
    health_check_interval=30,
    socket_connect_timeout=5,
    socket_timeout=5,
    retry_on_timeout=True,
)


def _serialize_value(value):
    return json.dumps(value)


def _deserialize_value(value):
    return json.loads(value)


def _get_cache_sync(key: str):
    cached_value = redis.get(key)
    if cached_value:
        logger.info("Cache hit", key=key)
        return _deserialize_value(cached_value)

    logger.info("Cache miss", key=key)
    return None


def _set_cache_sync(key: str, value, expire: int = 60):
    json_value = _serialize_value(value)
    redis.set(key, json_value, ex=expire)
    logger.info("Cache set", key=key, expire=expire)


def _delete_cache_sync(key: str):
    deleted_count = redis.delete(key)
    if deleted_count:
        logger.info("Cache invalidated", key=key)
    else:
        logger.info("Cache key not found for invalidation", key=key)


def _delete_cache_pattern_sync(pattern: str):
    # SCAN instead of KEYS: KEYS blocks Redis while scanning the whole
    # keyspace; scan_iter pages through with a cursor and never blocks.
    deleted_count = 0
    for key in redis.scan_iter(match=pattern, count=200):
        redis.delete(key)
        deleted_count += 1

    if deleted_count:
        logger.info("Cache pattern invalidated", pattern=pattern, deleted=deleted_count)
    else:
        logger.info("No cache keys matched pattern", pattern=pattern)

# ---------------------------------------------------------------------
# Step 2: Helper function to set cache
# ---------------------------------------------------------------------
async def set_cache(key: str, value, expire: int = 60):
    """
    Stores a value in Redis cache with optional TTL.
    
    Args:
        key (str): The cache key (prefer namespaced keys, e.g., "products:list")
        value (Any): The value to cache (Python object, dict, list, etc.)
        expire (int): TTL in seconds (default: 60s)
    
    Usage:
        await set_cache("products:list", data, expire=120)
    """
    await anyio.to_thread.run_sync(_set_cache_sync, key, value, expire)

# ---------------------------------------------------------------------
# Step 3: Helper function to get cache
# ---------------------------------------------------------------------
async def get_cache(key: str):
    """
    Retrieves a cached value from Redis.
    
    Args:
        key (str): The cache key
    
    Returns:
        Python object (dict, list, etc.) if found, else None
    
    Usage:
        data = await get_cache("products:list")
    """
    return await anyio.to_thread.run_sync(_get_cache_sync, key)

# ---------------------------------------------------------------------
# Step 4: Helper function to delete cache (manual invalidation)
# ---------------------------------------------------------------------
async def delete_cache(key: str):
    """
    Deletes a cached value from Redis.
    
    Args:
        key (str): The cache key to delete
    
    Usage:
        await delete_cache("products:list")
    """
    await anyio.to_thread.run_sync(_delete_cache_sync, key)

# ---------------------------------------------------------------------
# Step 5: Optional: Pattern-based invalidation
# ---------------------------------------------------------------------
async def delete_cache_pattern(pattern: str):
    """
    Deletes multiple cache keys matching a pattern.
    Useful for bulk invalidation when multiple keys need clearing.
    
    Args:
        pattern (str): Redis pattern (e.g., "products:*")
    
    Usage:
        await delete_cache_pattern("products:*")
    """
    await anyio.to_thread.run_sync(_delete_cache_pattern_sync, pattern)


def _run_sync_cache_task(coro):
    """Run an async cache helper from synchronous code."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    raise RuntimeError("Synchronous cache helpers cannot be used from an async context.")


def get_cache_sync(key: str):
    """Synchronous wrapper for get_cache()."""
    return _get_cache_sync(key)


def set_cache_sync(key: str, value, expire: int = 60):
    """Synchronous wrapper for set_cache()."""
    return _set_cache_sync(key, value, expire=expire)


def delete_cache_sync(key: str):
    """Synchronous wrapper for delete_cache()."""
    return _delete_cache_sync(key)


def delete_cache_pattern_sync(pattern: str):
    """Synchronous wrapper for delete_cache_pattern()."""
    return _delete_cache_pattern_sync(pattern)