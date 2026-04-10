import uuid
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import Boolean, String, DateTime, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin

if TYPE_CHECKING:
    from .user import User


class RefreshToken(Base, TimestampMixin):
    """
    Model representing a secure refresh token for session management.
    Used to issue new access tokens without requiring user re-authentication.

    Attributes:
        id (uuid.UUID): Primary key.
        user_id (uuid.UUID): ID of the user the token belongs to.
        token_hash (str): Securely hashed representation of the persistent token.
        expires_at (datetime): When the token becomes invalid.
        revoked (bool): Administrative override to invalidate the session.
        revoked_at (datetime): Specific timestamp of revocation.
        created_at (datetime): From TimestampMixin.
        updated_at (datetime): From TimestampMixin.
    """

    __tablename__ = "refresh_tokens"

    # Primary Key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        doc="Unique identifier for the refresh token record."
    )

    # User association
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Owner of this refresh session."
    )

    # Security Details
    token_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        doc="Hashed token value for database lookup and verification."
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        doc="Absolute expiration time of the token."
    )

    # Revocation Management
    revoked: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
        doc="Manually blacklists the token before its natural expiration."
    )
    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Timestamp of when 'revoked' was set to True."
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User", 
        backref="refresh_tokens",
        doc="User associated with this refresh capability."
    )

    def __repr__(self) -> str:
        return f"<RefreshToken(id={self.id}, user_id={self.user_id}, expires_at={self.expires_at})>"