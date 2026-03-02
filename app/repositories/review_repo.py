"""
Review Repository — handles database operations for the Review model.
"""

import uuid
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.review import Review
from app.schemas.review import ReviewCreate


class ReviewRepository:
    """Repository for Review CRUD and specialized queries."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, review_id: uuid.UUID) -> Optional[Review]:
        """Fetch a single review by its ID."""
        return self.db.query(Review).filter(Review.id == review_id).first()

    def get_by_order(self, order_id: uuid.UUID) -> List[Review]:
        """Fetch all reviews associated with a specific order (max 2: buyer and seller)."""
        return self.db.query(Review).filter(Review.orderId == order_id).all()

    def get_received_by_user(
        self, user_id: uuid.UUID, skip: int = 0, limit: int = 20
    ) -> List[Review]:
        """Return reviews received by a user, newest first."""
        return (
            self.db.query(Review)
            .filter(Review.reviewedUserId == user_id)
            .order_by(Review.createdAt.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_given_by_user(
        self, user_id: uuid.UUID, skip: int = 0, limit: int = 20
    ) -> List[Review]:
        """Return reviews written by a user, newest first."""
        return (
            self.db.query(Review)
            .filter(Review.reviewerId == user_id)
            .order_by(Review.createdAt.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def create(
        self, obj_in: ReviewCreate, reviewer_id: uuid.UUID, reviewed_user_id: uuid.UUID
    ) -> Review:
        """Create a new review in the database."""
        db_obj = Review(
            orderId=obj_in.orderId,
            reviewerId=reviewer_id,
            reviewedUserId=reviewed_user_id,
            rating=obj_in.rating,
            comment=obj_in.comment,
        )
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def delete(self, db_obj: Review) -> None:
        """Remove a review from the database."""
        self.db.delete(db_obj)
        self.db.commit()
