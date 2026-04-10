# Code Citations

## License: GPL-3.0
https://github.com/jeffpar/pcjs.v1/blob/52b8cc49176a90335acdbb3ddd6b632754c2b410/pubs/pc/reference/microsoft/mspl13/c/cadvprg/README.md

```
Now I have the full picture. Here's exactly what needs to change and why:

---

## What Needs to Change

| File | Change |
|---|---|
| `models/service_listing.py` | Replace `serviceLatitude` + `serviceLongitude` Float columns → `service_location Geography(POINT, 4326)` + GIST index |
| `schemas/services_listing.py` | Replace `serviceLatitude/serviceLongitude` float fields → `ServiceLocationPoint` nested schema with `WKTElement` conversion |
| `repositories/service_listing_repo.py` | Add `get_nearby()` proximity query using `ST_DWithin` + `ST_Distance`, fix `create()` to write `WKTElement` |
| `services/service_listing_service.py` | Add `get_nearby_listings()` method |
| `routes/service_listing_routes.py` | Add `GET /services/nearby` endpoint |

---

**Let's implement all 5 files now:**

````python
# filepath: d:\Backends\FastAPI\local_marketplace_backend\app\models\service_listing.py
import uuid
from typing import Optional

from geoalchemy2 import Geography
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base_class import Base


class ServiceListing(Base):
    """
    Represents a service offered by a seller on the local marketplace.

    Relationships:
        - seller   → User     (many-to-one)
        - city     → City     (many-to-one, MVP)
        - category → Category (many-to-one)
    """

    __tablename__ = "service_listings"

    __table_args__ = (
        UniqueConstraint(
            "title", "description", name="uq_service_listings_title_description"
        ),
        # ✅ GIST spatial index — powers ST_DWithin / ST_Distance queries
        Index(
            "idx_service_listings_location_gist",
            "service_location",
            postgresql_using="gist",
        ),
    )

    # ── Primary Key ──────────────────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )

    # ── Foreign Keys ─────────────────────────────────────────────────────────
    sellerId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    cityId: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cities.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    categoryId: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # ── Core Fields ──────────────────────────────────────────────────────────
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # ── Pricing ──────────────────────────────────────────────────────────────
    priceType: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'fixed'"),
    )

    priceAmount: Mapped[Optional[float]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )

    isNegotiable: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )

    # ── Location ─────────────────────────────────────────────────────────────

    # Human-readable address / area label
    serviceLocation: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    # ✅ How far (km) the seller is willing to serve from their point
    serviceRadiusKm: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    # ✅ Native PostGIS Geography point — replaces serviceLatitude + serviceLongitude
    # SRID 4326 = WGS84 (same coordinate system as every mobile GPS)
    service_location: Mapped[Optional[object]] = mapped_column(
        Geography(geometry_type="POINT", srid=4326),
        nullable=True,
    )

    # ── Moderation / Lifecycle ────────────────────────────────────────────────
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'draft'"),
        index=True,
    )

    # ── Timestamps ────────────────────────────────────────────────────────────
    createdAt: Mapped[str] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updatedAt: Mapped[str] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    seller: Mapped["User"] = relationship(
        "User",
        back_populates="service_listings",
        lazy="joined",
    )

    city: Mapped[Optional["City"]] = relationship(
        "City",
        lazy="joined",
    )

    category: Mapped["Category"] = relationship(
        "Category",
        lazy="joined",
    )

    media: Mapped[list["ListingMedia"]] = relationship(
        "ListingMedia",
        back_populates="listing",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="ListingMedia.sortOrder",
    )

    orders: Mapped[list["Order"]] = relationship(
        "Order",
        back_populates="listing",
        cascade="all, delete-orphan",
    )
````

````python
# filepath: d:\Backends\FastAPI\local_marketplace_backend\app\schemas\services_listing.py
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

    # ✅ Structured lat/lon — replaces flat serviceLatitude / serviceLongitude
    service_location_point: Optional[ServiceLocationPoint] = Field(
        default=None,
        description="Precise GPS coordinates of the service location",
    )

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
````

````python
# filepath: d:\Backends\FastAPI\local_marketplace_backend\app\repositories\service_listing_repo.py
"""
ServiceListing Repository — the *only* layer that talks to the DB for listings.
"""

from __future__ import annotations

import uuid
from typing import Optional

from geoalchemy2.elements import WKTElement
from geoalchemy2.functions import ST_DWithin, ST_Distance
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.service_listing import ServiceListing
from app.schemas.services_listing import ServiceListingCreate, ServiceListingUpdate


def _to_wkt(lat: float, lon: float) -> WKTElement:
    """Convert lat/lon → PostGIS WKTElement. Note: PostGIS is (lon lat) order."""
    return WKTElement(f"POINT({lon} {lat})", srid=4326)


class ServiceListingRepository:
    """Class-based repository: instantiated once per request with a DB session."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ── Single-record Lookups ────────────────────────────────────────────────

    def get(self, listing_id: uuid.UUID) -> Optional[ServiceListing]:
        return (
            self.db.query(ServiceListing)
            .filter(ServiceListing.id == listing_id)
            .first()
        )

    def get_by_seller_and_id(
        self, listing_id: uuid.UUID, seller_id: uuid.UUID
    ) -> Optional[ServiceListing]:
        return (
            self.db.query(ServiceListing)
            .filter(
                ServiceListing.id == listing_id,
                ServiceListing.sellerId == seller_id,
            )
            .first()
        )

    # ── Collection Queries ───────────────────────────────────────────────────

    def get_all(self, skip: int = 0, limit: int = 20) -> list[ServiceListing]:
        return (
            self.db.query(ServiceListing)
            .order_by(ServiceListing.createdAt.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_seller(
        self, seller_id: uuid.UUID, skip: int = 0, limit: int = 20
    ) -> list[ServiceListing]:
        return (
            self.db.query(ServiceListing)
            .filter(ServiceListing.sellerId == seller_id)
            .order_by(ServiceListing.createdAt.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_category(
        self, category_id: int, skip: int = 0, limit: int = 20
    ) -> list[ServiceListing]:
        return (
            self.db.query(ServiceListing)
            .filter(
                ServiceListing.categoryId == category_id,
                ServiceListing.status == "active",
            )
            .order_by(ServiceListing.createdAt.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_city(
        self, city_id: uuid.UUID, skip: int = 0, limit: int = 20
    ) -> list[ServiceListing]:
        return (
            self.db.query(ServiceListing)
            .filter(
                ServiceListing.cityId == city_id,
                ServiceListing.status == "active",
            )
            .order_by(ServiceListing.createdAt.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_filtered(
        self,
        *,
        status: Optional[str] = None,
        category_id: Optional[int] = None,
        city_id: Optional[uuid.UUID] = None,
        seller_id: Optional[uuid.UUID] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[ServiceListing], int]:
        query = self.db.query(ServiceListing)

        if status is not None:
            query = query.filter(ServiceListing.status == status)
        if category_id is not None:
            query = query.filter(ServiceListing.categoryId == category_id)
        if city_id is not None:
            query = query.filter(ServiceListing.cityId == city_id)
        if seller_id is not None:
            query = query.filter(ServiceListing.sellerId == seller_id)

        total = query.count()
        results = (
            query.order_by(ServiceListing.createdAt.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return results, total

    # ── ✅ Proximity Search ───────────────────────────────────────────────────

    def get_nearby(
        self,
        *,
        latitude: float,
        longitude: float,
        radius_km: float,
        category_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[tuple[ServiceListing, float]], int]:
        """
        Find active listings where the customer's location falls within
        the service's coverage radius.

        Logic:
            ST_DWithin(service_location, customer_point, serviceRadiusKm * 1000)

        Returns: list of (ServiceListing, distance_km) tuples, sorted closest first.
        """
        customer_point = _to_wkt(latitude, longitude)

        # Distance in meters from customer to service location point
        distance_m = ST_Distance(
            ServiceListing.service_location,
            customer_point,
        )

        query = (
            self.db.query(
                ServiceListing,
                # Convert meters → km, round to 2 decimal places
                func.round(
                    func.cast(distance_m, type_=None) / 1000, 2
                ).label("distance_km"),
            )
            .filter(
                # Only active listings
                ServiceListing.status == "active",
                # Only listings that HAVE a location point set
                ServiceListing.service_location.isnot(None),
                # ✅ Core proximity check:
                # Customer must be within the SERVICE's defined coverage radius
                ST_DWithin(
                    ServiceListing.service_location,
                    customer_point,
                    ServiceListing.serviceRadiusKm * 1000,  # km → meters
                ),
            )
        )

        if category_id is not None:
            query = query.filter(ServiceListing.categoryId == category_id)

        total = query.count()
        results = (
            query.order_by("distance_km")  # closest first
            .offset(skip)
            .limit(limit)
            .all()
        )
        return results, total

    # ── Write Operations ─────────────────────────────────────────────────────

    def create(
        self,
        obj_in: ServiceListingCreate,
        seller_id: uuid.UUID,
    ) -> ServiceListing:
        """
        Insert a new listing.
        Converts service_location_point → WKTElement for PostGIS storage.
        """
        # ✅ Convert lat/lon → PostGIS WKTElement if provided
        geo_point = None
        if obj_in.service_location_point is not None:
            geo_point = _to_wkt(
                obj_in.service_location_point.latitude,
                obj_in.service_location_point.longitude,
            )

        db_obj = ServiceListing(
            sellerId=seller_id,
            cityId=obj_in.cityId,
            categoryId=obj_in.categoryId,
            title=obj_in.title,
            description=obj_in.description,
            priceType=obj_in.priceType,
            priceAmount=obj_in.priceAmount,
            isNegotiable=obj_in.isNegotiable,
            serviceLocation=obj_in.serviceLocation,
            serviceRadiusKm=obj_in.serviceRadiusKm,
            service_location=geo_point,  # ✅ PostGIS Geography
            status=obj_in.status,
        )
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def update(
        self,
        db_obj: ServiceListing,
        obj_in: ServiceListingUpdate,
    ) -> ServiceListing:
        """
        Apply partial updates. Handles service_location_point → WKTElement conversion.
        """
        update_data = obj_in.model_dump(exclude_unset=True)

        # ✅ Handle geography field separately — needs WKTElement conversion
        location_point = update_data.pop("service_location_point", None)
        if location_point is not None:
            db_obj.service_location = _to_wkt(
                location_point["latitude"],
                location_point["longitude"],
            )

        for field, value in update_data.items():
            setattr(db_obj, field, value)

        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def delete(self, db_obj: ServiceListing) -> None:
        self.db.delete(db_obj)
        self.db.commit()

    # ── Count Helpers ────────────────────────────────────────────────────────

    def count_by_seller(self, seller_id: uuid.UUID) -> int:
        return (
            self.db.query(ServiceListing)
            .filter(ServiceListing.sellerId == seller_id)
            .count()
        )

    def get_by_title_and_description(
        self, title: str, description: Optional[str]
    ) -> Optional[ServiceListing]:
        return (
            self.db.query(ServiceListing)
            .filter(
                ServiceListing.title == title,
                ServiceListing.description == description,
            )
            .first()
        )
````

````python
# filepath: d:\Backends\FastAPI\local_marketplace_backend\app\services\service_listing_service.py
"""
ServiceListing Service — business logic layer.
"""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.repositories.service_listing_repo import ServiceListingRepository
from app.schemas.services_listing import (
    ServiceListingCreate,
    ServiceListingListResponse,
    ServiceListingNearbyListResponse,
    ServiceListingNearbyResponse,
    ServiceListingResponse,
    ServiceListingUpdate,
)


# ---------------------------------------------------------------------------
# Domain Exceptions
# ---------------------------------------------------------------------------

class ListingNotFoundError(HTTPException):
    def __init__(self, listing_id: uuid.UUID) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service listing '{listing_id}' not found.",
        )


class ListingForbiddenError(HTTPException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to modify this listing.",
        )


class DuplicateListingError(HTTPException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail="A service listing with this title and description already exists.",
        )


# ---------------------------------------------------------------------------
# Service Class
# ---------------------------------------------------------------------------

class ServiceListingService:

    def __init__(self, db: Session) -> None:
        self.repo = ServiceListingRepository(db)

    # ── Read Operations ──────────────────────────────────────────────────────

    def get_listing(self, listing_id: uuid.UUID) -> ServiceListingResponse:
        listing
```


