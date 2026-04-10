import uuid
from datetime import datetime
from typing import Optional, TYPE_CHECKING, Any

from sqlalchemy import String, Text, Boolean, Numeric, Float, ForeignKey, DateTime, text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from geoalchemy2 import Geography

from app.db.base_class import Base, TimestampMixin

if TYPE_CHECKING:
    from .user import User
    from .cities import City
    from .category import Category
    from .listing_media import ListingMedia
    from .order import Order
    from .notification import Notification


class ServiceListing(Base, TimestampMixin):
    """
    Represents a service offered by a seller on the local marketplace.
    Contains price, location, category, and lifecycle information.

    Attributes:
        id (uuid.UUID): Primary key.
        sellerId (uuid.UUID): ID of the user offering the service.
        cityId (uuid.UUID): ID of the city where the service is located.
        categoryId (uuid.UUID): ID of the service category.
        title (str): Brief headline for the listing.
        description (str): Detailed text about the service.
        priceType (str): Pricing model (fixed, hourly, etc.).
        priceAmount (float): Monetary value of the service.
        isNegotiable (bool): Whether the price can be discussed.
        serviceLocation (str): Human-readable address.
        serviceRadiusKm (float): Operational radius for the service.
        service_location (Geography): PostGIS Geography point (lon, lat).
        status (str): Current state of the listing (active, draft, etc.).
        created_at (datetime): Timestamp from TimestampMixin.
        updated_at (datetime): Timestamp from TimestampMixin.
    """

    __tablename__ = "service_listings"

    __table_args__ = (
        UniqueConstraint("title", "description", name="uq_service_listings_title_description"),
    )

    # Primary Key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
        doc="Unique identifier for the service listing."
    )

    # Foreign Keys (CamelCase preserved for compatibility)
    sellerId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Owner of the listing."
    )
    cityId: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cities.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        doc="Geographic city association."
    )
    categoryId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        doc="Service category link."
    )

    # Core Information
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        doc="Short headline of the service."
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Detailed description of the service offered."
    )

    # Pricing
    priceType: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'fixed'"),
        doc="Model of pricing (fixed, hourly, daily)."
    )
    priceAmount: Mapped[Optional[float]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        doc="Numeric price value."
    )
    isNegotiable: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
        doc="Indicates if the seller accepts price negotiations."
    )

    # Location Services
    serviceLocation: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Human-readable location or area name."
    )
    serviceRadiusKm: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        doc="Serviceable radius from the center point in kilometers."
    )
    service_location: Mapped[Optional[Any]] = mapped_column(
        Geography(geometry_type="POINT", srid=4326),
        nullable=True,
        doc="PostGIS point for precise geospatial searches."
    )

    # Lifecycle Management
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'draft'"),
        index=True,
        doc="Current status (draft, active, paused, closed, banned)."
    )

    # Relationships
    seller: Mapped["User"] = relationship(
        "User",
        back_populates="service_listings",
        lazy="joined",
        doc="The User who owns this listing."
    )
    city: Mapped[Optional["City"]] = relationship(
        "City",
        lazy="joined",
        doc="The city where this service is provided."
    )
    category: Mapped["Category"] = relationship(
        "Category",
        lazy="joined",
        doc="The category classification of this service."
    )
    media: Mapped[list["ListingMedia"]] = relationship(
        "ListingMedia",
        back_populates="listing",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="ListingMedia.sortOrder",
        doc="Associated images and videos."
    )
    orders: Mapped[list["Order"]] = relationship(
        "Order",
        back_populates="listing",
        cascade="all, delete-orphan",
        doc="Orders placed for this specific listing."
    )
    notifications: Mapped[list["Notification"]] = relationship(
        "Notification",
        back_populates="listing",
        cascade="all, delete-orphan",
        doc="System notifications related to this listing."
    )

    def __repr__(self) -> str:
        return f"<ServiceListing(id={self.id}, title='{self.title[:20]}...', status='{self.status}')>"
