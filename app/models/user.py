import uuid
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, DateTime, Boolean, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin

if TYPE_CHECKING:
    from .profile import Profile
    from .service_listing import ServiceListing
    from .order import Order
    from .review import Review
    from .notification import Notification


class User(Base, TimestampMixin):
    """
    Representation of a user in the system.
    Handles authentication, identity, and connections to other entities.

    Attributes:
        id (uuid.UUID): Primary key.
        email (str): Unique email address.
        phone (str): Unique phone number (optional).
        hashed_password (str): Bcrypt hashed password.
        is_active (bool): Whether the account is enabled.
        is_admin (bool): Whether the user has administrative privileges.
        is_email_verified (bool): Status of email verification.
        email_verified_at (datetime): Timestamp of email verification.
        last_active_at (datetime): Timestamp of last user activity.
        created_at (datetime): Fixed creation timestamp (from TimestampMixin).
        updated_at (datetime): Auto-updating timestamp (from TimestampMixin).
    """

    __tablename__ = "users"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        doc="Unique identifier for the user."
    )

    # Identity and Authentication
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        doc="Primary email address for login and communication."
    )
    phone: Mapped[Optional[str]] = mapped_column(
        String(20),
        unique=True,
        nullable=True,
        doc="Mobile phone number."
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Securely hashed password string."
    )

    # Status Flags
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
        doc="Indicates if the user account is active."
    )
    is_admin: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
        doc="Indicates if the user has administrative access."
    )

    # Verification and Activity
    is_email_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
        doc="Current status of email verification."
    )
    email_verified_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Timestamp of when the email was verified."
    )
    last_active_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Timestamp of the user's most recent activity."
    )

    # Relationships
    profile: Mapped[Optional["Profile"]] = relationship(
        "Profile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="joined",
        doc="One-to-one relationship with User Profile."
    )

    service_listings: Mapped[list["ServiceListing"]] = relationship(
        "ServiceListing",
        back_populates="seller",
        cascade="all, delete-orphan",
        doc="List of services offered by this user."
    )

    # Orders as Buyer and Seller
    orders_as_buyer: Mapped[list["Order"]] = relationship(
        "Order",
        back_populates="buyer",
        foreign_keys="[Order.buyerId]",
        doc="List of orders placed by this user."
    )
    orders_as_seller: Mapped[list["Order"]] = relationship(
        "Order",
        back_populates="seller",
        foreign_keys="[Order.sellerId]",
        doc="List of orders received by this user as a seller."
    )

    # Reviews as Recipient and Author
    reviews_given: Mapped[list["Review"]] = relationship(
        "Review",
        back_populates="reviewer",
        foreign_keys="[Review.reviewerId]",
        doc="Reviews authored by this user."
    )
    reviews_received: Mapped[list["Review"]] = relationship(
        "Review",
        back_populates="reviewed_user",
        foreign_keys="[Review.reviewedUserId]",
        doc="Reviews received for this user's services."
    )

    # Notifications Flow
    notifications_received: Mapped[list["Notification"]] = relationship(
        "Notification",
        back_populates="user",
        foreign_keys="Notification.userId",
        cascade="all, delete-orphan",
        doc="Direct notifications sent to this user."
    )
    notifications_sent: Mapped[list["Notification"]] = relationship(
        "Notification",
        back_populates="sender",
        foreign_keys="Notification.senderId",
        doc="Notifications initiated by this user."
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email='{self.email}', is_active={self.is_active})>"