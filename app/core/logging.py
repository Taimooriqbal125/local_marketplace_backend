# app/core/logging.py

"""
Logging configuration for the project using structlog.
This module provides a single logger instance to be used across the project.

Key Features:
- Uses structlog for structured logging
- JSON logs for production-friendly monitoring
- Async-friendly (works well with FastAPI)
- Easy to extend for additional processors or bindings
"""

import logging
import sys

import structlog

from app.core.config import settings

# ---------------------------------------------------------------------
# Step 1: Configure standard Python logging
# ---------------------------------------------------------------------
LOG_LEVEL_NAME = settings.LOG_LEVEL.upper()
LOG_LEVEL = getattr(logging, LOG_LEVEL_NAME, logging.INFO)

logging.basicConfig(
    format="%(message)s",  # structlog handles final rendering
    level=LOG_LEVEL,
    stream=sys.stdout,
    force=True,
)

# ---------------------------------------------------------------------
# Step 2: Configure structlog
# ---------------------------------------------------------------------
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

# ---------------------------------------------------------------------
# Step 3: Create global logger instance
# ---------------------------------------------------------------------
# Usage across the project:
# from app.core.logging import logger
# logger.info("Your message", key=value)
logger = structlog.get_logger()

# ---------------------------------------------------------------------
# Example Usage for Agent/Teammate Reference:
# ---------------------------------------------------------------------
# Basic log:
# logger.info("Cache hit", key="products:list")
#
# Log with contextual info:
# logger.bind(user_id=123, request_id="xyz").info("Request processed")
#
# Error log:
# logger.error("Failed to fetch products", error="Timeout")
#
# Metrics log (optional):
# metrics_logger = structlog.get_logger("metrics")
# metrics_logger.info("Cache stats", hits=50, misses=10)