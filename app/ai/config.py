# app/ai/config.py
"""
AI-specific configuration.
Reads from core settings and provides AI-focused access.
"""
from functools import lru_cache
from app.core.config import settings


class AISettings:
    """AI-specific settings wrapper for easy access."""

    @property
    def gemini_api_key(self) -> str:
        return settings.GEMINI_API_KEY

    @property
    def embedding_model(self) -> str:
        return settings.GEMINI_EMBEDDING_MODEL

    @property
    def embedding_dimensions(self) -> int:
        return settings.EMBEDDING_DIMENSIONS


@lru_cache()
def get_ai_settings() -> AISettings:
    """Cached singleton for AI settings."""
    return AISettings()


ai_settings = get_ai_settings()
