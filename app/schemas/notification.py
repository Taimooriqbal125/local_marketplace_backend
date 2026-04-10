"""Pydantic schemas for the Notification resource."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import Field

from .base import BaseSchema


# ---------------------------------------------------------------------------
# Base — shared fields for Create / Update / Response
# ---------------------------------------------------------------------------
class NotificationBase(BaseSchema):
    """Fields shared across all Notification schema variants."""

    type: str = Field(..., description="Type of notification (e.g., order_requested)")
    title: str = Field(..., description="Short summary of the notification")
    body: str = Field(..., description="Full content of the notification")


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------
class NotificationCreate(NotificationBase):
    """Payload for creating a new notification."""

    user_id: UUID = Field(..., description="The ID of the user receiving the notification")
    sender_id: Optional[UUID] = Field(default=None, description="The ID of the user who triggered the notification")
    order_id: Optional[UUID] = Field(default=None, description="The ID of the related order")
    listing_id: Optional[UUID] = Field(default=None, description="The ID of the related service listing")


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------
class NotificationUpdate(BaseSchema):
    """Payload for updating notification status (e.g., marking as read)."""

    is_read: bool = Field(default=True, description="Mark the notification as read or unread")


# ---------------------------------------------------------------------------
# Response
# ---------------------------------------------------------------------------
class NotificationResponse(NotificationBase):
    """Full notification object returned by the API."""

    id: UUID
    user_id: UUID
    sender_id: Optional[UUID] = None
    order_id: Optional[UUID] = None
    listing_id: Optional[UUID] = None
    is_read: bool
    read_at: Optional[datetime] = None
    created_at: datetime


class NotificationMarkReadResponse(BaseSchema):
    """Minimized response for marking a notification as read."""

    id: UUID
    is_read: bool
    read_at: Optional[datetime] = None


class NotificationListResponse(BaseSchema):
    """Minimized response for the notification list endpoint."""

    id: UUID
    type: str
    title: str
    body: str
    is_read: bool
    created_at: datetime
    order_id: Optional[UUID] = None
    listing_id: Optional[UUID] = None
