"""Pydantic schemas for Profile resource."""

from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional
from uuid import UUID

from geoalchemy2.elements import WKBElement
from geoalchemy2.shape import to_shape
from pydantic import Field, field_validator, model_validator

from .base import BaseSchema


class LocationPoint(BaseSchema):
    """
    Helper schema for Latitude/Longitude points.
    Used for both input and output of geographic data.
    """
    latitude: float = Field(..., ge=-90, le=90, description="GPS Latitude (-90 to 90)")
    longitude: float = Field(..., ge=-180, le=180, description="GPS Longitude (-180 to 180)")


class ProfileBase(BaseSchema):
    """
    Shared profile fields used across create, update, and response schemas.
    """
    name: str = Field(..., min_length=1, max_length=100, description="User's full name or display name")
    bio: Optional[str] = Field(default=None, max_length=1000, description="Short biography of the user")
    photo_url: Optional[str] = Field(default=None, max_length=500, description="URL of the profile photo")
    cloudinary_public_id: Optional[str] = Field(default=None, max_length=500, description="ID for Cloudinary storage")
    seller_status: Literal["none", "active", "suspended"] = Field(default="active", description="Current status of the seller")
    seller_completed_orders_count: int = Field(default=0, ge=0, description="Total number of successfully completed orders")
    
    # Location tracking attributes
    last_location_point: Optional[LocationPoint] = Field(default=None, description="Most recent GPS coordinates")
    last_location_at: Optional[datetime] = Field(default=None, description="Timestamp of the last location update")
    last_location_accuracy_m: Optional[int] = Field(default=None, ge=0, description="Accuracy of the last location in meters")
    last_location_source: Optional[str] = Field(default=None, max_length=20, description="Source of the location data (gps, network, etc)")
    default_location_point: Optional[LocationPoint] = Field(default=None, description="User's primary/default service location")
    location_tracking_enabled: bool = Field(default=False, description="Whether location tracking is active for this user")

    is_banned: bool = Field(default=False, description="Administrative ban status")


class ProfileCreate(ProfileBase):
    """
    Schema for creating a new Profile.
    """
    user_id: Optional[UUID] = Field(default=None, description="ID of the user this profile belongs to")
    seller_rating_avg: Decimal = Field(default=Decimal("0.00"), ge=0, le=5.0, description="Average rating of the seller (0-5)")
    seller_rating_count: int = Field(default=0, ge=0, description="Total number of ratings received")


class ProfileUpdate(BaseSchema):
    """
    Schema for updating an existing Profile. All fields are optional.
    """
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    bio: Optional[str] = None
    photo_url: Optional[str] = Field(default=None, max_length=500)
    cloudinary_public_id: Optional[str] = Field(default=None, max_length=500)
    seller_status: Optional[Literal["none", "active", "suspended"]] = None
    seller_completed_orders_count: Optional[int] = Field(default=None, ge=0)
    
    last_location_point: Optional[LocationPoint] = None
    last_location_accuracy_m: Optional[int] = Field(default=None, ge=0)
    last_location_at: Optional[datetime] = None
    last_location_source: Optional[str] = Field(default=None, max_length=20)
    default_location_point: Optional[LocationPoint] = None
    location_tracking_enabled: Optional[bool] = None

    is_banned: Optional[bool] = None
    seller_rating_avg: Optional[Decimal] = Field(default=None, ge=0, le=5.0)
    seller_rating_count: Optional[int] = Field(default=None, ge=0)


class ProfileResponse(ProfileBase):
    """
    Full Profile object returned by the API.
    """
    user_id: UUID
    seller_rating_avg: Decimal
    seller_rating_count: int
    created_at: datetime
    updated_at: datetime

    @field_validator("last_location_point", "default_location_point", mode="before")
    @classmethod
    def validate_geo(cls, v):
        """
        Converts PostGIS geography (WKB) or WKT strings into a LocationPoint schema.
        Handles both ORM objects and dictionaries.
        """
        if v is None:
            return None
        
        # Handle PostGIS WKBElement
        if isinstance(v, WKBElement):
            try:
                shape = to_shape(v)
                return LocationPoint(latitude=shape.y, longitude=shape.x)
            except Exception:
                return None
        
        # Handle string WKT "POINT(lon lat)" (Dev/SQLite fallback)
        if isinstance(v, str) and v.startswith("POINT"):
            try:
                parts = v.replace("POINT(", "").replace(")", "").split()
                if len(parts) == 2:
                    return LocationPoint(latitude=float(parts[1]), longitude=float(parts[0]))
            except Exception:
                return None

        if isinstance(v, dict):
            return LocationPoint(**v)
            
        return v


