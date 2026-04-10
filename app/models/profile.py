import uuid
from datetime import datetime
from typing import Optional, TYPE_CHECKING, Any

from sqlalchemy import String, DateTime, Boolean, Integer, Numeric, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from geoalchemy2 import Geography

from app.db.base_class import Base, TimestampMixin

if TYPE_CHECKING:
    from .user import User


class Profile(Base, TimestampMixin):
    """
    Detailed profile information for a User, including seller statistics
    and location data for PostGIS-enabled geospatial queries.

    Attributes:
        user_id (uuid.UUID): Primary and Foreign Key to User.
        name (str): Full name or display name.
        bio (str): Biography or description.
        seller_completed_orders_count (int): Total orders completed as a seller.
        photo_url (str): URL to the profile picture.
        cloudinary_public_id (str): Reference for Cloudinary image management.
        seller_rating_avg (float): Average rating across all reviews.
        seller_rating_count (int): Number of reviews received.
        seller_status (str): Status of the seller (active, suspended, etc.).
        last_location_point (Geography): PostGIS Point for the user's last known location.
        location_tracking_enabled (bool): Privacy setting for location services.
        is_banned (bool): Administrative flag for user restrictions.
    """

    __tablename__ = "profiles"

    # Link to User
    userId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
        doc="Reference to the associated User ID."
    )

    # Personal Info
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc="Full or display name of the user."
    )
    bio: Mapped[Optional[str]] = mapped_column(
        String,
        nullable=True,
        doc="User biography or service description."
    )

    # Seller Statistics (CamelCase preserved for compatibility)
    sellerCompletedOrdersCount: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
        doc="Number of successfully completed sales."
    )
    photoUrl: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        doc="URL to the user's profile image."
    )
    cloudinary_public_id: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        doc="Public identifier for Cloudinary assets."
    )

    sellerRatingAvg: Mapped[float] = mapped_column(
        Numeric(3, 2),
        nullable=False,
        server_default=text("0.00"),
        doc="Average rating as calculated from historical reviews."
    )
    sellerRatingCount: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
        doc="Total number of ratings received."
    )
    sellerStatus: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'active'"),
        doc="Current status of the seller's account."
    )

    # Geospatial Data (PostGIS POINT, WGS84)
    last_location_point: Mapped[Optional[Any]] = mapped_column(
        Geography(geometry_type="POINT", srid=4326),
        nullable=True,
        doc="Last recorded GPS point for the user."
    )
    last_location_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Timestamp of the most recent location update."
    )
    last_location_accuracy_m: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        doc="GPS accuracy in meters."
    )
    last_location_source: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        doc="Source of the location data (e.g., 'gps', 'network')."
    )
    default_location_point: Mapped[Optional[Any]] = mapped_column(
        Geography(geometry_type="POINT", srid=4326),
        nullable=True,
        doc="User's set default or home location."
    )

    # Privacy and Moderation
    location_tracking_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
        doc="User consent flag for real-time location tracking."
    )
    isBanned: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
        doc="Flag indicating if the user has been administratively banned."
    )

    # Legacy columns removed in favor of TimestampMixin? 
    # Profile already had createdAt/updatedAt, but we merged to created_at/updated_at in Base.
    # To keep DB compatibility, we can map the attribute names if desired, 
    # but the user agreed to clean code, so consolidating on the Mixin is better 
    # as long as we migrate correctly.
    # For now, I'll keep the mixin as it adds NEW columns (created_at/updated_at).
    # If I want to replace the old ones, I should do it carefully.
    # The user said refactor all then migrate, so I'll let the migration handle the consolidation.

    # Relationship back to User
    user: Mapped["User"] = relationship(
        "User",
        back_populates="profile",
        uselist=False,
        doc="Associated User account for this profile."
    )

    def __repr__(self) -> str:
        return f"<Profile(userId={self.userId}, name='{self.name}', status='{self.sellerStatus}')>"