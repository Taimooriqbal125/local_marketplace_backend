import uuid
from typing import Optional
from datetime import datetime

from sqlalchemy import String, Text, Boolean, ForeignKey, DateTime, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base_class import Base

class NotificationType:
    """Constants for notification types."""
    ORDER_REQUESTED = "order_requested"
    ORDER_ACCEPTED = "order_accepted"
    BUYER_MARKED_COMPLETED = "buyer_marked_completed"
    ORDER_COMPLETED = "order_completed"
    ORDER_CANCELLED = "order_cancelled"
    ORDER_UPDATE = "order_update"  # General update
    REVIEW_RECEIVED = "review_received"


class Notification(Base):
    """
    Model representing a notification for a user.
    """
    __tablename__ = "notifications"

    # Notification Types (Legacy constants for backward compatibility if needed, 
    # but preferred to use NotificationType class directly)
    TYPE_ORDER_REQUESTED = NotificationType.ORDER_REQUESTED
    TYPE_ORDER_ACCEPTED = NotificationType.ORDER_ACCEPTED
    TYPE_BUYER_MARKED_COMPLETED = NotificationType.BUYER_MARKED_COMPLETED
    TYPE_ORDER_COMPLETED = NotificationType.ORDER_COMPLETED
    TYPE_ORDER_CANCELLED = NotificationType.ORDER_CANCELLED
    TYPE_REVIEW_RECEIVED = NotificationType.REVIEW_RECEIVED

    # ── Primary Key ──────────────────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )

    # ── Foreign Keys ─────────────────────────────────────────────────────────
    
    # userId: The user who receives the notification
    userId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # senderId: The user who triggered the notification (Optional)
    senderId: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    # orderId: Related order (Optional)
    orderId: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )

    # listingId: Related service listing (Optional)
    listingId: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("service_listings.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )

    # ── Core Fields ──────────────────────────────────────────────────────────

    type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    
    isRead: Mapped[bool] = mapped_column(
        Boolean, 
        nullable=False, 
        server_default=text("false")
    )

    # ── Timestamps ────────────────────────────────────────────────────────────
    
    readAt: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), 
        nullable=True
    )

    createdAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    
    # The user receiving the notification
    user: Mapped["User"] = relationship(
        "User", 
        foreign_keys=[userId], 
        back_populates="notifications_received"
    )

    # The user who triggered the notification
    sender: Mapped[Optional["User"]] = relationship(
        "User", 
        foreign_keys=[senderId], 
        back_populates="notifications_sent"
    )

    order: Mapped[Optional["Order"]] = relationship(
        "Order", 
        back_populates="notifications"
    )

    listing: Mapped[Optional["ServiceListing"]] = relationship(
        "ServiceListing",
        back_populates="notifications"
    )
