"""Pydantic schemas for ServiceListing resource."""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal, Optional, List
from uuid import UUID

from fastapi import Query
from geoalchemy2.elements import WKBElement
from geoalchemy2.shape import to_shape
from pydantic import Field, field_validator, model_validator, computed_field

from .base import BaseSchema


# ---------------------------------------------------------------------------
# Allowed literals
# ---------------------------------------------------------------------------
PriceType = Literal["fixed", "hourly", "daily"]
ListingStatus = Literal["draft", "active", "paused", "closed", "banned"]


# ---------------------------------------------------------------------------
# Nested location point schema
# ---------------------------------------------------------------------------
class ServiceLocationPoint(BaseSchema):
    """
    Represents a geographic coordinate pair.
    Used for both input (create/update) and output (response).
    """
    latitude: float = Field(..., ge=-90, le=90, description="GPS Latitude")
    longitude: float = Field(..., ge=-180, le=180, description="GPS Longitude")


# ---------------------------------------------------------------------------
# Base — shared fields for Create / Update / Response
# ---------------------------------------------------------------------------
class ServiceListingBase(BaseSchema):
    """
    Fields shared across all ServiceListing schema variants.
    """
    title: str = Field(..., min_length=3, max_length=255, description="Brief, catchy title for the service")
    description: Optional[str] = Field(default=None, max_length=5000, description="Detailed service description")

    price_type: PriceType = Field(default="fixed", description="Pricing model (fixed, hourly, daily)")
    price_amount: Optional[Decimal] = Field(default=None, ge=0, decimal_places=2, description="Monetary value of the service")
    is_negotiable: bool = Field(default=False, description="Whether the price can be discussed")

    service_location: str = Field(..., max_length=255, description="Human-readable address or area name")
    service_radius_km: float = Field(..., ge=0, le=500, description="Service coverage radius from the central point")

    service_location_point: Optional[ServiceLocationPoint] = Field(
        default=None,
        description="Precise GPS coordinates for mapping and nearby search",
    )

    category_id: UUID = Field(..., description="ID of the category this service belongs to")
    city_id: Optional[UUID] = Field(default=None, description="ID of the city where the service is primarily located")
    status: ListingStatus = Field(default="draft", description="Current workflow state of the listing")

    @field_validator("title", "service_location")
    @classmethod
    def strip_and_validate_non_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Field cannot be blank")
        return v

    @field_validator("description")
    @classmethod
    def strip_optional(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return v.strip() or None

    @model_validator(mode="after")
    def validate_pricing_rules(self) -> "ServiceListingBase":
        """
        Ensures business rules for pricing are followed.
        """
        if self.price_amount is None:
            raise ValueError(f"priceAmount is required for price type '{self.price_type}'")
        
        if self.price_type == "fixed" and self.is_negotiable:
            raise ValueError("Fixed price services cannot be negotiable.")
            
        return self


# ---------------------------------------------------------------------------
# Create / Update
# ---------------------------------------------------------------------------
class ServiceListingCreate(ServiceListingBase):
    """Payload for POST /services."""
    pass


class ServiceListingUpdate(BaseSchema):
    """
    Payload for PATCH /services/{id}.
    Every field is optional; only provided fields are updated.
    """
    title: Optional[str] = Field(default=None, min_length=3, max_length=255)
    description: Optional[str] = Field(default=None, max_length=5000)
    price_type: Optional[PriceType] = None
    price_amount: Optional[Decimal] = Field(default=None, ge=0, decimal_places=2)
    is_negotiable: Optional[bool] = None
    service_location: Optional[str] = Field(default=None, max_length=255)
    service_radius_km: Optional[float] = Field(default=None, ge=0, le=500)
    service_location_point: Optional[ServiceLocationPoint] = None
    category_id: Optional[UUID] = None
    city_id: Optional[UUID] = None
    status: Optional[ListingStatus] = None

    @field_validator("title")
    @classmethod
    def title_strip(cls, v: Optional[str]) -> Optional[str]:
        if v is None: return v
        v = v.strip()
        if not v: raise ValueError("title cannot be blank")
        return v


# ---------------------------------------------------------------------------
# Relationship Schemas (Nested)
# ---------------------------------------------------------------------------
class SellerProfileSummary(BaseSchema):
    """Simplified profile data for service cards."""
    name: str
    photo_url: Optional[str] = None
    seller_rating_avg: Decimal = Field(default=Decimal("0.00"))
    seller_rating_count: int = 0


class SellerProfileDetail(SellerProfileSummary):
    """Enriched profile data for service details."""
    user_id: UUID
    phone: Optional[str] = None


# ---------------------------------------------------------------------------
# Response Models
# ---------------------------------------------------------------------------
class ServiceListingCore(BaseSchema):
    """Essential card fields shared by all listing views."""
    id: UUID
    title: str
    description: Optional[str] = None
    price_type: PriceType
    price_amount: Optional[Decimal] = None
    is_negotiable: bool
    service_location: str
    status: ListingStatus
    created_at: datetime
    updated_at: datetime

    # These will be populated by validators or computed fields
    category_name: Optional[str] = None
    city_name: Optional[str] = None
    image_url: Optional[str] = None


class ServiceListingResponse(ServiceListingCore):
    """Full public listing object with seller and location details."""
    category_id: UUID
    city_id: Optional[UUID] = None
    service_radius_km: float
    service_location_point: Optional[ServiceLocationPoint] = None
    seller: Optional[SellerProfileSummary] = None

    @model_validator(mode="before")
    @classmethod
    def map_relationships(cls, data: any) -> any:
        """
        Advanced relationship mapper to flatten ORM attributes into schema fields.
        """
        if isinstance(data, dict):
            return data

        # Map basic names from objects
        category_name = data.category.name if hasattr(data, "category") and data.category else "Other"
        city_name = data.city.name if hasattr(data, "city") and data.city else None
        
        # Map primary image
        image_url = None
        if hasattr(data, "media") and data.media:
            # Assumes media list is already sorted by sortOrder in DB relationship
            image_url = data.media[0].imageUrl

        # Map seller summary
        seller_summary = None
        if hasattr(data, "seller") and data.seller and hasattr(data.seller, "profile") and data.seller.profile:
            p = data.seller.profile
            seller_summary = {
                "name": p.name,
                "photo_url": p.photoUrl,
                "seller_rating_avg": p.sellerRatingAvg,
                "seller_rating_count": p.sellerRatingCount,
            }

        # Convert attributes to dict for Pydantic processing
        result = {k: v for k, v in data.__dict__.items() if not k.startswith('_')}
        result.update({
            "category_name": category_name,
            "city_name": city_name,
            "image_url": image_url,
            "seller": seller_summary
        })
        return result

    @field_validator("service_location_point", mode="before")
    @classmethod
    def deserialize_geo(cls, v: any) -> Optional[ServiceLocationPoint]:
        if v is None: return None
        if isinstance(v, WKBElement):
            shape = to_shape(v)
            return ServiceLocationPoint(latitude=shape.y, longitude=shape.x)
        if isinstance(v, dict): return ServiceLocationPoint(**v)
        return v


class ServiceListingMeResponse(ServiceListingCore):
    """Response for /services/me (seller's own listings)."""
    category_id: UUID

    @model_validator(mode="before")
    @classmethod
    def map_me_fields(cls, data: any) -> any:
        if isinstance(data, dict): return data
        
        category_name = data.category.name if hasattr(data, "category") and data.category else "Other"
        image_url = data.media[0].imageUrl if hasattr(data, "media") and data.media else None

        result = {k: v for k, v in data.__dict__.items() if not k.startswith('_')}
        result.update({
            "category_name": category_name,
            "image_url": image_url
        })
        return result


class ServiceListingDetailResponse(ServiceListingResponse):
    """
    Detailed listing view including full seller details and contact info.
    """
    seller: Optional[SellerProfileDetail] = None

    @model_validator(mode="before")
    @classmethod
    def map_detail_relationships(cls, data: any) -> any:
        if isinstance(data, dict): return data
        
        # Base mapping
        result = ServiceListingResponse.map_relationships(data)
        
        # Enrich seller with detail info
        if hasattr(data, "seller") and data.seller and data.seller.profile:
            p = data.seller.profile
            result["seller"] = {
                "user_id": p.userId,
                "name": p.name,
                "photo_url": p.photoUrl,
                "seller_rating_avg": p.sellerRatingAvg,
                "seller_rating_count": p.sellerRatingCount,
                "phone": data.seller.phone if hasattr(data.seller, "phone") else None
            }
        return result


# ---------------------------------------------------------------------------
# Filter Dependencies
# ---------------------------------------------------------------------------
class ServiceListingFilterParams:
    """
    FastAPI dependency for query string filtering.
    """
    def __init__(
        self,
        is_negotiable: Annotated[Optional[bool], Query(alias="isNegotiable")] = None,
        price_type: Annotated[Optional[PriceType], Query(alias="priceType")] = None,
        min_price: Annotated[Optional[Decimal], Query(alias="minPrice", ge=0)] = None,
        max_price: Annotated[Optional[Decimal], Query(alias="maxPrice", ge=0)] = None,
        search: Optional[str] = Query(None, max_length=100),
        category_id: Annotated[Optional[UUID], Query(alias="categoryId")] = None,
        city_id: Annotated[Optional[UUID], Query(alias="cityId")] = None,
        seller_id: Annotated[Optional[UUID], Query(alias="sellerId")] = None,
        profile_id: Annotated[Optional[UUID], Query(alias="profileId")] = None,
        status: ListingStatus = "active",
        top_selling: Annotated[Optional[bool], Query(alias="topSelling")] = None,
        top_rating: Annotated[Optional[bool], Query(alias="topRating")] = None,
        city_slug: Annotated[Optional[str], Query(alias="citySlug")] = None,
        category_slug: Annotated[Optional[str], Query(alias="categorySlug")] = None,
        page: int = Query(1, ge=1),
        page_size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 20,
    ) -> None:
        self.is_negotiable = is_negotiable
        self.price_type = price_type
        self.min_price = min_price
        self.max_price = max_price
        self.search = search
        self.category_id = category_id
        self.city_id = city_id
        self.seller_id = seller_id
        self.profile_id = profile_id
        self.status = status
        self.top_selling = top_selling
        self.top_rating = top_rating
        self.city_slug = city_slug
        self.category_slug = category_slug
        self.page = page
        self.page_size = page_size


class ServiceListingNearbyFilterParams:
    """
    FastAPI dependency for nearby query string filtering.
    """
    def __init__(
        self,
        is_negotiable: Annotated[Optional[bool], Query(alias="isNegotiable")] = None,
        price_type: Annotated[Optional[PriceType], Query(alias="priceType")] = None,
        category_id: Annotated[Optional[UUID], Query(alias="categoryId")] = None,
        status: ListingStatus = "active",
        top_selling: Annotated[Optional[bool], Query(alias="topSelling")] = None,
        top_rating: Annotated[Optional[bool], Query(alias="topRating")] = None,
        page: int = Query(1, ge=1),
        page_size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 20,
    ) -> None:
        self.is_negotiable = is_negotiable
        self.price_type = price_type
        self.category_id = category_id
        self.status = status
        self.top_selling = top_selling
        self.top_rating = top_rating
        self.page = page
        self.page_size = page_size


# ---------------------------------------------------------------------------
# Nearby Search Models
# ---------------------------------------------------------------------------
class ServiceListingNearbyResponse(ServiceListingCore):
    """Optimized response for location-based searches."""
    distance_km: Optional[float] = None
    seller: Optional[SellerProfileSummary] = None

    @model_validator(mode="before")
    @classmethod
    def map_nearby(cls, data: any) -> any:
        # Re-use logic from Response
        return ServiceListingResponse.map_relationships(data)


class ServiceListingNearbyListResponse(BaseSchema):
    """Paginated nearby results wrapper."""
    total: int
    page: int
    page_size: int
    radius_km: float
    results: List[ServiceListingNearbyResponse]


class ServiceListingListResponse(BaseSchema):
    """Wrapper for standard paginated results."""
    total: int
    page: int
    page_size: int
    results: List[ServiceListingResponse]

class ServiceListingPublicResponse(ServiceListingResponse):
    pass

class ServiceListingPublicListResponse(BaseSchema):
    total: int
    page: int
    page_size: int
    results: List[ServiceListingPublicResponse]

class ServiceListingMeListResponse(BaseSchema):
    total: int
    page: int
    page_size: int
    results: List[ServiceListingMeResponse]

class ServiceListingProfileSummaryResponse(ServiceListingCore):
    pass

class ServiceListingProfileSummaryListResponse(BaseSchema):
    profile_id: UUID
    total_services: int
    page: int
    page_size: int
    results: List[ServiceListingProfileSummaryResponse]
