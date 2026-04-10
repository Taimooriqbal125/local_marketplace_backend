import uuid
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, Integer, ForeignKey, text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin

if TYPE_CHECKING:
    from .order import Order
    from .user import User


class Review(Base, TimestampMixin):
    """
    Model representing a review/rating left on an order transaction.
    A review can be left by a buyer for a seller, or vice versa.

    Attributes:
        id (uuid.UUID): Primary key.
        orderId (uuid.UUID): Linked transaction ID.
        reviewerId (uuid.UUID): User who wrote the review.
        reviewedUserId (uuid.UUID): User who is being rated.
        rating (int): Score from 1 to 5.
        comment (str): Verbal feedback.
        created_at (datetime): From TimestampMixin.
        updated_at (datetime): From TimestampMixin.
    """

    __tablename__ = "reviews"

    __table_args__ = (
        # A user can only review their counterpart once per order
        UniqueConstraint("orderId", "reviewerId", name="uq_reviews_order_reviewer"),
    )

    # Primary Key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
        doc="Unique identifier for the review."
    )

    # Foreign Keys (CamelCase preserved for compatibility)
    orderId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Reference to the transaction being reviewed."
    )
    reviewerId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="The author of the review."
    )
    reviewedUserId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="The target user receiving the rating."
    )

    # Core Content
    rating: Mapped[int] = mapped_column(
        Integer, 
        nullable=False,
        doc="Rating numerical score (typically 1-5)."
    )
    comment: Mapped[Optional[str]] = mapped_column(
        String, 
        nullable=True,
        doc="Optional text feedback provide by the reviewer."
    )

    # Relationships
    order: Mapped["Order"] = relationship(
        "Order", 
        back_populates="reviews",
        doc="The order associated with this review."
    )
    reviewer: Mapped["User"] = relationship(
        "User", 
        foreign_keys=[reviewerId], 
        back_populates="reviews_given",
        doc="Access to the reviewer's user data."
    )
    reviewed_user: Mapped["User"] = relationship(
        "User", 
        foreign_keys=[reviewedUserId], 
        back_populates="reviews_received",
        doc="Access to the reviewed user's data."
    )

    def __repr__(self) -> str:
        return f"<Review(id={self.id}, orderId={self.orderId}, rating={self.rating})>"