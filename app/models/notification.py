import uuid
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, Text, Boolean, ForeignKey, DateTime, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin


class NotificationType:
    """Constants for notification types."""
    ORDER_REQUESTED = "order_requested"
    ORDER_ACCEPTED = "order_accepted"
    BUYER_MARKED_COMPLETED = "buyer_marked_completed"
    ORDER_COMPLETED = "order_completed"
    ORDER_CANCELLED = "order_cancelled"
    ORDER_UPDATE = "order_update"  # General update
    REVIEW_RECEIVED = "review_received"


if TYPE_CHECKING:
    from .user import User
    from .order import Order
    from .service_listing import ServiceListing


class Notification(Base, TimestampMixin):
    """
    Model representing an in-app notification for a user.
    Alerts users about order status changes, reviews, or system updates.

    Attributes:
        id (uuid.UUID): Primary key.
        userId (uuid.UUID): Receiver of the notification.
        senderId (uuid.UUID): User who triggered the event (optional).
        orderId (uuid.UUID): Related order (optional).
        listingId (uuid.UUID): Related listing (optional).
        type (str): Category of notification (see NotificationType).
        title (str): Summary text.
        body (str): Detailed message.
        isRead (bool): Read status.
        readAt (datetime): Timestamp of when the notification was opened.
        created_at (datetime): From TimestampMixin.
        updated_at (datetime): From TimestampMixin.
    """

    __tablename__ = "notifications"

    # Type Constants Constants (Preserved for legacy code compatibility)
    TYPE_ORDER_REQUESTED = NotificationType.ORDER_REQUESTED
    TYPE_ORDER_ACCEPTED = NotificationType.ORDER_ACCEPTED
    TYPE_BUYER_MARKED_COMPLETED = NotificationType.BUYER_MARKED_COMPLETED
    TYPE_ORDER_COMPLETED = NotificationType.ORDER_COMPLETED
    TYPE_ORDER_CANCELLED = NotificationType.ORDER_CANCELLED
    TYPE_REVIEW_RECEIVED = NotificationType.REVIEW_RECEIVED

    # Primary Key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
        doc="Unique identifier for the notification."
    )

    # Foreign Keys (CamelCase preserved for compatibility)
    userId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="The recipient user ID."
    )
    senderId: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        doc="The user who triggered this notification."
    )
    orderId: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        doc="Reference to the associated order."
    )
    listingId: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("service_listings.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        doc="Reference to the associated service listing."
    )

    # Content
    type: Mapped[str] = mapped_column(
        String(50), 
        nullable=False,
        doc="Categorical type of the notification."
    )
    title: Mapped[str] = mapped_column(
        String(255), 
        nullable=False,
        doc="Short title or subject."
    )
    body: Mapped[str] = mapped_column(
        Text, 
        nullable=False,
        doc="Detailed notification content."
    )
    
    isRead: Mapped[bool] = mapped_column(
        Boolean, 
        nullable=False, 
        server_default=text("false"),
        doc="True if the user has read the notification."
    )

    # Lifecycle tracking
    readAt: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), 
        nullable=True,
        doc="Record of exactly when the user opened the notification."
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User", 
        foreign_keys=[userId], 
        back_populates="notifications_received",
        doc="The recipient user object."
    )
    sender: Mapped[Optional["User"]] = relationship(
        "User", 
        foreign_keys=[senderId], 
        back_populates="notifications_sent",
        doc="The user who sent/triggered the notification."
    )
    order: Mapped[Optional["Order"]] = relationship(
        "Order", 
        back_populates="notifications",
        doc="Access to related order details."
    )
    listing: Mapped[Optional["ServiceListing"]] = relationship(
        "ServiceListing",
        back_populates="notifications",
        doc="Access to related service listing details."
    )

    def __repr__(self) -> str:
        return f"<Notification(id={self.id}, type='{self.type}', userId={self.userId}, isRead={self.isRead})>"
