"""
WebSocket Events — Pydantic models for real-time messages.
"""

from typing import Any, Dict, Optional
from uuid import UUID
from pydantic import BaseModel, Field


class BaseWebsocketMessage(BaseModel):
    """Base structure for all messages sent over WebSocket."""
    event: str = Field(..., description="The type of event (e.g., 'notification', 'error')")
    data: Any = Field(..., description="The payload associated with the event")


class NotificationEvent(BaseModel):
    """Payload for real-time notifications."""
    id: UUID
    type: str
    title: str
    body: str
    isRead: bool = False
    createdAt: str  # Send as ISO string for frontend


class SystemEvent(BaseModel):
    """Payload for system-level messages (errors, success, etc)."""
    message: str
    status: str = "success"  # success, error, info
