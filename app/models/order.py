import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, ForeignKey, DateTime, text, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.db.base_class import Base

class Order(Base):
    """
    Model representing an order for a service listing.
    
    Status Lifecycle:
    - requested: Buyer has sent a request.
    - accepted: Seller has accepted the request.
    - completed: Service is finished and confirmed.
    - cancelled: Request or order was cancelled.
    - disputed: There is a problem with the order.
    """
    __tablename__ = "orders"
    
    __table_args__ = (
        # Business rules validation at database level
        CheckConstraint('"proposedPrice" > 0', name="ck_orders_proposed_price_positive"),
        CheckConstraint('"agreedPrice" IS NULL OR "agreedPrice" > 0', name="ck_orders_agreed_price_positive"),
    )

    # ── Primary Key ──────────────────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )

    # ── Foreign Keys ─────────────────────────────────────────────────────────
    
    # listingId → service_listings.id
    # Using RESTRICT to prevent deleting a listing that has active/past orders
    listingId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("service_listings.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )

    # buyerId → users.id (The user requesting the service)
    buyerId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )

    # sellerId → users.id (The user providing the service, denormalized for easier querying)
    sellerId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )

    # ── Core Fields ──────────────────────────────────────────────────────────

    # status: current state of the order
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'requested'"),
        index=True
    )

    # proposedPrice: initial price offered by the buyer
    proposedPrice: Mapped[int] = mapped_column(Integer, nullable=False)

    # agreedPrice: final price confirmed by the seller
    agreedPrice: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # notes: extra info or requirements provided by the buyer
    notes: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # ── Timestamps for Lifecycle ─────────────────────────────────────────────

    # acceptedAt: when the seller accepts the request
    acceptedAt: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), 
        nullable=True
    )

    # sellerCompletedAt: when the seller marks the job as done
    sellerCompletedAt: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), 
        nullable=True
    )

    # buyerCompletedAt: when the buyer confirms receipt/satisfaction
    buyerCompletedAt: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), 
        nullable=True
    )

    # ── General Timestamps ───────────────────────────────────────────────────
    createdAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )

    updatedAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now()
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    
    listing: Mapped["ServiceListing"] = relationship("ServiceListing")
    buyer: Mapped["User"] = relationship("User", foreign_keys=[buyerId])
    seller: Mapped["User"] = relationship("User", foreign_keys=[sellerId])
    reviews: Mapped[list["Review"]] = relationship("Review", back_populates="order", cascade="all, delete-orphan")
    notifications: Mapped[list["Notification"]] = relationship("Notification", back_populates="order", cascade="all, delete-orphan")