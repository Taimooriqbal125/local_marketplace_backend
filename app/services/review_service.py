"""
Review Service — encapsulates business logic for the Review resource.
"""

import uuid
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.repositories.review_repo import ReviewRepository
from app.repositories.order_repo import OrderRepository
from app.schemas.review import ReviewCreate
from app.models.review import Review


class ReviewService:
    """Enhanced Service layer for Review business logic."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = ReviewRepository(db)
        self.order_repo = OrderRepository(db)

    def create_review(self, obj_in: ReviewCreate, current_user_id: uuid.UUID) -> Review:
        """
        Create a new review for an order.
        
        Business Rules:
        1. Order must exist.
        2. Order must be in 'completed' status.
        3. Reviewer must be either the Buyer or the Seller of the order.
        4. User cannot review themselves (enforced by role check).
        5. User cannot review the same order twice (enforced by DB unique constraint).
        """
        # 1. Fetch the order
        order = self.order_repo.get(obj_in.orderId)
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found"
            )

        # 2. Check order status
        # Note: Usually, we only allow reviews for completed orders
        if order.status != "completed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You can only review an order after it has been completed"
            )

        # 3. Verify ownership and identify the recipient (reviewedUserId)
        is_buyer = order.buyerId == current_user_id
        is_seller = order.sellerId == current_user_id

        if not (is_buyer or is_seller):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to review this order"
            )

        # Auto-discover reviewedUserId
        reviewed_user_id = order.sellerId if is_buyer else order.buyerId

        # 4. Check for duplicate review (Prevent 500 error from DB constraint)
        existing_reviews = self.repo.get_by_order(obj_in.orderId)
        for r in existing_reviews:
            if r.reviewerId == current_user_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="You have already reviewed this order"
                )

        # 5. Create the review
        return self.repo.create(
            obj_in=obj_in,
            reviewer_id=current_user_id,
            reviewed_user_id=reviewed_user_id
        )

    def get_review(self, review_id: uuid.UUID) -> Review:
        """Fetch a single review or raise 404."""
        review = self.repo.get(review_id)
        if not review:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Review not found"
            )
        return review

    def list_received_reviews(self, user_id: uuid.UUID, skip: int = 0, limit: int = 20) -> List[Review]:
        """Fetch reviews received by a user."""
        return self.repo.get_received_by_user(user_id, skip=skip, limit=limit)

    def list_given_reviews(self, user_id: uuid.UUID, skip: int = 0, limit: int = 20) -> List[Review]:
        """Fetch reviews written by a user."""
        return self.repo.get_given_by_user(user_id, skip=skip, limit=limit)

    def delete_review(self, review_id: uuid.UUID, current_user_id: uuid.UUID) -> None:
        """Delete a review (only the author or an admin can delete)."""
        review = self.get_review(review_id)
        
        if review.reviewerId != current_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the author can delete this review"
            )
            
        self.repo.delete(review)