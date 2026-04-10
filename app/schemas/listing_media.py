"""Pydantic schemas for ListingMedia resource."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import Field

from .base import BaseSchema


# ---------------------------------------------------------------------------
# Base — shared fields for Create / Update / Response
# ---------------------------------------------------------------------------
class ListingMediaBase(BaseSchema):
    """Fields shared across all ListingMedia schema variants."""

    image_url: str = Field(..., max_length=500, description="Full URL of the image")
    sort_order: int = Field(default=0, description="Ordering of images (0 is primary)")


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------
class ListingMediaCreate(ListingMediaBase):
    """Payload for POST /listingmedia/ when you already have a URL."""

    listing_id: UUID = Field(..., description="The ID of the service listing this media belongs to")
    cloudinary_public_id: Optional[str] = Field(
        default=None, 
        max_length=300, 
        description="Cloudinary public_id for asset management"
    )


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------
class ListingMediaUpdate(BaseSchema):
    """Payload for PATCH /listingmedia/{id}."""

    image_url: Optional[str] = Field(default=None, max_length=500)
    sort_order: Optional[int] = None


# ---------------------------------------------------------------------------
# Response
# ---------------------------------------------------------------------------
class ListingMediaResponse(ListingMediaBase):
    """Full media object returned by the API."""

    id: UUID
    listing_id: UUID
    cloudinary_public_id: Optional[str] = None
    created_at: datetime
