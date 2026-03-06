"""Pydantic schemas for ServiceListing resource."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal, Optional
from uuid import UUID

from fastapi import Query
from geoalchemy2.shape import to_shape
from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Allowed literals
# ---------------------------------------------------------------------------
PriceType = Literal["fixed", "hourly", "daily", "negotiable"]
ListingStatus = Literal["draft", "active", "paused", "closed", "banned"]


# ---------------------------------------------------------------------------
# Nested location point schema — same pattern as profile
# ---------------------------------------------------------------------------
class ServiceLocationPoint(BaseModel):
    """
    Represents a geographic coordinate pair.
    Used for both input (create/update) and output (response).
    """
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)


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

    # Human-readable address label (still kept — useful for display)
    serviceLocation: str = Field(..., max_length=255)

    # ✅ Coverage radius — how far the provider serves from their point
    serviceRadiusKm: float = Field(..., ge=0, le=500)

    # ✅ Structured lat/lon — accepts both servicePoint and service_location_point
    service_location_point: Optional[ServiceLocationPoint] = Field(
        default=None,
        alias="servicePoint",
        description="Precise GPS coordinates of the service location",
    )

    model_config = dict(populate_by_name=True)

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
        return v.strip() or None

    @field_validator("serviceLocation")
    @classmethod
    def service_location_strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("serviceLocation cannot be blank")
        return v

    @model_validator(mode="after")
    def price_amount_required_for_fixed(self) -> "ServiceListingBase":
        if self.priceType != "negotiable" and self.priceAmount is None:
            raise ValueError(
                f"priceAmount is required when priceType is '{self.priceType}'"
            )
        return self


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------
class ServiceListingCreate(ServiceListingBase):
    """
    Payload for POST /services.
    sellerId is injected server-side from the authenticated user.
    """
    pass


# ---------------------------------------------------------------------------
# Update — PATCH payload (all fields optional)
# ---------------------------------------------------------------------------
class ServiceListingUpdate(BaseModel):
    """
    Payload for PATCH /services/{id}.
    Every field is optional; only provided fields are updated.
    """

    title: Optional[str] = Field(default=None, min_length=3, max_length=255)
    description: Optional[str] = Field(default=None, max_length=5000)

    priceType: Optional[PriceType] = None
    priceAmount: Optional[Decimal] = Field(default=None, ge=0, decimal_places=2)
    isNegotiable: Optional[bool] = None

    serviceLocation: Optional[str] = Field(default=None, max_length=255)
    serviceRadiusKm: Optional[float] = Field(default=None, ge=0, le=500)

    # ✅ Optional location update
    service_location_point: Optional[ServiceLocationPoint] = None

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
# Seller Info for Cards
# ---------------------------------------------------------------------------
class SellerProfileSchema(BaseModel):
    """Simplified profile data for service cards."""
    name: str
    photoUrl: Optional[str] = None
    sellerRatingAvg: Decimal = Field(default=Decimal("0.00"))
    sellerRatingCount: int = 0

    model_config = dict(from_attributes=True)


# ---------------------------------------------------------------------------
# Response Hierarchy
# ---------------------------------------------------------------------------
class ServiceListingCore(BaseModel):
    """Essential card fields shared by all listing views."""
    id: UUID
    title: str
    description: Optional[str] = None
    priceType: PriceType
    priceAmount: Optional[Decimal] = None
    isNegotiable: bool
    serviceLocation: str

    model_config = dict(from_attributes=True)


class ServiceListingBaseResponse(ServiceListingCore):
    """Internal base for full views (includes metadata and radius)."""
    categoryId: int
    serviceRadiusKm: float
    status: ListingStatus
    createdAt: datetime
    updatedAt: datetime


class ServiceListingMeResponse(ServiceListingBaseResponse):
    """Cleaned-up response for /services/me (excludes public IDs)."""
    pass


class ServiceListingResponse(ServiceListingBaseResponse):
    """Full public listing object with seller and location details."""
    sellerId: UUID
    cityId: Optional[UUID] = None
    service_location_point: Optional[ServiceLocationPoint] = None
    seller: Optional[SellerProfileSchema] = None

    @field_validator("seller", mode="before")
    @classmethod
    def map_seller_profile(cls, v: object) -> Optional[dict]:
        """Maps SQL User model → SellerProfileSchema."""
        if isinstance(v, (dict, SellerProfileSchema)):
            return v
        if hasattr(v, "profile") and v.profile:
            return {
                "name": v.profile.name,
                "photoUrl": v.profile.photoUrl,
                "sellerRatingAvg": v.profile.sellerRatingAvg
            }
        return None

    @field_validator("service_location_point", mode="before")
    @classmethod
    def deserialize_geo(cls, v: object) -> Optional[ServiceLocationPoint]:
        """Convert PostGIS WKBElement → ServiceLocationPoint."""
        if v is None: return None
        if isinstance(v, dict): return ServiceLocationPoint(**v)
        if isinstance(v, ServiceLocationPoint): return v
        try:
            shape = to_shape(v)
            return ServiceLocationPoint(latitude=shape.y, longitude=shape.x)
        except Exception: return None


class ServiceListingDetailResponse(ServiceListingCore):
    """
    Detailed listing view for the public.
    Includes enriched seller and category data, excludes internal IDs.
    """
    cityName: Optional[str] = None
    categoryName: str
    seller: SellerProfileSchema
    serviceRadiusKm: float
    service_location_point: Optional[ServiceLocationPoint] = None

    @model_validator(mode="before")
    @classmethod
    def map_relations(cls, data: any) -> any:
        """Map city and category names from SQLAlchemy relations."""
        if hasattr(data, "city") and data.city:
            setattr(data, "cityName", data.city.name)
        if hasattr(data, "category") and data.category:
            setattr(data, "categoryName", data.category.name)
        return data

    @field_validator("seller", mode="before")
    @classmethod
    def map_seller_profile(cls, v: object) -> Optional[dict]:
        """Maps SQL User model → SellerProfileSchema."""
        if isinstance(v, (dict, SellerProfileSchema)):
            return v
        if v and hasattr(v, "profile") and v.profile:
            return {
                "name": v.profile.name,
                "photoUrl": v.profile.photoUrl,
                "sellerRatingAvg": v.profile.sellerRatingAvg,
                "sellerRatingCount": v.profile.sellerRatingCount
            }
        return None

    @field_validator("service_location_point", mode="before")
    @classmethod
    def deserialize_geo(cls, v: object) -> Optional[ServiceLocationPoint]:
        """Convert PostGIS WKBElement → ServiceLocationPoint."""
        if v is None: return None
        if isinstance(v, dict): return ServiceLocationPoint(**v)
        if isinstance(v, ServiceLocationPoint): return v
        try:
            shape = to_shape(v)
            return ServiceLocationPoint(latitude=shape.y, longitude=shape.x)
        except Exception: return None


# ---------------------------------------------------------------------------
# Reusable filter dependency — inject via Depends(ServiceListingFilterParams)
# ---------------------------------------------------------------------------
class ServiceListingFilterParams:
    """
    FastAPI dependency that bundles all common service-listing query filters.

    Supports camelCase aliases for JSON-API consistency while keeping
    Python attribute names in snake_case.

    Usage::

        @router.get("/")
        def list_listings(
            filters: Annotated[ServiceListingFilterParams, Depends()],
            db: Session = Depends(get_db),
        ):
            ...
    """

    def __init__(
        self,
        is_negotiable: Annotated[
            Optional[bool],
            Query(alias="isNegotiable", description="Filter by negotiability"),
        ] = None,
        price_type: Annotated[
            Optional[PriceType],
            Query(
                alias="priceType",
                description="Price model: fixed | hourly | daily | negotiable",
            ),
        ] = None,
        min_price: Annotated[
            Optional[Decimal],
            Query(
                alias="minPrice",
                ge=0,
                description="Minimum price amount (inclusive). Skipped for negotiable listings.",
            ),
        ] = None,
        max_price: Annotated[
            Optional[Decimal],
            Query(
                alias="maxPrice",
                ge=0,
                description="Maximum price amount (inclusive). Skipped for negotiable listings.",
            ),
        ] = None,
        search: Annotated[
            Optional[str],
            Query(
                max_length=100,
                description="Case-insensitive keyword search in title or description",
            ),
        ] = None,
        category_id: Annotated[
            Optional[int],
            Query(alias="categoryId", gt=0, description="Filter by category ID"),
        ] = None,
        city_slug: Annotated[
            Optional[str],
            Query(alias="citySlug", description="Filter by city slug"),
        ] = None,
        category_slug: Annotated[
            Optional[str],
            Query(alias="categorySlug", description="Filter by category slug"),
        ] = None,
        top_selling: Annotated[
            bool,
            Query(alias="topSelling", description="Sort by top selling sellers"),
        ] = False,
        top_rating: Annotated[
            bool,
            Query(alias="topRating", description="Sort by top rated sellers"),
        ] = False,
        page: Annotated[
            int,
            Query(ge=1, description="Page number (1-based)"),
        ] = 1,
        page_size: Annotated[
            int,
            Query(alias="pageSize", ge=1, le=100, description="Results per page"),
        ] = 20,
    ) -> None:
        self.is_negotiable = is_negotiable
        self.price_type = price_type
        self.min_price = min_price
        self.max_price = max_price
        self.search = search
        self.category_id = category_id
        self.city_slug = city_slug
        self.category_slug = category_slug
        self.top_selling = top_selling
        self.top_rating = top_rating
        self.page = page
        self.page_size = page_size


# ---------------------------------------------------------------------------
# Nearby search query params schema (kept for internal use / documentation)
# ---------------------------------------------------------------------------
class NearbySearchParams(BaseModel):
    """Query parameters for the nearby services endpoint."""
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    radius_km: float = Field(default=10.0, ge=0.1, le=100.0)
    category_id: Optional[int] = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


# ---------------------------------------------------------------------------
# Nearby response — custom slimmed-down card for UI
# ---------------------------------------------------------------------------
class ServiceListingNearbyResponse(ServiceListingCore):
    """Extended response for nearby search — highly optimized for UI cards."""
    distance_km: Optional[float] = None
    cityName: Optional[str] = None
    categoryName: str
    imageUrl: Optional[str] = None
    seller: Optional[SellerProfileSchema] = None

    @model_validator(mode="before")
    @classmethod
    def map_relations(cls, data: any) -> any:
        """
        Pull cityName, categoryName, and primary imageUrl from relations.
        Handles both SQLAlchemy objects and dictionaries.
        """
        # If it's a dict
        if isinstance(data, dict):
            # Map City/Category Names
            city = data.get("city")
            if city and hasattr(city, "name"):
                data["cityName"] = city.name
            
            category = data.get("category")
            if category and hasattr(category, "name"):
                data["categoryName"] = category.name

            # Map Primary Image URL
            media = data.get("media", [])
            if media:
                # media is likely a list of ListingMedia objects or dicts
                # Sort by sortOrder then take the first
                try:
                    sorted_media = sorted(media, key=lambda x: getattr(x, "sortOrder", 0) if hasattr(x, "sortOrder") else x.get("sortOrder", 0))
                    first_item = sorted_media[0]
                    data["imageUrl"] = getattr(first_item, "imageUrl", None) if hasattr(first_item, "imageUrl") else first_item.get("imageUrl")
                except Exception:
                    pass
            
            return data

        # If it's an object (SQLAlchemy model)
        obj_dict = {k: v for k, v in data.__dict__.items() if not k.startswith('_')}
        
        # City/Category
        obj_dict["cityName"] = data.city.name if hasattr(data, "city") and data.city else None
        obj_dict["categoryName"] = data.category.name if hasattr(data, "category") and data.category else "Other"
        
        # Primary Image
        if hasattr(data, "media") and data.media:
            # Relationship is sorted by sortOrder in the model definition already
            obj_dict["imageUrl"] = data.media[0].imageUrl
            
        obj_dict["seller"] = getattr(data, "seller", None)
        return obj_dict

    @field_validator("seller", mode="before")
    @classmethod
    def map_seller_profile(cls, v: object) -> Optional[dict]:
        """Maps SQL User model → SellerProfileSchema."""
        if isinstance(v, (dict, SellerProfileSchema)):
            return v
        if v and hasattr(v, "profile") and v.profile:
            return {
                "name": v.profile.name,
                "photoUrl": v.profile.photoUrl,
                "sellerRatingAvg": v.profile.sellerRatingAvg
            }
        return None


class ServiceListingNearbyListResponse(BaseModel):
    """Paginated nearby results wrapper."""
    total: int
    page: int
    pageSize: int
    radius_km: float
    results: list[ServiceListingNearbyResponse]


# ---------------------------------------------------------------------------
# Paginated list response helpers
# ---------------------------------------------------------------------------
class ServiceListingListResponse(BaseModel):
    """Wrapper for paginated public results."""
    total: int
    page: int
    pageSize: int
    results: list[ServiceListingResponse]


class ServiceListingMeListResponse(BaseModel):
    """Wrapper for paginated seller-specific results."""
    total: int
    page: int
    pageSize: int
    results: list[ServiceListingMeResponse]