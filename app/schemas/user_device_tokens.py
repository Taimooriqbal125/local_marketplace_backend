"""Pydantic schemas for the UserDeviceToken resource."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import Field

from .base import BaseSchema


# ---------------------------------------------------------------------------
# Base — shared fields for Create / Update / Response
# ---------------------------------------------------------------------------
class UserDeviceTokenBase(BaseSchema):
    """Fields shared across all UserDeviceToken schema variants."""

    expo_push_token: str = Field(..., description="The unique Expo push notification token")
    device_type: str = Field(..., description="The platform type (e.g., android, ios)")
    device_name: Optional[str] = Field(None, description="Human-readable name of the device")


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------
class UserDeviceTokenCreate(UserDeviceTokenBase):
    """Payload for registering a new device token."""
    pass


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------
class UserDeviceTokenUpdate(BaseSchema):
    """Payload for updating an existing device token's status."""

    is_active: Optional[bool] = Field(None, description="Update the active status of the token")
    last_used_at: Optional[datetime] = Field(None, description="Update the last used timestamp")


# ---------------------------------------------------------------------------
# Response
# ---------------------------------------------------------------------------
class UserDeviceTokenResponse(UserDeviceTokenBase):
    """Full device token object returned by the API."""

    id: UUID
    user_id: UUID
    is_active: bool
    last_used_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
