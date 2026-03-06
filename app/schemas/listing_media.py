"""Pydantic schemas for ListingMedia resource."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Base — shared fields for Create / Update / Response
# ---------------------------------------------------------------------------
class ListingMediaBase(BaseModel):
    """Fields shared across all ListingMedia schema variants."""

    imageUrl: str = Field(..., max_length=500, description="Full URL of the image")
    sortOrder: int = Field(default=0, description="Ordering of images (0 is primary)")


# ---------------------------------------------------------------------------
# Create — what a client POSTs to add media to a listing
# ---------------------------------------------------------------------------
class ListingMediaCreate(ListingMediaBase):
    """Payload for POST /listingmedia/ when you already have a URL (e.g. from external source)."""

    listingId: UUID = Field(..., description="The ID of the service listing this media belongs to")
    cloudinaryPublicId: Optional[str] = Field(default=None, max_length=300, description="Cloudinary public_id for asset management")


# ---------------------------------------------------------------------------
# Update — PATCH payload (all fields optional)
# ---------------------------------------------------------------------------
class ListingMediaUpdate(BaseModel):
    """Payload for PATCH /listingmedia/{id}."""

    imageUrl: Optional[str] = Field(default=None, max_length=500)
    sortOrder: Optional[int] = None


# ---------------------------------------------------------------------------
# Response — what the API returns
# ---------------------------------------------------------------------------
class ListingMediaResponse(ListingMediaBase):
    """Full media object returned by the API."""

    id: UUID
    listingId: UUID
    cloudinaryPublicId: Optional[str] = None
    createdAt: datetime

    model_config = dict(from_attributes=True)
