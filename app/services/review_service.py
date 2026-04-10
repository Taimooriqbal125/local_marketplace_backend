"""
Review Service — encapsulates business logic for the Review resource.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.repositories.review_repo import ReviewRepository
from app.repositories.order_repo import OrderRepository
from app.repositories.profile_repo import ProfileRepository
from app.schemas.review import ReviewCreate
from app.models.review import Review
from app.services.notification_service import NotificationService
from app.models.notification import NotificationType
from app.models.user import User


class OrderNotFoundError(HTTPException):
    def __init__(self, detail: str = "Order not found"):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


class OrderStateError(HTTPException):
    def __init__(self, detail: str = "You can only review an order after it has been completed"):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


class ReviewForbiddenError(HTTPException):
    def __init__(self, detail: str = "Only the buyer of an order is authorized to leave a review"):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


class ReviewDuplicateError(HTTPException):
    def __init__(self, detail: str = "You have already reviewed this order"):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


class ReviewNotFoundError(HTTPException):
    def __init__(self, detail: str = "Review not found"):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


class ReviewService:
    """Enhanced Service layer for Review business logic."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = ReviewRepository(db)
        self.order_repo = OrderRepository(db)
        self.profile_repo = ProfileRepository(db)
        self.notification_service = NotificationService(db)

    async def create_review(self, obj_in: ReviewCreate, current_user_id: uuid.UUID) -> Review:
        """
        Create a new review for an order enforcing state and security rules.
        """
        # 1. Fetch the order
        order = self.order_repo.get(obj_in.order_id)
        if not order:
            raise OrderNotFoundError()

        # 2. Check strict order status
        if order.status != "completed":
            raise OrderStateError()

        # 3. Verify ownership: ONLY the buyer can leave a review
        is_buyer = order.buyerId == current_user_id
        if not is_buyer:
            raise ReviewForbiddenError()

        reviewed_user_id = order.sellerId

        # 4. Check for duplicate review preemptively
        existing_reviews = self.repo.get_by_order(obj_in.order_id)
        if any(r.reviewerId == current_user_id for r in existing_reviews):
            raise ReviewDuplicateError()

        # 5. Create the review
        review = self.repo.create(
            obj_in=obj_in,
            reviewer_id=current_user_id,
            reviewed_user_id=reviewed_user_id
        )

        # 6. Update Seller Reputation in Profile
        self.profile_repo.update_seller_rating(reviewed_user_id, obj_in.rating)

        # 7. Trigger Notification for Seller
        reviewer_profile = self.profile_repo.get_by_user_id(current_user_id)
        reviewer_name = reviewer_profile.name if reviewer_profile else "A Buyer"

        listing_title = order.listing.title if order and order.listing else "your service"

        await self.notification_service.send_notification(
            user_id=reviewed_user_id,
            sender_id=current_user_id,
            order_id=obj_in.order_id,
            listing_id=order.listingId if order else None,
            type=NotificationType.REVIEW_RECEIVED,
            title="New Review Received",
            body=f"{reviewer_name} has left a {obj_in.rating}-star review for '{listing_title}'."
        )

        return review

    def get_review(self, review_id: uuid.UUID) -> Review:
        """Fetch a single review or raise 404."""
        review = self.repo.get(review_id)
        if not review:
            raise ReviewNotFoundError()
        return review

    def list_received_reviews(
        self, user_id: uuid.UUID, rating: Optional[int] = None, skip: int = 0, limit: int = 20
    ) -> List[Review]:
        """Fetch reviews received by a user with optional rating filter."""
        return self.repo.get_received_by_user(user_id, rating=rating, skip=skip, limit=limit)

    def list_given_reviews(self, user_id: uuid.UUID, skip: int = 0, limit: int = 20) -> List[Review]:
        """Fetch reviews written by a user."""
        return self.repo.get_given_by_user(user_id, skip=skip, limit=limit)

    def list_reviews_by_listing(
        self, listing_id: uuid.UUID, skip: int = 0, limit: int = 20
    ) -> List[Review]:
        """Fetch all reviews for a specific service listing."""
        return self.repo.get_by_listing(listing_id, skip=skip, limit=limit)

    def delete_review(self, review_id: uuid.UUID, current_user_id: uuid.UUID) -> None:
        """Delete a review (only the author or an admin can delete)."""
        review = self.get_review(review_id)
        
        if review.reviewerId != current_user_id:
            raise ReviewForbiddenError("Only the author can delete this review")
            
        self.repo.delete(review)

    def list_all_reviews(
        self,
        current_user: User,
        days: Optional[int] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Review]:
        """
        Fetch all reviews for admin listing with optional date range.
        """
        if not current_user.is_admin:
            raise ReviewForbiddenError("Only administrators can access the full review listing.")
            
        start_date = None
        if days:
            start_date = datetime.now(timezone.utc) - timedelta(days=days)

        return self.repo.get_all_filtered(start_date=start_date, skip=skip, limit=limit)