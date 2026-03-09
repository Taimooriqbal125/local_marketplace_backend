"""Pydantic schemas for Review resource."""

from datetime import datetime
from typing import Optional, List
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


# ---------------------------------------------------------------------------
# POST /reviews/ — creation response
# ---------------------------------------------------------------------------
class ReviewCreateResponse(BaseModel):
    """Refined response for review creation."""

    id: UUID
    createdAt: datetime
    rating: int
    sellerName: str

    @model_validator(mode="before")
    @classmethod
    def map_relationships(cls, data: any) -> any:
        """Map reviewed_user.profile.name to sellerName."""
        if not hasattr(data, "reviewed_user"):
            return data

        seller_name = "Unknown Seller"
        if data.reviewed_user and data.reviewed_user.profile:
            seller_name = data.reviewed_user.profile.name

        return {
            "id": data.id,
            "createdAt": data.createdAt,
            "rating": data.rating,
            "sellerName": seller_name,
        }

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# /reviews/me/given — reviews written by the buyer
# ---------------------------------------------------------------------------
class ReviewGivenResponse(BaseModel):
    """Refined response for reviews given by the user, with service context."""

    id: UUID
    rating: int
    comment: Optional[str] = None
    createdAt: datetime

    # Service context
    serviceName: str
    categoryName: str
    imageUrl: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def map_relationships(cls, data: any) -> any:
        """Map listing, category, and media info."""
        if not hasattr(data, "order") or not data.order or not data.order.listing:
            return data

        listing = data.order.listing
        service_name = listing.title
        category_name = listing.category.name if listing.category else "Other"
        
        service_image = None
        if listing.media:
            service_image = listing.media[0].imageUrl

        return {
            "id": data.id,
            "rating": data.rating,
            "comment": data.comment,
            "createdAt": data.createdAt,
            "serviceName": service_name,
            "categoryName": category_name,
            "imageUrl": service_image,
        }

    class Config:
        from_attributes = True

class AdminReviewResponse(BaseModel):
    """
    Comprehensive review response for admin dashboard.
    Includes reviewer, seller, and service context.
    """

    id: UUID
    rating: int
    comment: Optional[str] = None
    createdAt: datetime
    
    # Enriched context
    reviewerName: str
    sellerName: str
    serviceName: str
    serviceImages: List[str] = []

    @model_validator(mode="before")
    @classmethod
    def map_relationships(cls, data: any) -> any:
        """Map fields from reviewer, reviewed_user, and order.listing relations."""
        if isinstance(data, dict):
            return data

        # Reviewer info
        reviewer_name = "Anonymous"
        if data.reviewer and data.reviewer.profile:
            reviewer_name = data.reviewer.profile.name or "User"
        
        # Seller info
        seller_name = "Unknown Seller"
        if data.reviewed_user and data.reviewed_user.profile:
            seller_name = data.reviewed_user.profile.name or "Seller"

        # Service info
        service_name = "Unknown Service"
        service_images = []
        if data.order and data.order.listing:
            service_name = data.order.listing.title
            if data.order.listing.media:
                service_images = [m.imageUrl for m in data.order.listing.media]

        return {
            "id": data.id,
            "rating": data.rating,
            "comment": data.comment,
            "createdAt": data.createdAt,
            "reviewerName": reviewer_name,
            "sellerName": seller_name,
            "serviceName": service_name,
            "serviceImages": service_images,
        }

    class Config:
        from_attributes = True
