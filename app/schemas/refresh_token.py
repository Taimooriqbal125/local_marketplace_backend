"""Pydantic schemas for RefreshToken resource."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import Field

from .base import BaseSchema


class RefreshTokenBase(BaseSchema):
    """Shared refresh token fields."""

    user_id: UUID = Field(..., description="Owner of the token")
    token_hash: str = Field(..., min_length=1, max_length=255, description="Secure hash of the refresh token")
    expires_at: datetime = Field(..., description="Expiration timestamp")


class RefreshTokenCreate(RefreshTokenBase):
    """Payload to create/store a refresh token record."""

    revoked: bool = Field(default=False, description="Whether the token has been invalidated")
    revoked_at: Optional[datetime] = Field(default=None, description="When the token was revoked")


class RefreshTokenUpdate(BaseSchema):
    """Payload to update refresh token state (e.g., revoke)."""

    revoked: Optional[bool] = None
    revoked_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None


class RefreshTokenResponse(RefreshTokenBase):
    """Refresh token object returned by API/internal services."""

    id: UUID
    revoked: bool
    created_at: datetime
    revoked_at: Optional[datetime] = None
