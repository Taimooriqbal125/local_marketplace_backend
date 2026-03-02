import uuid
from typing import Optional
from sqlalchemy import Column, String, Integer, ForeignKey, DateTime, text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.db.base_class import Base

class Review(Base):
    """
    Model representing a review left on an order.
    
    A review can be left by a buyer for a seller, or vice versa.
    The reviewedUserId explicitly identifies who is receiving the rating.
    """
    __tablename__ = "reviews"
    
    __table_args__ = (
        # A user can only review their counterpart once per order
        UniqueConstraint("orderId", "reviewerId", name="uq_reviews_order_reviewer"),
    )

    # ── Primary Key ──────────────────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )

    # ── Foreign Keys ─────────────────────────────────────────────────────────
    
    # orderId → orders.id
    orderId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # reviewerId → users.id (The person writing the review)
    reviewerId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # reviewedUserId → users.id (The person being reviewed)
    reviewedUserId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # ── Core Fields ──────────────────────────────────────────────────────────
    
    # rating: 1 to 5
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # comment: voluntary feedback
    comment: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # ── Timestamps ────────────────────────────────────────────────────────────
    createdAt: Mapped[str] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    order: Mapped["Order"] = relationship("Order", back_populates="reviews")
    reviewer: Mapped["User"] = relationship("User", foreign_keys=[reviewerId], back_populates="reviews_given")
    reviewed_user: Mapped["User"] = relationship("User", foreign_keys=[reviewedUserId], back_populates="reviews_received")