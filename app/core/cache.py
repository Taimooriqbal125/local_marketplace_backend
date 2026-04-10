# app/core/cache.py

"""
Async caching module for the project using Redis.
This file provides utility functions to manage cache efficiently.

Key Features:
- Async Redis client (latest redis library)
- Cache get, set, delete operations
- TTL (Time To Live) support
- Manual invalidation
- Structured logging using structlog
- Fully commented for agent/teammate understanding
"""

import json
from app.core.logging import logger
from app.core.redis import get_redis

# ---------------------------------------------------------------------
# Step 1: Initialize Redis connection
# ---------------------------------------------------------------------
# Use the centralized Redis connection from app.core.redis.
redis = get_redis()

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
    # Convert value to JSON string for safe storage
    json_value = json.dumps(value)
    
    # Store in Redis with TTL
    await redis.set(key, json_value, ex=expire)
    
    # Log the cache set operation
    logger.info("Cache set", key=key, expire=expire)

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
    # Get JSON string from Redis
    cached_value = await redis.get(key)
    
    if cached_value:
        # Log cache hit
        logger.info("Cache hit", key=key)
        return json.loads(cached_value)  # Convert back to Python object
    
    # Log cache miss
    logger.info("Cache miss", key=key)
    return None

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
    deleted_count = await redis.delete(key)
    
    # Log the invalidation
    if deleted_count:
        logger.info("Cache invalidated", key=key)
    else:
        logger.info("Cache key not found for invalidation", key=key)

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
    keys = await redis.keys(pattern)
    if keys:
        await redis.delete(*keys)
        logger.info("Cache pattern invalidated", pattern=pattern, deleted=len(keys))
    else:
        logger.info("No cache keys matched pattern", pattern=pattern)