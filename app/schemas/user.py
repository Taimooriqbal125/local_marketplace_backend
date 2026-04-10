"""
Pydantic schemas for the User resource.

Schemas define what the API *accepts* (request bodies) and what it *returns* (responses).
They also handle automatic validation — if a field is wrong, FastAPI returns a 422 error.
"""

import re
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import EmailStr, Field, field_validator

from .base import BaseSchema


# Basic phone regex (international format or domestic 10-digit)
PHONE_REGEX = re.compile(r"^\+?1?\d{9,15}$")


# ---------- Request Schemas (what the client sends) ----------

class UserCreate(BaseSchema):
    """
    Fields required to create a new user.
    """
    email: EmailStr = Field(..., description="Unique email address for the user")
    password: str = Field(..., min_length=8, description="Secure password (min 8 chars)")
    is_admin: Optional[bool] = Field(default=False, description="Whether the user has admin privileges")
    phone: Optional[str] = Field(default=None, description="Optional phone number")

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not v:
            return None
        if not PHONE_REGEX.match(v):
            raise ValueError("Invalid phone number format")
        return v


class UserUpdate(BaseSchema):
    """
    Fields the client can update. All optional — send only what changes.
    """
    email: Optional[EmailStr] = None
    password: Optional[str] = Field(default=None, min_length=8)
    is_admin: Optional[bool] = None
    is_active: Optional[bool] = None
    phone: Optional[str] = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not v:
            return None
        if not PHONE_REGEX.match(v):
            raise ValueError("Invalid phone number format")
        return v


class ForgotPasswordRequest(BaseSchema):
    """
    Schema for requesting a password reset OTP.
    """
    email: EmailStr


class ResetPasswordConfirm(BaseSchema):
    """
    Schema for confirming password reset with an OTP.
    """
    email: EmailStr
    otp: str = Field(..., min_length=6, max_length=6, description="6-digit verification code")
    new_password: str = Field(..., min_length=8, description="New secure password")


# ---------- Response Schemas (what the API sends back) ----------

class UserResponse(BaseSchema):
    """
    The public representation of a User.
    Notice: NO password field here — we never expose that.
    """
    id: UUID
    email: str
    is_active: bool
    is_admin: bool
    is_email_verified: bool = Field(default=False)
    email_verified_at: Optional[datetime] = None
    last_active_at: Optional[datetime] = None
    phone: Optional[str] = None
    created_at: datetime
    updated_at: datetime


# ---------- Token Schema (for Login) ----------

class Token(BaseSchema):
    """
    Authentication token response returned on successful login.
    """
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = Field(default="bearer")
    user: UserResponse
