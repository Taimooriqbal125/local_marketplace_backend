"""
Review Repository — handles database operations for the Review model.
Modernized to SQLAlchemy 2.0 select syntax and safely bridges snake_case schemas with camelCase DB columns.
"""

import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.review import Review
from app.models.user import User
from app.models.order import Order
from app.models.service_listing import ServiceListing
from app.schemas.review import ReviewCreate


REVIEW_MODEL_MAP = {
    "order_id": "orderId",
    "rating": "rating",
    "comment": "comment",
}


class ReviewRepository:
    """Repository for Review CRUD and specialized queries."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, review_id: uuid.UUID) -> Optional[Review]:
        """Fetch a single review by its ID."""
        stmt = select(Review).where(Review.id == review_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_order(self, order_id: uuid.UUID) -> List[Review]:
        """Fetch all reviews associated with a specific order (max 2: buyer and seller)."""
        stmt = select(Review).where(Review.orderId == order_id)
        return list(self.db.execute(stmt).scalars().all())

    def get_received_by_user(
        self, user_id: uuid.UUID, rating: Optional[int] = None, skip: int = 0, limit: int = 20
    ) -> List[Review]:
        """Return reviews received by a user, newest first. Includes joined relations."""
        stmt = (
            select(Review)
            .options(
                joinedload(Review.reviewer).joinedload(User.profile),
                joinedload(Review.order).joinedload(Order.listing).joinedload(ServiceListing.category),
                joinedload(Review.order).joinedload(Order.listing).joinedload(ServiceListing.media),
            )
            .where(Review.reviewedUserId == user_id)
        )

        if rating is not None:
            stmt = stmt.where(Review.rating == rating)

        stmt = stmt.order_by(Review.created_at.desc()).offset(skip).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def get_given_by_user(
        self, user_id: uuid.UUID, skip: int = 0, limit: int = 20
    ) -> List[Review]:
        """Return reviews written by a user, newest first. Includes service context."""
        stmt = (
            select(Review)
            .options(
                joinedload(Review.order).joinedload(Order.listing).joinedload(ServiceListing.category),
                joinedload(Review.order).joinedload(Order.listing).joinedload(ServiceListing.media),
            )
            .where(Review.reviewerId == user_id)
            .order_by(Review.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_by_listing(
        self, listing_id: uuid.UUID, skip: int = 0, limit: int = 20
    ) -> List[Review]:
        """Return all reviews for a specific service listing, newest first."""
        stmt = (
            select(Review)
            .join(Order, Review.orderId == Order.id)
            .options(
                joinedload(Review.reviewer).joinedload(User.profile),
                joinedload(Review.order).joinedload(Order.listing).joinedload(ServiceListing.category),
                joinedload(Review.order).joinedload(Order.listing).joinedload(ServiceListing.media),
            )
            .where(Order.listingId == listing_id)
            .order_by(Review.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_all_filtered(
        self,
        start_date: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Review]:
        """
        Fetch all reviews with filters (Admin only context).
        Joins all related models for a comprehensive response.
        """
        stmt = select(Review).options(
            joinedload(Review.reviewer).joinedload(User.profile),
            joinedload(Review.reviewed_user).joinedload(User.profile),
            joinedload(Review.order).joinedload(Order.listing).joinedload(ServiceListing.media),
        )

        if start_date:
            stmt = stmt.where(Review.created_at >= start_date)

        stmt = stmt.order_by(Review.created_at.desc()).offset(skip).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def create(
        self, obj_in: ReviewCreate, reviewer_id: uuid.UUID, reviewed_user_id: uuid.UUID
    ) -> Review:
        """Create a new review in the database with explicit mapping."""
        data = obj_in.model_dump()
        db_data = {
            "reviewerId": reviewer_id,
            "reviewedUserId": reviewed_user_id,
        }
        
        for key, value in data.items():
            model_key = REVIEW_MODEL_MAP.get(key, key)
            db_data[model_key] = value

        db_obj = Review(**db_data)
        self.db.add(db_obj)
        self.db.commit()
        
        # Reload with relationships for the response
        stmt = (
            select(Review)
            .options(joinedload(Review.reviewed_user).joinedload(User.profile))
            .where(Review.id == db_obj.id)
        )
        return self.db.execute(stmt).scalar_one()

    def delete(self, db_obj: Review) -> None:
        """Remove a review from the database."""
        self.db.delete(db_obj)
        self.db.commit()
