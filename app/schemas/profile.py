"""Pydantic schemas for Profile resource."""

from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ProfileBase(BaseModel):
    """Shared profile fields used in create/update/response schemas."""

    name: str = Field(min_length=1, max_length=100)
    bio: Optional[str] = None
    photoUrl: Optional[str] = Field(default=None, max_length=500)
    sellerStatus: Literal["none", "active", "suspended"] = "none"
    sellerCompletedOrdersCount: Optional[int] = 0
    lastLocation: Optional[str] = Field(default=None, max_length=50)
    isBanned: bool = False


class ProfileCreate(ProfileBase):
    """Fields required to create a profile."""

    userId: UUID
    sellerRatingAvg: Decimal = Field(default=Decimal("0.00"), ge=0, le=9.99)
    sellerRatingCount: int = Field(default=0, ge=0)


class ProfileUpdate(BaseModel):
    """Fields that can be updated for a profile (all optional)."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    bio: Optional[str] = None
    photoUrl: Optional[str] = Field(default=None, max_length=500)
    sellerStatus: Optional[Literal["none", "active", "suspended"]] = None
    sellerCompletedOrdersCount: Optional[int] = Field(default=None, ge=0)
    lastLocation: Optional[str] = Field(default=None, max_length=50)
    isBanned: Optional[bool] = None
    sellerRatingAvg: Optional[Decimal] = Field(default=None, ge=0, le=9.99)
    sellerRatingCount: Optional[int] = Field(default=None, ge=0)


class ProfileResponse(ProfileBase):
    """Profile object returned by the API."""

    userId: UUID
    sellerRatingAvg: Decimal
    sellerRatingCount: int
    sellerCompletedOrdersCount: int
    createdAt: datetime
    updatedAt: datetime
    name: str

    class Config:
        from_attributes = True
