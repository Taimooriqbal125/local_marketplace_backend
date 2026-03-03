"""Pydantic schemas for ServiceListing resource."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional
from uuid import UUID

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
# Response
# ---------------------------------------------------------------------------
class ServiceListingResponse(BaseModel):
    """
    Full listing object returned by the API.
    Deserializes PostGIS Geography → clean {latitude, longitude} object.
    """

    id: UUID
    sellerId: UUID
    categoryId: int
    cityId: Optional[UUID] = None
    title: str
    description: Optional[str] = None
    priceType: PriceType
    priceAmount: Optional[Decimal] = None
    isNegotiable: bool
    serviceLocation: str
    serviceRadiusKm: float

    # ✅ Deserialized from PostGIS WKBElement → clean lat/lon for the client
    service_location_point: Optional[ServiceLocationPoint] = None

    status: ListingStatus
    createdAt: datetime
    updatedAt: datetime

    model_config = dict(from_attributes=True)

    @field_validator("service_location_point", mode="before")
    @classmethod
    def deserialize_geo(cls, v: object) -> Optional[ServiceLocationPoint]:
        """
        Convert PostGIS WKBElement → ServiceLocationPoint.
        Same pattern as ProfileResponse.validate_geo().
        """
        if v is None:
            return None
        # Already a dict or ServiceLocationPoint (e.g. in tests)
        if isinstance(v, dict):
            return ServiceLocationPoint(**v)
        if isinstance(v, ServiceLocationPoint):
            return v
        # PostGIS WKBElement from the DB
        try:
            shape = to_shape(v)
            return ServiceLocationPoint(latitude=shape.y, longitude=shape.x)
        except Exception:
            return None


# ---------------------------------------------------------------------------
# Nearby search query params schema
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
# Nearby response — extends standard response with distance info
# ---------------------------------------------------------------------------
class ServiceListingNearbyResponse(ServiceListingResponse):
    """Extended response for nearby search — includes distance from user."""
    distance_km: Optional[float] = None


class ServiceListingNearbyListResponse(BaseModel):
    """Paginated nearby results wrapper."""
    total: int
    page: int
    pageSize: int
    radius_km: float
    results: list[ServiceListingNearbyResponse]


# ---------------------------------------------------------------------------
# Paginated list response helper
# ---------------------------------------------------------------------------
class ServiceListingListResponse(BaseModel):
    """Wrapper for paginated listing results."""
    total: int
    page: int
    pageSize: int
    results: list[ServiceListingResponse]