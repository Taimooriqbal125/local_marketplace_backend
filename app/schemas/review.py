"""Pydantic schemas for Review resource."""

from __future__ import annotations

from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import Field, model_validator

from .base import BaseSchema


class ReviewBase(BaseSchema):
    """Shared fields for reviews."""
    
    rating: int = Field(..., ge=1, le=5, description="Numerical rating from 1 (lowest) to 5 (highest)")
    comment: Optional[str] = Field(default=None, description="Optional textual feedback from the reviewer")


class ReviewCreate(ReviewBase):
    """Payload to create a new review for a specific order."""
    
    order_id: UUID = Field(..., description="The unique ID of the order being reviewed")


class ReviewResponse(ReviewBase):
    """Full review object as stored in the database."""

    id: UUID
    order_id: UUID
    reviewer_id: UUID
    reviewed_user_id: UUID
    created_at: datetime


class ReviewReceivedResponse(BaseSchema):
    """
    Enriched response for reviews received by a user.
    Includes reviewer profile details and service context.
    """

    id: UUID
    rating: int
    comment: Optional[str] = None
    created_at: datetime
    
    # Enriched context fields
    reviewer_name: str
    reviewer_photo_url: Optional[str] = None
    service_title: str
    category_name: str
    service_image_url: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def map_relationships(cls, data: any) -> any:
        """Flattens reviewer profile and order/listing data from ORM objects."""
        if isinstance(data, dict):
            return data

        # Reviewer context
        reviewer_name = "Anonymous"
        reviewer_photo = None
        if data.reviewer and data.reviewer.profile:
            reviewer_name = data.reviewer.profile.name
            reviewer_photo = data.reviewer.profile.photo_url

        # Service context
        service_title = "Unknown Service"
        category_name = "Other"
        service_image = None
        if data.order and data.order.listing:
            listing = data.order.listing
            service_title = listing.title
            if listing.category:
                category_name = listing.category.name
            if listing.media:
                service_image = listing.media[0].image_url

        # Convert ORM to dict and update with flattened fields
        result = {k: v for k, v in data.__dict__.items() if not k.startswith('_')}
        result.update({
            "reviewer_name": reviewer_name,
            "reviewer_photo_url": reviewer_photo,
            "service_title": service_title,
            "category_name": category_name,
            "service_image_url": service_image,
        })
        return result


class ReviewForServiceResponse(BaseSchema):
    """
    Lean response for reviews associated with a specific service listing.
    """

    id: UUID
    rating: int
    comment: Optional[str] = None
    created_at: datetime

    # Reviewer identity
    reviewer_name: str
    reviewer_photo_url: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def map_reviewer(cls, data: any) -> any:
        if isinstance(data, dict): return data

        reviewer_name = "Anonymous"
        reviewer_photo = None
        if data.reviewer and data.reviewer.profile:
            reviewer_name = data.reviewer.profile.name
            reviewer_photo = data.reviewer.profile.photo_url

        result = {k: v for k, v in data.__dict__.items() if not k.startswith('_')}
        result.update({
            "reviewer_name": reviewer_name,
            "reviewer_photo_url": reviewer_photo,
        })
        return result


class ReviewByUserReviewer(BaseSchema):
    """Minimal reviewer identity payload."""
    id: UUID
    name: str
    photo_url: Optional[str] = None


class ReviewByUserResponse(BaseSchema):
    """
    Schema for reviews received by a specific user profile.
    """
    id: UUID
    rating: int = Field(..., ge=1, le=5)
    note: Optional[str] = None  # Re-mapped from 'comment'
    created_at: datetime
    reviewer: ReviewByUserReviewer

    @model_validator(mode="before")
    @classmethod
    def map_user_review(cls, data: any) -> any:
        if isinstance(data, dict): return data

        reviewer_name = "Anonymous"
        reviewer_photo = None
        if data.reviewer and data.reviewer.profile:
            reviewer_name = data.reviewer.profile.name or "Anonymous"
            reviewer_photo = data.reviewer.profile.photo_url

        return {
            "id": data.id,
            "rating": data.rating,
            "note": data.comment,
            "created_at": data.created_at,
            "reviewer": {
                "id": data.reviewer_id,
                "name": reviewer_name,
                "photo_url": reviewer_photo,
            },
        }


class ReviewCreateResponse(BaseSchema):
    """Summary response returned immediately after successful review creation."""
    id: UUID
    created_at: datetime
    rating: int
    seller_name: str

    @model_validator(mode="before")
    @classmethod
    def map_seller_name(cls, data: any) -> any:
        if isinstance(data, dict): return data

        seller_name = "Unknown Seller"
        if data.reviewed_user and data.reviewed_user.profile:
            seller_name = data.reviewed_user.profile.name

        result = {k: v for k, v in data.__dict__.items() if not k.startswith('_')}
        result["seller_name"] = seller_name
        return result


class ReviewGivenResponse(BaseSchema):
    """Response for reviews authored by the current user."""
    id: UUID
    order_id: UUID
    rating: int
    comment: Optional[str] = None
    created_at: datetime

    # Contextual service info
    service_name: str
    category_name: str
    image_url: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def map_service_context(cls, data: any) -> any:
        if isinstance(data, dict): return data

        service_name = "Unknown Service"
        category_name = "Other"
        image_url = None

        if data.order and data.order.listing:
            listing = data.order.listing
            service_name = listing.title
            category_name = listing.category.name if listing.category else "Other"
            if listing.media:
                image_url = listing.media[0].image_url

        result = {k: v for k, v in data.__dict__.items() if not k.startswith('_')}
        result.update({
            "service_name": service_name,
            "category_name": category_name,
            "image_url": image_url,
        })
        return result


class AdminReviewResponse(BaseSchema):
    """Comprehensive review data for administrative oversight."""
    id: UUID
    rating: int
    comment: Optional[str] = None
    created_at: datetime
    
    # Identity and context strings
    reviewer_name: str
    seller_name: str
    service_name: str
    service_images: List[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def map_admin_fields(cls, data: any) -> any:
        if isinstance(data, dict): return data

        reviewer_name = data.reviewer.profile.name if data.reviewer and data.reviewer.profile else "User"
        seller_name = data.reviewed_user.profile.name if data.reviewed_user and data.reviewed_user.profile else "Seller"
        
        service_name = "Unknown Service"
        service_images = []
        if data.order and data.order.listing:
            service_name = data.order.listing.title
            service_images = [m.image_url for m in data.order.listing.media] if data.order.listing.media else []

        result = {k: v for k, v in data.__dict__.items() if not k.startswith('_')}
        result.update({
            "reviewer_name": reviewer_name,
            "seller_name": seller_name,
            "service_name": service_name,
            "service_images": service_images,
        })
        return result
