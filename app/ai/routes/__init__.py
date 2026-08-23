# app/ai/routes/__init__.py
"""
AI Routes - API endpoints for AI features.
"""
from app.ai.routes.ai_routes import router as ai_router

__all__ = ["ai_router"]
