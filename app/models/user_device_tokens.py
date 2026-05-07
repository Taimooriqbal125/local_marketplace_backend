import uuid
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, ForeignKey, DateTime, Boolean, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin

if TYPE_CHECKING:
    from .user import User


class UserDeviceToken(Base, TimestampMixin):
    """
    Model representing a user's device push notification token.
    Maps a user to their specific devices for targeted push notifications.

    Attributes:
        id (uuid.UUID): Primary key.
        userId (uuid.UUID): Foreign key to the User.
        token (str): The unique push notification token (e.g., FCM registration token).
        deviceType (str): Type of device (e.g., 'android', 'ios', 'web').
        deviceName (str): Optional human-readable name for the device.
        isActive (bool): Whether this token is currently active and valid.
        lastUsedAt (datetime): Timestamp of the last time this token was used.
    """

    __tablename__ = "user_device_tokens"

    # Primary Key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
        doc="Unique identifier for the device token record."
    )

    # Foreign Key
    userId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="The ID of the user who owns this device."
    )

    # Token and Device Info
    expo_push_token: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        unique=True,
        index=True,
        doc="The Expo push notification token provided by the client."
    )
    deviceType: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        doc="The platform type (e.g., android, ios)."
    )
    deviceName: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        doc="Human-readable name of the device (e.g., iPhone 13)."
    )

    # Status and Activity
    isActive: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
        doc="Whether this token is active."
    )
    lastUsedAt: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Timestamp of when the token was last used to send a notification."
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        backref="device_tokens",
        doc="The user associated with this device token."
    )

    def __repr__(self) -> str:
        return f"<UserDeviceToken(id={self.id}, userId={self.userId}, deviceType='{self.deviceType}')>"