class PrivateProfileResponse(BaseSchema):
    """
    Detailed personal profile response for the authenticated user.
    Aggregates data from both User and Profile models.
    """
    user_id: UUID
    name: str
    bio: Optional[str] = None
    email: str
    photo_url: Optional[str] = None
    seller_status: str
    seller_completed_orders_count: int
    seller_rating_count: int
    total_services: int

    @model_validator(mode="before")
    @classmethod
    def map_user_data(cls, data: any) -> any:
        """
        Maps fields from a User model (and its joined relations) into the schema.
        Input is expected to be a User instance or dictionary with 'profile' and 'service_listings'.
        """
        if isinstance(data, dict):
            return data

        # Extract nested profile
        profile = getattr(data, "profile", None)
        if not profile:
            return data

        # Calculate metrics from relations
        service_listings = getattr(data, "service_listings", [])
        total_services = len(service_listings)

        return {
            "user_id": profile.userId,
            "name": profile.name,
            "bio": profile.bio,
            "email": getattr(data, "email", "Unknown"),
            "photo_url": profile.photoUrl,
            "seller_status": profile.sellerStatus,
            "seller_completed_orders_count": profile.sellerCompletedOrdersCount,
            "seller_rating_count": profile.sellerRatingCount,
            "total_services": total_services,
        }


class ProfilePublicResponse(BaseSchema):
    """
    Publicly visible profile summary, often used in administrative lists or seller searches.
    """
    user_id: UUID
    user_name: str
    photo_url: Optional[str] = None
    email: str
    phone: Optional[str] = None
    seller_rating_avg: Decimal = Field(default=Decimal("0.00"))
    is_banned: bool = False
    seller_completed_orders_count: int

    @model_validator(mode="before")
    @classmethod
    def map_profile_data(cls, data: any) -> any:
        """
        Maps fields from Profile and its related User into the public schema.
        """
        if isinstance(data, dict):
            return data

        user = getattr(data, "user", None)
        return {
            "user_id": data.userId,
            "user_name": data.name,
            "photo_url": data.photoUrl,
            "email": user.email if user else "Unknown",
            "phone": user.phone if user else None,
            "seller_rating_avg": data.sellerRatingAvg,
            "is_banned": data.isBanned,
            "seller_completed_orders_count": data.sellerCompletedOrdersCount,
        }


class PublicProfileDetailResponse(BaseSchema):
    """
    Enhanced public detail view for a specific profile.
    Includes comprehensive stats, reviews, and service counts.
    """
    user_id: UUID
    name: str
    bio: Optional[str] = None
    photo_url: Optional[str] = None
    completed_order_count: int
    avg_rating: Decimal
    reviews_count: int
    created_at: datetime
    phone: Optional[str] = None
    total_services: int

    @model_validator(mode="before")
    @classmethod
    def map_profile_detail(cls, data: any) -> any:
        """
        Consolidates profile data, user contact info, and relational counts.
        """
        if isinstance(data, dict):
            return data

        user = getattr(data, "user", None)
        # Assuming services are available via the user relationship or pre-fetched
        service_listings = getattr(user, "service_listings", []) if user else []

        return {
            "user_id": data.userId,
            "name": data.name,
            "bio": data.bio,
            "photo_url": data.photoUrl,
            "completed_order_count": data.sellerCompletedOrdersCount,
            "avg_rating": data.sellerRatingAvg,
            "reviews_count": data.sellerRatingCount,
            "created_at": data.created_at,
            "phone": user.phone if user else None,
            "total_services": len(service_listings),
        }
