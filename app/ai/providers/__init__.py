# app/ai/providers/__init__.py
"""
AI Providers - Abstraction layer for AI services (Gemini, Groq, OpenAI, etc.)
"""
from app.ai.providers.gemini_provider import GeminiProvider

__all__ = ["GeminiProvider"]
