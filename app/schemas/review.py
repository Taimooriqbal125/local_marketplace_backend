"""Pydantic schemas for Review resource."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class ReviewBase(BaseModel):
    """Shared fields for reviews."""
    
    rating: int = Field(..., ge=1, le=5, description="Rating from 1 to 5")
    comment: Optional[str] = Field(default=None, description="Optional feedback text")


class ReviewCreate(ReviewBase):
    """Payload to create a new review."""
    
    orderId: UUID = Field(..., description="The order being reviewed")


class ReviewResponse(BaseModel):
    """Review object returned by the API."""

    id: UUID
    orderId: UUID
    reviewerId: UUID
    reviewedUserId: UUID
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = None
    createdAt: datetime

    class Config:
        from_attributes = True


class ReviewReceivedResponse(BaseModel):
    """
    Customized response for received reviews.
    Enriched with reviewer profile and service listing info.
    """

    id: UUID
    rating: int
    comment: Optional[str] = None
    createdAt: datetime
    
    # New enriched fields
    reviewerName: str
    reviewerPhotoUrl: Optional[str] = None
    serviceTitle: str
    categoryName: str
    serviceImageUrl: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def map_relationships(cls, data: any) -> any:
        """Extract data from reviewer.profile and order.listing relationships."""
        if not hasattr(data, "reviewer") or not hasattr(data, "order"):
            return data

        # Check for reviewer profile
        reviewer_name = "Anonymous"
        reviewer_photo = None
        if data.reviewer and data.reviewer.profile:
            reviewer_name = data.reviewer.profile.name
            reviewer_photo = data.reviewer.profile.photoUrl

        # Check for listing info
        service_title = "Unknown Service"
        category_name = "Other"
        service_image = None
        if data.order and data.order.listing:
            service_title = data.order.listing.title
            if data.order.listing.category:
                category_name = data.order.listing.category.name
            
            # Extract primary image URL
            if data.order.listing.media:
                # media is pre-sorted by sortOrder in the model relationship
                service_image = data.order.listing.media[0].imageUrl

        # Return a dict for Pydantic to validate
        return {
            "id": data.id,
            "rating": data.rating,
            "comment": data.comment,
            "createdAt": data.createdAt,
            "reviewerName": reviewer_name,
            "reviewerPhotoUrl": reviewer_photo,
            "serviceTitle": service_title,
            "categoryName": category_name,
            "serviceImageUrl": service_image,
        }

    class Config:
        from_attributes = True


class ReviewForServiceResponse(BaseModel):
    """
    Leaner response for reviews listed under a specific service.
    Excludes service info (caller already knows the service).
    """

    id: UUID
    rating: int
    comment: Optional[str] = None
    createdAt: datetime

    # Reviewer info only
    reviewerName: str
    reviewerPhotoUrl: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def map_relationships(cls, data: any) -> any:
        """Extract reviewer profile data."""
        if not hasattr(data, "reviewer"):
            return data

        reviewer_name = "Anonymous"
        reviewer_photo = None
        if data.reviewer and data.reviewer.profile:
            reviewer_name = data.reviewer.profile.name
            reviewer_photo = data.reviewer.profile.photoUrl

        return {
            "id": data.id,
            "rating": data.rating,
            "comment": data.comment,
            "createdAt": data.createdAt,
            "reviewerName": reviewer_name,
            "reviewerPhotoUrl": reviewer_photo,
        }

    class Config:
        from_attributes = True
