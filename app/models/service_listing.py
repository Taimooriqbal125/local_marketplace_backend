import uuid
from typing import Optional

from sqlalchemy import String, Text, Boolean, Numeric, Float, ForeignKey, DateTime, text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from geoalchemy2 import Geography

from app.db.base_class import Base


class ServiceListing(Base):
    """
    Represents a service offered by a seller on the local marketplace.

    Relationships:
        - seller  → User   (many-to-one)
        - city    → City   (many-to-one, MVP)
        - category → Category (many-to-one)
    """

    __tablename__ = "service_listings"

    __table_args__ = (
        UniqueConstraint("title", "description", name="uq_service_listings_title_description"),
    )

    # ── Primary Key ──────────────────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )

    # ── Foreign Keys ─────────────────────────────────────────────────────────

    # sellerId → users.id  (required; cascade-delete so listings are removed when user is deleted)
    sellerId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # cityId → cities.id  (MVP: optional at schema level so it can be phased in)
    cityId: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cities.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # categoryId → categories.id  (required)
    categoryId: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # ── Core Fields ──────────────────────────────────────────────────────────

    # title: short, searchable headline for the listing
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    # description: full details of the service (up to ~64 KB in Postgres TEXT)
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # ── Pricing ──────────────────────────────────────────────────────────────

    # priceType: e.g. "fixed", "hourly", "daily", "negotiable"
    priceType: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'fixed'"),
    )

    # priceAmount: monetary value (up to 10 digits, 2 decimal places)
    priceAmount: Mapped[Optional[float]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )

    # isNegotiable: buyer can haggle on final price
    isNegotiable: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )

    # ── Location ─────────────────────────────────────────────────────────────

    # serviceLocation: human-readable address or area description
    serviceLocation: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    # serviceRadiusKm: how far (in km) the seller is willing to travel / serve
    serviceRadiusKm: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    # service_location: PostGIS Geography point (lon, lat, WGS84)
    service_location: Mapped[Optional[object]] = mapped_column(
        Geography(geometry_type="POINT", srid=4326),
        nullable=True,
    )

    # ── Moderation / Lifecycle ────────────────────────────────────────────────

    # status: "draft" | "active" | "paused" | "closed" | "banned"
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
        order_by="ListingMedia.sortOrder"
    )

    orders: Mapped[list["Order"]] = relationship(
        "Order",
        back_populates="listing",
        cascade="all, delete-orphan"
    )

    notifications: Mapped[list["Notification"]] = relationship(
        "Notification",
        back_populates="listing",
        cascade="all, delete-orphan"
    )
