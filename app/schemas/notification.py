"""Pydantic schemas for the Notification resource."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Base — shared fields for Create / Update / Response
# ---------------------------------------------------------------------------
class NotificationBase(BaseModel):
    """Fields shared across all Notification schema variants."""

    type: str = Field(..., description="Type of notification (e.g., order_requested)")
    title: str = Field(..., description="Short summary of the notification")
    body: str = Field(..., description="Full content of the notification")


# ---------------------------------------------------------------------------
# Create — what a client (or service) POSTs to create a new notification
# ---------------------------------------------------------------------------
class NotificationCreate(NotificationBase):
    """Payload for creating a new notification."""

    userId: UUID = Field(..., description="The ID of the user receiving the notification")
    senderId: Optional[UUID] = Field(default=None, description="The ID of the user who triggered the notification")
    orderId: Optional[UUID] = Field(default=None, description="The ID of the related order")
    listingId: Optional[UUID] = Field(default=None, description="The ID of the related service listing")


# ---------------------------------------------------------------------------
# Update — payload for updating notification status (e.g., marking as read)
# ---------------------------------------------------------------------------
class NotificationUpdate(BaseModel):
    """Payload for PATCH /notifications/{id}."""

    isRead: bool = Field(default=True, description="Mark the notification as read or unread")


# ---------------------------------------------------------------------------
# Response — what the API returns
# ---------------------------------------------------------------------------
class NotificationResponse(NotificationBase):
    """Full notification object returned by the API."""

    id: UUID
    userId: UUID
    senderId: Optional[UUID] = None
    orderId: Optional[UUID] = None
    listingId: Optional[UUID] = None
    isRead: bool
    readAt: Optional[datetime] = None
    createdAt: datetime

    model_config = dict(from_attributes=True)


class NotificationMarkReadResponse(BaseModel):
    """Minimized response for marking a notification as read."""

    id: UUID
    isRead: bool
    readAt: Optional[datetime] = None

    model_config = dict(from_attributes=True)


class NotificationListResponse(BaseModel):
    """Minimized response for the notification list endpoint."""

    id: UUID
    type: str
    title: str
    body: str
    isRead: bool
    createdAt: datetime
    orderId: Optional[UUID] = None
    listingId: Optional[UUID] = None

    model_config = dict(from_attributes=True)
