"""Pydantic schemas for OTPToken resource."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import EmailStr, Field

from .base import BaseSchema


class OTPPurpose(str, Enum):
    """Enumeration of valid OTP use cases."""
    SIGNUP_VERIFY = "signup_verify"
    RESET_PASSWORD = "reset_password"


class OTPTokenBase(BaseSchema):
    """Shared fields for OTP tokens."""
    email: EmailStr = Field(..., description="Target email for the OTP")
    purpose: OTPPurpose = Field(..., description="Intended use for this OTP code")


class OTPTokenCreate(OTPTokenBase):
    """Payload to create/store an OTP record."""
    user_id: Optional[UUID] = Field(default=None, description="Related user ID if exists")
    otp_hash: str = Field(..., description="Secure hash of the 6-digit code")
    expires_at: datetime = Field(..., description="Expiration timestamp")


class OTPVerify(BaseSchema):
    """Payload for submitting an OTP for verification."""
    email: EmailStr = Field(..., description="Email that received the code")
    otp: str = Field(..., min_length=6, max_length=6, description="6-digit OTP code")
    purpose: OTPPurpose = Field(..., description="The purpose for which the OTP was issued")


class OTPTokenResponse(OTPTokenBase):
    """OTP token object returned by internal services."""
    id: UUID
    user_id: Optional[UUID]
    expires_at: datetime
    used: bool
    attempts: int
    created_at: datetime
    used_at: Optional[datetime]
    last_sent_at: Optional[datetime]
    resend_count: int
