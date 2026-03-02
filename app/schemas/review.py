"""Pydantic schemas for Review resource."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ReviewBase(BaseModel):
    """Shared fields for reviews."""
    
    rating: int = Field(..., ge=1, le=5, description="Rating from 1 to 5")
    comment: Optional[str] = Field(default=None, description="Optional feedback text")


class ReviewCreate(ReviewBase):
    """Payload to create a new review."""
    
    orderId: UUID = Field(..., description="The order being reviewed")


class ReviewResponse(ReviewBase):
    """Review object returned by the API."""

    id: UUID
    orderId: UUID
    reviewerId: UUID
    reviewedUserId: UUID
    createdAt: datetime

    class Config:
        from_attributes = True