## License: GPL-3.0
https://github.com/jeffpar/pcjs.v1/blob/52b8cc49176a90335acdbb3ddd6b632754c2b410/pubs/pc/reference/microsoft/mspl13/c/cadvprg/README.md

```
Now I have the full picture. Here's exactly what needs to change and why:

---

## What Needs to Change

| File | Change |
|---|---|
| `models/service_listing.py` | Replace `serviceLatitude` + `serviceLongitude` Float columns → `service_location Geography(POINT, 4326)` + GIST index |
| `schemas/services_listing.py` | Replace `serviceLatitude/serviceLongitude` float fields → `ServiceLocationPoint` nested schema with `WKTElement` conversion |
| `repositories/service_listing_repo.py` | Add `get_nearby()` proximity query using `ST_DWithin` + `ST_Distance`, fix `create()` to write `WKTElement` |
| `services/service_listing_service.py` | Add `get_nearby_listings()` method |
| `routes/service_listing_routes.py` | Add `GET /services/nearby` endpoint |

---

**Let's implement all 5 files now:**

````python
# filepath: d:\Backends\FastAPI\local_marketplace_backend\app\models\service_listing.py
import uuid
from typing import Optional

from geoalchemy2 import Geography
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base_class import Base


class ServiceListing(Base):
    """
    Represents a service offered by a seller on the local marketplace.

    Relationships:
        - seller   → User     (many-to-one)
        - city     → City     (many-to-one, MVP)
        - category → Category (many-to-one)
    """

    __tablename__ = "service_listings"

    __table_args__ = (
        UniqueConstraint(
            "title", "description", name="uq_service_listings_title_description"
        ),
        # ✅ GIST spatial index — powers ST_DWithin / ST_Distance queries
        Index(
            "idx_service_listings_location_gist",
            "service_location",
            postgresql_using="gist",
        ),
    )

    # ── Primary Key ──────────────────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )

    # ── Foreign Keys ─────────────────────────────────────────────────────────
    sellerId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    cityId: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cities.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    categoryId: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # ── Core Fields ──────────────────────────────────────────────────────────
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # ── Pricing ──────────────────────────────────────────────────────────────
    priceType: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'fixed'"),
    )

    priceAmount: Mapped[Optional[float]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )

    isNegotiable: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )

    # ── Location ─────────────────────────────────────────────────────────────

    # Human-readable address / area label
    serviceLocation: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    # ✅ How far (km) the seller is willing to serve from their point
    serviceRadiusKm: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    # ✅ Native PostGIS Geography point — replaces serviceLatitude + serviceLongitude
    # SRID 4326 = WGS84 (same coordinate system as every mobile GPS)
    service_location: Mapped[Optional[object]] = mapped_column(
        Geography(geometry_type="POINT", srid=4326),
        nullable=True,
    )

    # ── Moderation / Lifecycle ────────────────────────────────────────────────
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'draft'"),
        index=True,
    )

    # ── Timestamps ────────────────────────────────────────────────────────────
    createdAt: Mapped[str] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updatedAt: Mapped[str] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    seller: Mapped["User"] = relationship(
        "User",
        back_populates="service_listings",
        lazy="joined",
    )

    city: Mapped[Optional["City"]] = relationship(
        "City",
        lazy="joined",
    )

    category: Mapped["Category"] = relationship(
        "Category",
        lazy="joined",
    )

    media: Mapped[list["ListingMedia"]] = relationship(
        "ListingMedia",
        back_populates="listing",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="ListingMedia.sortOrder",
    )

    orders: Mapped[list["Order"]] = relationship(
        "Order",
        back_populates="listing",
        cascade="all, delete-orphan",
    )
````

````python
# filepath: d:\Backends\FastAPI\local_marketplace_backend\app\schemas\services_listing.py
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

    # ✅ Structured lat/lon — replaces flat serviceLatitude / serviceLongitude
    service_location_point: Optional[ServiceLocationPoint] = Field(
        default=None,
        description="Precise GPS coordinates of the service location",
    )

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
````

````python
# filepath: d:\Backends\FastAPI\local_marketplace_backend\app\repositories\service_listing_repo.py
"""
ServiceListing Repository — the *only* layer that talks to the DB for listings.
"""

from __future__ import annotations

import uuid
from typing import Optional

from geoalchemy2.elements import WKTElement
from geoalchemy2.functions import ST_DWithin, ST_Distance
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.service_listing import ServiceListing
from app.schemas.services_listing import ServiceListingCreate, ServiceListingUpdate


def _to_wkt(lat: float, lon: float) -> WKTElement:
    """Convert lat/lon → PostGIS WKTElement. Note: PostGIS is (lon lat) order."""
    return WKTElement(f"POINT({lon} {lat})", srid=4326)


class ServiceListingRepository:
    """Class-based repository: instantiated once per request with a DB session."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ── Single-record Lookups ────────────────────────────────────────────────

    def get(self, listing_id: uuid.UUID) -> Optional[ServiceListing]:
        return (
            self.db.query(ServiceListing)
            .filter(ServiceListing.id == listing_id)
            .first()
        )

    def get_by_seller_and_id(
        self, listing_id: uuid.UUID, seller_id: uuid.UUID
    ) -> Optional[ServiceListing]:
        return (
            self.db.query(ServiceListing)
            .filter(
                ServiceListing.id == listing_id,
                ServiceListing.sellerId == seller_id,
            )
            .first()
        )

    # ── Collection Queries ───────────────────────────────────────────────────

    def get_all(self, skip: int = 0, limit: int = 20) -> list[ServiceListing]:
        return (
            self.db.query(ServiceListing)
            .order_by(ServiceListing.createdAt.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_seller(
        self, seller_id: uuid.UUID, skip: int = 0, limit: int = 20
    ) -> list[ServiceListing]:
        return (
            self.db.query(ServiceListing)
            .filter(ServiceListing.sellerId == seller_id)
            .order_by(ServiceListing.createdAt.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_category(
        self, category_id: int, skip: int = 0, limit: int = 20
    ) -> list[ServiceListing]:
        return (
            self.db.query(ServiceListing)
            .filter(
                ServiceListing.categoryId == category_id,
                ServiceListing.status == "active",
            )
            .order_by(ServiceListing.createdAt.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_city(
        self, city_id: uuid.UUID, skip: int = 0, limit: int = 20
    ) -> list[ServiceListing]:
        return (
            self.db.query(ServiceListing)
            .filter(
                ServiceListing.cityId == city_id,
                ServiceListing.status == "active",
            )
            .order_by(ServiceListing.createdAt.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_filtered(
        self,
        *,
        status: Optional[str] = None,
        category_id: Optional[int] = None,
        city_id: Optional[uuid.UUID] = None,
        seller_id: Optional[uuid.UUID] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[ServiceListing], int]:
        query = self.db.query(ServiceListing)

        if status is not None:
            query = query.filter(ServiceListing.status == status)
        if category_id is not None:
            query = query.filter(ServiceListing.categoryId == category_id)
        if city_id is not None:
            query = query.filter(ServiceListing.cityId == city_id)
        if seller_id is not None:
            query = query.filter(ServiceListing.sellerId == seller_id)

        total = query.count()
        results = (
            query.order_by(ServiceListing.createdAt.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return results, total

    # ── ✅ Proximity Search ───────────────────────────────────────────────────

    def get_nearby(
        self,
        *,
        latitude: float,
        longitude: float,
        radius_km: float,
        category_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[tuple[ServiceListing, float]], int]:
        """
        Find active listings where the customer's location falls within
        the service's coverage radius.

        Logic:
            ST_DWithin(service_location, customer_point, serviceRadiusKm * 1000)

        Returns: list of (ServiceListing, distance_km) tuples, sorted closest first.
        """
        customer_point = _to_wkt(latitude, longitude)

        # Distance in meters from customer to service location point
        distance_m = ST_Distance(
            ServiceListing.service_location,
            customer_point,
        )

        query = (
            self.db.query(
                ServiceListing,
                # Convert meters → km, round to 2 decimal places
                func.round(
                    func.cast(distance_m, type_=None) / 1000, 2
                ).label("distance_km"),
            )
            .filter(
                # Only active listings
                ServiceListing.status == "active",
                # Only listings that HAVE a location point set
                ServiceListing.service_location.isnot(None),
                # ✅ Core proximity check:
                # Customer must be within the SERVICE's defined coverage radius
                ST_DWithin(
                    ServiceListing.service_location,
                    customer_point,
                    ServiceListing.serviceRadiusKm * 1000,  # km → meters
                ),
            )
        )

        if category_id is not None:
            query = query.filter(ServiceListing.categoryId == category_id)

        total = query.count()
        results = (
            query.order_by("distance_km")  # closest first
            .offset(skip)
            .limit(limit)
            .all()
        )
        return results, total

    # ── Write Operations ─────────────────────────────────────────────────────

    def create(
        self,
        obj_in: ServiceListingCreate,
        seller_id: uuid.UUID,
    ) -> ServiceListing:
        """
        Insert a new listing.
        Converts service_location_point → WKTElement for PostGIS storage.
        """
        # ✅ Convert lat/lon → PostGIS WKTElement if provided
        geo_point = None
        if obj_in.service_location_point is not None:
            geo_point = _to_wkt(
                obj_in.service_location_point.latitude,
                obj_in.service_location_point.longitude,
            )

        db_obj = ServiceListing(
            sellerId=seller_id,
            cityId=obj_in.cityId,
            categoryId=obj_in.categoryId,
            title=obj_in.title,
            description=obj_in.description,
            priceType=obj_in.priceType,
            priceAmount=obj_in.priceAmount,
            isNegotiable=obj_in.isNegotiable,
            serviceLocation=obj_in.serviceLocation,
            serviceRadiusKm=obj_in.serviceRadiusKm,
            service_location=geo_point,  # ✅ PostGIS Geography
            status=obj_in.status,
        )
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def update(
        self,
        db_obj: ServiceListing,
        obj_in: ServiceListingUpdate,
    ) -> ServiceListing:
        """
        Apply partial updates. Handles service_location_point → WKTElement conversion.
        """
        update_data = obj_in.model_dump(exclude_unset=True)

        # ✅ Handle geography field separately — needs WKTElement conversion
        location_point = update_data.pop("service_location_point", None)
        if location_point is not None:
            db_obj.service_location = _to_wkt(
                location_point["latitude"],
                location_point["longitude"],
            )

        for field, value in update_data.items():
            setattr(db_obj, field, value)

        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def delete(self, db_obj: ServiceListing) -> None:
        self.db.delete(db_obj)
        self.db.commit()

    # ── Count Helpers ────────────────────────────────────────────────────────

    def count_by_seller(self, seller_id: uuid.UUID) -> int:
        return (
            self.db.query(ServiceListing)
            .filter(ServiceListing.sellerId == seller_id)
            .count()
        )

    def get_by_title_and_description(
        self, title: str, description: Optional[str]
    ) -> Optional[ServiceListing]:
        return (
            self.db.query(ServiceListing)
            .filter(
                ServiceListing.title == title,
                ServiceListing.description == description,
            )
            .first()
        )
````

````python
# filepath: d:\Backends\FastAPI\local_marketplace_backend\app\services\service_listing_service.py
"""
ServiceListing Service — business logic layer.
"""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.repositories.service_listing_repo import ServiceListingRepository
from app.schemas.services_listing import (
    ServiceListingCreate,
    ServiceListingListResponse,
    ServiceListingNearbyListResponse,
    ServiceListingNearbyResponse,
    ServiceListingResponse,
    ServiceListingUpdate,
)


# ---------------------------------------------------------------------------
# Domain Exceptions
# ---------------------------------------------------------------------------

class ListingNotFoundError(HTTPException):
    def __init__(self, listing_id: uuid.UUID) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service listing '{listing_id}' not found.",
        )


class ListingForbiddenError(HTTPException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to modify this listing.",
        )


class DuplicateListingError(HTTPException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail="A service listing with this title and description already exists.",
        )


# ---------------------------------------------------------------------------
# Service Class
# ---------------------------------------------------------------------------

class ServiceListingService:

    def __init__(self, db: Session) -> None:
        self.repo = ServiceListingRepository(db)

    # ── Read Operations ──────────────────────────────────────────────────────

    def get_listing(self, listing_id: uuid.UUID) -> ServiceListingResponse:
        listing
```


