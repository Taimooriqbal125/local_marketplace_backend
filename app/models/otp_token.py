import uuid
import enum
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import Boolean, String, DateTime, ForeignKey, Integer, text, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin

if TYPE_CHECKING:
    from .user import User


class OTPPurpose(str, enum.Enum):
    """Enumeration of possible purposes for an OTP."""
    SIGNUP_VERIFY = "signup_verify"
    RESET_PASSWORD = "reset_password"


class OTPToken(Base, TimestampMixin):
    """
    Model representing a one-time password (OTP) token.
    Used for email verification, password resets, and multi-factor flows.

    Attributes:
        id (uuid.UUID): Primary key.
        email (str): Target email for the OTP (can be for a new or existing user).
        user_id (uuid.UUID): Link to local User ID if applicable.
        otp_hash (str): Securely hashed OTP value.
        purpose (OTPPurpose): Why the OTP was issued.
        expires_at (datetime): Validity window.
        used (bool): Whether the OTP has already been verified.
        attempts (int): Counter for failed verification attempts.
        used_at (datetime): Detailed confirmation of usage.
        last_sent_at (datetime): Throttling safeguard for resending.
        resend_count (int): Counter for help-center escalation.
        created_at (datetime): From TimestampMixin.
        updated_at (datetime): From TimestampMixin.
    """

    __tablename__ = "otp_tokens"

    # Primary Key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        doc="Unique identifier for the OTP record."
    )

    # Identification
    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        doc="Destination email address for the code."
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        doc="Associated user record, if the user already exists."
    )

    # Content and Logic
    otp_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Hashed OTP secret for validation."
    )
    purpose: Mapped[OTPPurpose] = mapped_column(
        Enum(OTPPurpose),
        nullable=False,
        doc="Contextual usage of this OTP (e.g., reset, signup)."
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        doc="Expiration deadline for the token."
    )

    # Verification Lifecycle
    used: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
        doc="Flag indicating successful usage."
    )
    used_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Timestamp of when 'used' was toggled."
    )

    # Security and Throttling
    attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
        doc="Count of failed verification attempts."
    )
    last_sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        server_default=text("now()"),
        doc="Timestamp of the most recent delivery notification."
    )
    resend_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
        doc="Number of times the OTP has been re-delivered."
    )

    # Relationships
    user: Mapped[Optional["User"]] = relationship(
        "User", 
        backref="otp_tokens",
        doc="Associated User object."
    )

    def __repr__(self) -> str:
        return f"<OTPToken(id={self.id}, email='{self.email}', purpose='{self.purpose}')>"