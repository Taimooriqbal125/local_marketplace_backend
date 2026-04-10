import uuid
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, Integer, ForeignKey, DateTime, text, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin

if TYPE_CHECKING:
    from .service_listing import ServiceListing
    from .user import User
    from .review import Review
    from .notification import Notification


class Order(Base, TimestampMixin):
    """
    Model representing an order for a service listing.
    Tracks the lifecycle from request to completion or dispute.

    Status Lifecycle:
        - requested: Buyer has sent a request.
        - accepted: Seller has accepted the request.
        - completed: Service is finished and confirmed.
        - cancelled: Request or order was cancelled.
        - disputed: There is a problem with the order.
    
    Attributes:
        id (uuid.UUID): Primary key.
        listingId (uuid.UUID): Related ServiceListing ID.
        buyerId (uuid.UUID): ID of the User purchasing the service.
        sellerId (uuid.UUID): ID of the User providing the service.
        status (str): Current state of the order.
        proposedPrice (int): Price initially offered by the buyer.
        agreedPrice (int): Final price confirmed by both parties.
        notes (str): Communication from the buyer.
        acceptedAt (datetime): When the seller accepted the order.
        sellerCompletedAt (datetime): When the seller finished the work.
        buyerCompletedAt (datetime): When the buyer confirmed satisfaction.
        created_at (datetime): From TimestampMixin.
        updated_at (datetime): From TimestampMixin.
    """

    __tablename__ = "orders"

    __table_args__ = (
        # Business rules validation at database level
        CheckConstraint('"proposedPrice" > 0', name="ck_orders_proposed_price_positive"),
        CheckConstraint('"agreedPrice" IS NULL OR "agreedPrice" > 0', name="ck_orders_agreed_price_positive"),
    )

    # Primary Key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
        doc="Unique identifier for the order."
    )

    # Foreign Keys (CamelCase preserved for compatibility)
    listingId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("service_listings.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        doc="Reference to the service being ordered."
    )
    buyerId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        doc="The buyer who initiated the order."
    )
    sellerId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        doc="The seller providing the service (denormalized)."
    )

    # Core Information
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'requested'"),
        index=True,
        doc="Current lifecycle status of the order."
    )
    proposedPrice: Mapped[int] = mapped_column(
        Integer, 
        nullable=False,
        doc="Buyer's initial price proposal."
    )
    agreedPrice: Mapped[Optional[int]] = mapped_column(
        Integer, 
        nullable=True,
        doc="Final price confirmed by the seller."
    )
    notes: Mapped[Optional[str]] = mapped_column(
        String, 
        nullable=True,
        doc="Optional requirements or messages from the buyer."
    )

    # Lifecycle Milestones
    acceptedAt: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Timestamp of seller acceptance."
    )
    sellerCompletedAt: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Timestamp when seller marked order as done."
    )
    buyerCompletedAt: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Timestamp when buyer confirmed completion."
    )

    # Relationships
    listing: Mapped["ServiceListing"] = relationship(
        "ServiceListing",
        doc="The specific listing associated with this order."
    )
    buyer: Mapped["User"] = relationship(
        "User", 
        foreign_keys=[buyerId],
        doc="User object for the buyer."
    )
    seller: Mapped["User"] = relationship(
        "User", 
        foreign_keys=[sellerId],
        doc="User object for the seller."
    )
    reviews: Mapped[list["Review"]] = relationship(
        "Review", 
        back_populates="order", 
        cascade="all, delete-orphan",
        doc="Reviews linked to this transaction."
    )
    notifications: Mapped[list["Notification"]] = relationship(
        "Notification", 
        back_populates="order", 
        cascade="all, delete-orphan",
        doc="Notifications triggered by this order's events."
    )

    def __repr__(self) -> str:
        return f"<Order(id={self.id}, status='{self.status}', buyerId={self.buyerId})>"