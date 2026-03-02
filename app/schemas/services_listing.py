"""Pydantic schemas for ServiceListing resource."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Allowed literals — change these here and everywhere updates automatically
# ---------------------------------------------------------------------------
PriceType = Literal["fixed", "hourly", "daily", "negotiable"]
ListingStatus = Literal["draft", "active", "paused", "closed", "banned"]


# ---------------------------------------------------------------------------
# Base — shared fields for Create / Update / Response
# ---------------------------------------------------------------------------
class ServiceListingBase(BaseModel):
    """Fields shared across all ServiceListing schema variants."""

    title: str = Field(..., min_length=3, max_length=255)
    description: Optional[str] = Field(default=None, max_length=5000)

    priceType: PriceType = Field(default="fixed")
    priceAmount: Optional[Decimal] = Field(default=None, ge=0, decimal_places=2)
    isNegotiable: bool = Field(default=False)

    serviceLocation: Optional[str] = Field(default=None, max_length=255)
    serviceRadiusKm: Optional[float] = Field(default=None, ge=0, le=500)

    # MVP: category is always required; city is optional
    categoryId: int = Field(..., gt=0)
    cityId: Optional[UUID] = None

    status: ListingStatus = Field(default="draft")

    # ── Validators ──────────────────────────────────────────────────────────

    @field_validator("title")
    @classmethod
    def title_strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("title cannot be blank")
        return v

    @field_validator("description")
    @classmethod
    def description_strip(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        return v or None  # collapse empty string → None

    @field_validator("serviceLocation")
    @classmethod
    def service_location_strip(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return v.strip() or None

    @model_validator(mode="after")
    def price_amount_required_for_fixed(self) -> "ServiceListingBase":
        """
        If priceType is 'fixed' | 'hourly' | 'daily', priceAmount should be set.
        For 'negotiable', it is optional.
        """
        if self.priceType != "negotiable" and self.priceAmount is None:
            raise ValueError(
                f"priceAmount is required when priceType is '{self.priceType}'"
            )
        return self


# ---------------------------------------------------------------------------
# Create — what a client POSTs to create a new listing
# ---------------------------------------------------------------------------
class ServiceListingCreate(ServiceListingBase):
    """
    Payload for POST /service-listings.

    sellerId is injected server-side from the authenticated user —
    it is NOT accepted from the request body.
    """
    pass


# ---------------------------------------------------------------------------
# Update — PATCH payload (all fields optional)
# ---------------------------------------------------------------------------
class ServiceListingUpdate(BaseModel):
    """
    Payload for PATCH /service-listings/{id}.
    Every field is optional; only provided fields are updated.
    """

    title: Optional[str] = Field(default=None, min_length=3, max_length=255)
    description: Optional[str] = Field(default=None, max_length=5000)

    priceType: Optional[PriceType] = None
    priceAmount: Optional[Decimal] = Field(default=None, ge=0, decimal_places=2)
    isNegotiable: Optional[bool] = None

    serviceLocation: Optional[str] = Field(default=None, max_length=255)
    serviceRadiusKm: Optional[float] = Field(default=None, ge=0, le=500)

    categoryId: Optional[int] = Field(default=None, gt=0)
    cityId: Optional[UUID] = None

    status: Optional[ListingStatus] = None

    @field_validator("title")
    @classmethod
    def title_strip(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("title cannot be blank")
        return v

    @field_validator("description", "serviceLocation")
    @classmethod
    def optional_str_strip(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return v.strip() or None


# ---------------------------------------------------------------------------
# Response — what the API returns
# ---------------------------------------------------------------------------
class ServiceListingResponse(ServiceListingBase):
    """
    Full listing object returned by the API.
    Includes server-generated fields (id, sellerId, timestamps).
    """

    id: UUID
    sellerId: UUID
    createdAt: datetime
    updatedAt: datetime

    model_config = dict(from_attributes=True)  # Pydantic v2: ORM → Pydantic


# ---------------------------------------------------------------------------
# Paginated list response helper
# ---------------------------------------------------------------------------
class ServiceListingListResponse(BaseModel):
    """Wrapper for paginated listing results."""

    total: int
    page: int
    pageSize: int
    results: list[ServiceListingResponse]