## License: GPL-3.0
https://github.com/jeffpar/pcjs.v1/blob/52b8cc49176a90335acdbb3ddd6b632754c2b410/pubs/pc/reference/microsoft/mspl13/c/cadvprg/README.md

```
Now I have the full picture. Here's exactly what needs to change and why:

---

## What Needs to Change

| File | Change |
|---|---|
| `models/service_listing.py` | Replace `serviceLatitude` + `serviceLongitude` Float columns → `service_location Geography(POINT, 4326)` + GIST index |
| `schemas/services_listing.py` | Replace `serviceLatitude/serviceLongitude` float fields → `ServiceLocationPoint` nested schema with `WKTElement` conversion |
| `repositories/service_listing_repo.py` | Add `get_nearby()` proximity query using `ST_DWithin` + `ST_Distance`, fix `create()` to write `WKTElement` |
| `services/service_listing_service.py` | Add `get_nearby_listings()` method |
| `routes/service_listing_routes.py` | Add `GET /services/nearby` endpoint |

---

**Let's implement all 5 files now:**

````python
# filepath: d:\Backends\FastAPI\local_marketplace_backend\app\models\service_listing.py
import uuid
from typing import Optional

from geoalchemy2 import Geography
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base_class import Base


class ServiceListing(Base):
    """
    Represents a service offered by a seller on the local marketplace.

    Relationships:
        - seller   → User     (many-to-one)
        - city     → City     (many-to-one, MVP)
        - category → Category (many-to-one)
    """

    __tablename__ = "service_listings"

    __table_args__ = (
        UniqueConstraint(
            "title", "description", name="uq_service_listings_title_description"
        ),
        # ✅ GIST spatial index — powers ST_DWithin / ST_Distance queries
        Index(
            "idx_service_listings_location_gist",
            "service_location",
            postgresql_using="gist",
        ),
    )

    # ── Primary Key ──────────────────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )

    # ── Foreign Keys ─────────────────────────────────────────────────────────
    sellerId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    cityId: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cities.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    categoryId: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # ── Core Fields ──────────────────────────────────────────────────────────
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # ── Pricing ──────────────────────────────────────────────────────────────
    priceType: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'fixed'"),
    )

    priceAmount: Mapped[Optional[float]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )

    isNegotiable: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )

    # ── Location ─────────────────────────────────────────────────────────────

    # Human-readable address / area label
    serviceLocation: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    # ✅ How far (km) the seller is willing to serve from their point
    serviceRadiusKm: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    # ✅ Native PostGIS Geography point — replaces serviceLatitude + serviceLongitude
    # SRID 4326 = WGS84 (same coordinate system as every mobile GPS)
    service_location: Mapped[Optional[object]] = mapped_column(
        Geography(geometry_type="POINT", srid=4326),
        nullable=True,
    )

    # ── Moderation / Lifecycle ────────────────────────────────────────────────
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'draft'"),
        index=True,
    )

    # ── Timestamps ────────────────────────────────────────────────────────────
    createdAt: Mapped[str] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updatedAt: Mapped[str] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    seller: Mapped["User"] = relationship(
        "User",
        back_populates="service_listings",
        lazy="joined",
    )

    city: Mapped[Optional["City"]] = relationship(
        "City",
        lazy="joined",
    )

    category: Mapped["Category"] = relationship(
        "Category",
        lazy="joined",
    )

    media: Mapped[list["ListingMedia"]] = relationship(
        "ListingMedia",
        back_populates="listing",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="ListingMedia.sortOrder",
    )

    orders: Mapped[list["Order"]] = relationship(
        "Order",
        back_populates="listing",
        cascade="all, delete-orphan",
    )
````

````python
# filepath: d:\Backends\FastAPI\local_marketplace_backend\app\schemas\services_listing.py
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

    # ✅ Structured lat/lon — replaces flat serviceLatitude / serviceLongitude
    service_location_point: Optional[ServiceLocationPoint] = Field(
        default=None,
        description="Precise GPS coordinates of the service location",
    )

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
````

````python
# filepath: d:\Backends\FastAPI\local_marketplace_backend\app\repositories\service_listing_repo.py
"""
ServiceListing Repository — the *only* layer that talks to the DB for listings.
"""

from __future__ import annotations

import uuid
from typing import Optional

from geoalchemy2.elements import WKTElement
from geoalchemy2.functions import ST_DWithin, ST_Distance
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.service_listing import ServiceListing
from app.schemas.services_listing import ServiceListingCreate, ServiceListingUpdate


def _to_wkt(lat: float, lon: float) -> WKTElement:
    """Convert lat/lon → PostGIS WKTElement. Note: PostGIS is (lon lat) order."""
    return WKTElement(f"POINT({lon} {lat})", srid=4326)


class ServiceListingRepository:
    """Class-based repository: instantiated once per request with a DB session."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ── Single-record Lookups ────────────────────────────────────────────────

    def get(self, listing_id: uuid.UUID) -> Optional[ServiceListing]:
        return (
            self.db.query(ServiceListing)
            .filter(ServiceListing.id == listing_id)
            .first()
        )

    def get_by_seller_and_id(
        self, listing_id: uuid.UUID, seller_id: uuid.UUID
    ) -> Optional[ServiceListing]:
        return (
            self.db.query(ServiceListing)
            .filter(
                ServiceListing.id == listing_id,
                ServiceListing.sellerId == seller_id,
            )
            .first()
        )

    # ── Collection Queries ───────────────────────────────────────────────────

    def get_all(self, skip: int = 0, limit: int = 20) -> list[ServiceListing]:
        return (
            self.db.query(ServiceListing)
            .order_by(ServiceListing.createdAt.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_seller(
        self, seller_id: uuid.UUID, skip: int = 0, limit: int = 20
    ) -> list[ServiceListing]:
        return (
            self.db.query(ServiceListing)
            .filter(ServiceListing.sellerId == seller_id)
            .order_by(ServiceListing.createdAt.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_category(
        self, category_id: int, skip: int = 0, limit: int = 20
    ) -> list[ServiceListing]:
        return (
            self.db.query(ServiceListing)
            .filter(
                ServiceListing.categoryId == category_id,
                ServiceListing.status == "active",
            )
            .order_by(ServiceListing.createdAt.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_city(
        self, city_id: uuid.UUID, skip: int = 0, limit: int = 20
    ) -> list[ServiceListing]:
        return (
            self.db.query(ServiceListing)
            .filter(
                ServiceListing.cityId == city_id,
                ServiceListing.status == "active",
            )
            .order_by(ServiceListing.createdAt.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_filtered(
        self,
        *,
        status: Optional[str] = None,
        category_id: Optional[int] = None,
        city_id: Optional[uuid.UUID] = None,
        seller_id: Optional[uuid.UUID] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[ServiceListing], int]:
        query = self.db.query(ServiceListing)

        if status is not None:
            query = query.filter(ServiceListing.status == status)
        if category_id is not None:
            query = query.filter(ServiceListing.categoryId == category_id)
        if city_id is not None:
            query = query.filter(ServiceListing.cityId == city_id)
        if seller_id is not None:
            query = query.filter(ServiceListing.sellerId == seller_id)

        total = query.count()
        results = (
            query.order_by(ServiceListing.createdAt.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return results, total

    # ── ✅ Proximity Search ───────────────────────────────────────────────────

    def get_nearby(
        self,
        *,
        latitude: float,
        longitude: float,
        radius_km: float,
        category_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[tuple[ServiceListing, float]], int]:
        """
        Find active listings where the customer's location falls within
        the service's coverage radius.

        Logic:
            ST_DWithin(service_location, customer_point, serviceRadiusKm * 1000)

        Returns: list of (ServiceListing, distance_km) tuples, sorted closest first.
        """
        customer_point = _to_wkt(latitude, longitude)

        # Distance in meters from customer to service location point
        distance_m = ST_Distance(
            ServiceListing.service_location,
            customer_point,
        )

        query = (
            self.db.query(
                ServiceListing,
                # Convert meters → km, round to 2 decimal places
                func.round(
                    func.cast(distance_m, type_=None) / 1000, 2
                ).label("distance_km"),
            )
            .filter(
                # Only active listings
                ServiceListing.status == "active",
                # Only listings that HAVE a location point set
                ServiceListing.service_location.isnot(None),
                # ✅ Core proximity check:
                # Customer must be within the SERVICE's defined coverage radius
                ST_DWithin(
                    ServiceListing.service_location,
                    customer_point,
                    ServiceListing.serviceRadiusKm * 1000,  # km → meters
                ),
            )
        )

        if category_id is not None:
            query = query.filter(ServiceListing.categoryId == category_id)

        total = query.count()
        results = (
            query.order_by("distance_km")  # closest first
            .offset(skip)
            .limit(limit)
            .all()
        )
        return results, total

    # ── Write Operations ─────────────────────────────────────────────────────

    def create(
        self,
        obj_in: ServiceListingCreate,
        seller_id: uuid.UUID,
    ) -> ServiceListing:
        """
        Insert a new listing.
        Converts service_location_point → WKTElement for PostGIS storage.
        """
        # ✅ Convert lat/lon → PostGIS WKTElement if provided
        geo_point = None
        if obj_in.service_location_point is not None:
            geo_point = _to_wkt(
                obj_in.service_location_point.latitude,
                obj_in.service_location_point.longitude,
            )

        db_obj = ServiceListing(
            sellerId=seller_id,
            cityId=obj_in.cityId,
            categoryId=obj_in.categoryId,
            title=obj_in.title,
            description=obj_in.description,
            priceType=obj_in.priceType,
            priceAmount=obj_in.priceAmount,
            isNegotiable=obj_in.isNegotiable,
            serviceLocation=obj_in.serviceLocation,
            serviceRadiusKm=obj_in.serviceRadiusKm,
            service_location=geo_point,  # ✅ PostGIS Geography
            status=obj_in.status,
        )
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def update(
        self,
        db_obj: ServiceListing,
        obj_in: ServiceListingUpdate,
    ) -> ServiceListing:
        """
        Apply partial updates. Handles service_location_point → WKTElement conversion.
        """
        update_data = obj_in.model_dump(exclude_unset=True)

        # ✅ Handle geography field separately — needs WKTElement conversion
        location_point = update_data.pop("service_location_point", None)
        if location_point is not None:
            db_obj.service_location = _to_wkt(
                location_point["latitude"],
                location_point["longitude"],
            )

        for field, value in update_data.items():
            setattr(db_obj, field, value)

        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def delete(self, db_obj: ServiceListing) -> None:
        self.db.delete(db_obj)
        self.db.commit()

    # ── Count Helpers ────────────────────────────────────────────────────────

    def count_by_seller(self, seller_id: uuid.UUID) -> int:
        return (
            self.db.query(ServiceListing)
            .filter(ServiceListing.sellerId == seller_id)
            .count()
        )

    def get_by_title_and_description(
        self, title: str, description: Optional[str]
    ) -> Optional[ServiceListing]:
        return (
            self.db.query(ServiceListing)
            .filter(
                ServiceListing.title == title,
                ServiceListing.description == description,
            )
            .first()
        )
````

````python
# filepath: d:\Backends\FastAPI\local_marketplace_backend\app\services\service_listing_service.py
"""
ServiceListing Service — business logic layer.
"""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.repositories.service_listing_repo import ServiceListingRepository
from app.schemas.services_listing import (
    ServiceListingCreate,
    ServiceListingListResponse,
    ServiceListingNearbyListResponse,
    ServiceListingNearbyResponse,
    ServiceListingResponse,
    ServiceListingUpdate,
)


# ---------------------------------------------------------------------------
# Domain Exceptions
# ---------------------------------------------------------------------------

class ListingNotFoundError(HTTPException):
    def __init__(self, listing_id: uuid.UUID) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service listing '{listing_id}' not found.",
        )


class ListingForbiddenError(HTTPException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to modify this listing.",
        )


class DuplicateListingError(HTTPException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail="A service listing with this title and description already exists.",
        )


# ---------------------------------------------------------------------------
# Service Class
# ---------------------------------------------------------------------------

class ServiceListingService:

    def __init__(self, db: Session) -> None:
        self.repo = ServiceListingRepository(db)

    # ── Read Operations ──────────────────────────────────────────────────────

    def get_listing(self, listing_id: uuid.UUID) -> ServiceListingResponse:
        listing
```

