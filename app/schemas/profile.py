"""Pydantic schemas for Profile resource."""

from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator
from geoalchemy2.elements import WKBElement
from geoalchemy2.shape import to_shape



class LocationPoint(BaseModel):
    """Helper schema for Latitude/Longitude points."""
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)


class ProfileBase(BaseModel):
    """Shared profile fields used in create/update/response schemas."""

    name: str = Field(min_length=1, max_length=100)
    bio: Optional[str] = None
    photoUrl: Optional[str] = Field(default=None, max_length=500)
    cloudinary_public_id: Optional[str] = Field(default=None, max_length=500)
    sellerStatus: Literal["none", "active", "suspended"] = "none"
    sellerCompletedOrdersCount: Optional[int] = 0
    
    # New Location Fields
    last_location_point: Optional[LocationPoint] = None
    last_location_at: Optional[datetime] = None
    last_location_accuracy_m: Optional[int] = Field(default=None, ge=0)
    last_location_source: Optional[str] = Field(default=None, max_length=20)
    default_location_point: Optional[LocationPoint] = None
    location_tracking_enabled: bool = False

    isBanned: bool = False


class ProfileCreate(ProfileBase):
    """Fields required to create a profile."""

    userId: Optional[UUID] = None
    sellerRatingAvg: Decimal = Field(default=Decimal("0.00"), ge=0, le=9.99)
    sellerRatingCount: int = Field(default=0, ge=0)


class ProfileUpdate(BaseModel):
    """Fields that can be updated for a profile (all optional)."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    bio: Optional[str] = None
    photoUrl: Optional[str] = Field(default=None, max_length=500)
    cloudinary_public_id: Optional[str] = Field(default=None, max_length=500)
    sellerStatus: Optional[Literal["none", "active", "suspended"]] = None
    sellerCompletedOrdersCount: Optional[int] = Field(default=None, ge=0)
    
    # New Location Fields
    last_location_point: Optional[LocationPoint] = None
    last_location_accuracy_m: Optional[int] = Field(default=None, ge=0)
    last_location_source: Optional[str] = Field(default=None, max_length=20)
    default_location_point: Optional[LocationPoint] = None
    location_tracking_enabled: Optional[bool] = None

    isBanned: Optional[bool] = None
    sellerRatingAvg: Optional[Decimal] = Field(default=None, ge=0, le=9.99)
    sellerRatingCount: Optional[int] = Field(default=None, ge=0)

class ProfileIdMixin(BaseModel):
    """Mixin to ensure userId is the first field in the schema."""
    userId: UUID


class ProfileResponse(ProfileIdMixin, ProfileBase):
    """Profile object returned by the API."""

    sellerRatingAvg: Decimal
    sellerRatingCount: int
    sellerCompletedOrdersCount: int
    createdAt: datetime
    updatedAt: datetime

    @field_validator("last_location_point", "default_location_point", mode="before")
    @classmethod
    def validate_geo(cls, v):
        """Convert GeoAlchemy2 WKBElement/WKTElement or plain WKT string to LocationPoint."""
        if v is None:
            return None
        
        # Handle binary WKB (PostGIS)
        if isinstance(v, WKBElement):
            try:
                shape = to_shape(v)
                return LocationPoint(latitude=shape.y, longitude=shape.x)
            except Exception:
                return None
        
        # Handle string WKT "POINT(lon lat)" (SQLite/Dev)
        if isinstance(v, str) and v.startswith("POINT"):
            try:
                # Simple extraction from "POINT(lon lat)"
                parts = v.replace("POINT(", "").replace(")", "").split()
                if len(parts) == 2:
                    return LocationPoint(latitude=float(parts[1]), longitude=float(parts[0]))
            except Exception:
                return None

        if isinstance(v, dict):
            return LocationPoint(**v)
        return v

    class Config:
        from_attributes = True


class PrivateProfileResponse(BaseModel):
    """
    Detailed profile response for the authenticated user's own dashboard.
    Includes identity (email) and aggregate metrics (totalServices).
    """

    id: UUID
    name: str
    email: str
    photoUrl: Optional[str] = None
    sellerStatus: str
    sellerCompletedOrdersCount: int
    sellerRatingCount: int
    totalServices: int

    @model_validator(mode="before")
    @classmethod
    def map_user_data(cls, data: any) -> any:
        """
        Map data from User model.
        Expected input: User instance with 'profile' and 'service_listings' loaded.
        """
        # If we already have a dict (e.g. from a test or manual construction)
        if isinstance(data, dict):
            return data

        # Check if we have a User object with a profile
        profile = getattr(data, "profile", None)
        if not profile:
            return data

        # Calculate total services
        service_listings = getattr(data, "service_listings", [])
        total_services = len(service_listings)

        return {
            "id": profile.userId,
            "name": profile.name,
            "email": getattr(data, "email", "Unknown"),
            "photoUrl": profile.photoUrl,
            "sellerStatus": profile.sellerStatus,
            "sellerCompletedOrdersCount": profile.sellerCompletedOrdersCount,
            "sellerRatingCount": profile.sellerRatingCount,
            "totalServices": total_services,
        }

    class Config:
        from_attributes = True


class ProfilePublicResponse(BaseModel):
    """
    Publicly accessible profile summary, primarily for admin listing.
    Includes identity and status.
    """

    id: UUID
    userName: str
    image: Optional[str] = None
    status: str
    email: str

    @model_validator(mode="before")
    @classmethod
    def map_profile_data(cls, data: any) -> any:
        """Map fields from Profile and User models."""
        if isinstance(data, dict):
            return data

        # Mapping for the public list
        return {
            "id": data.userId,
            "userName": data.name,
            "image": data.photoUrl,
            "status": data.sellerStatus,
            "email": data.user.email if (hasattr(data, "user") and data.user) else "Unknown",
        }

    class Config:
        from_attributes = True


class PublicProfileDetailResponse(BaseModel):
    """
    Enhanced public profile detail response.
    Includes contact info and service counts.
    """

    id: UUID
    name: str
    image: Optional[str] = None
    completedordercount: int
    avgRating: Decimal
    createdat: datetime
    phone: Optional[str] = None
    email: str
    totalService: int

    @model_validator(mode="before")
    @classmethod
    def map_profile_detail(cls, data: any) -> any:
        """Map fields from Profile and joined User/Services relations."""
        if isinstance(data, dict):
            return data

        user = getattr(data, "user", None)
        service_listings = getattr(user, "service_listings", []) if user else []

        return {
            "id": data.userId,
            "name": data.name,
            "image": data.photoUrl,
            "completedordercount": data.sellerCompletedOrdersCount,
            "avgRating": data.sellerRatingAvg,
            "createdat": data.createdAt,
            "phone": user.phone if user else None,
            "email": user.email if user else "Unknown",
            "totalService": len(service_listings),
        }

    class Config:
        from_attributes = True
