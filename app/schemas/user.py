"""
Pydantic schemas for the User resource.

Schemas define what the API *accepts* (request bodies) and what it *returns* (responses).
They also handle automatic validation — if a field is wrong, FastAPI returns a 422 error.

Why separate from the SQLAlchemy model?
  - Model  = database shape   (what gets saved)
  - Schema = API shape         (what the client sees)
"""

from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional
from uuid import UUID


# ---------- Request Schemas (what the client sends) ----------

class UserCreate(BaseModel):
    """Fields required to create a new user."""
    name: str
    email: EmailStr
    password: str
    is_admin: Optional[bool] = Field(default=False, alias="isAdmin")

    class Config:
        populate_by_name = True  # allows both is_admin and isAdmin


class UserUpdate(BaseModel):
    """Fields the client can update. All optional — send only what changes."""
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    is_admin: Optional[bool] = None
    is_active: Optional[bool] = None


# ---------- Response Schemas (what the API sends back) ----------

class UserResponse(BaseModel):
    """
    The public representation of a User.
    Notice: NO password field here — we never expose that.
    """
    id: UUID
    name: str
    email: str
    is_active: bool
    is_admin: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True  # allows creating this from a SQLAlchemy model instance


# ---------- Token Schema (for Login) ----------

class Token(BaseModel):
    access_token: str
    token_type: str
