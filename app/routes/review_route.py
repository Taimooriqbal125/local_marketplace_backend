"""
Review Routes — API endpoints for reviews.

This is the *thinnest* layer. A route should:
  1. Accept the request
  2. Call the service
  3. Return the response
"""

from fastapi import APIRouter, Depends, Query, status, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID
from typing import Optional

from app.db.session import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.review import (
    ReviewCreate,
    ReviewResponse,
    AdminReviewResponse,
    ReviewReceivedResponse,
    ReviewForServiceResponse,
    ReviewCreateResponse,
    ReviewGivenResponse
)
from app.services import ReviewService

router = APIRouter(prefix="/reviews", tags=["Reviews"])


# ============================================================
#  POST /reviews  →  Leave a review for an order
# ============================================================
@router.post("/", response_model=ReviewCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_review(
    obj_in: ReviewCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Leave a review for an order.
    
    - **orderId**: The ID of the completed order
    - **rating**: 1 to 5 stars
    - **comment**: Optional feedback
    """
    service = ReviewService(db)
    return await service.create_review(obj_in, current_user.id)


# ============================================================
#  GET /reviews  →  List all reviews (Admin Only)
# ============================================================
@router.get("/", response_model=list[AdminReviewResponse])
def get_all_reviews(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    days: Optional[int] = Query(None, description="Filter reviews from last X days (e.g., 7, 30)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieve a comprehensive list of all reviews in the system.
    
    **Restricted to Administrators only.**
    """
    # Restricted to Admin Only
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can access the full review listing."
        )

    service = ReviewService(db)
    return service.list_all_reviews(days=days, skip=skip, limit=limit)


# ============================================================
#  GET /reviews/me/received  →  Reviews received by user
# ============================================================
@router.get("/me/received", response_model=list[ReviewReceivedResponse])
def get_my_received_reviews(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    rating: Optional[int] = Query(None, ge=1, le=5, description="Filter by star rating"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all reviews received by the authenticated user."""
    service = ReviewService(db)
    return service.list_received_reviews(current_user.id, rating=rating, skip=skip, limit=limit)


# ============================================================
#  GET /reviews/me/given  →  Reviews written by user
# ============================================================
@router.get("/me/given", response_model=list[ReviewGivenResponse])
def get_my_given_reviews(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all reviews written by the authenticated user."""
    service = ReviewService(db)
    return service.list_given_reviews(current_user.id, skip=skip, limit=limit)


# ============================================================
#  GET /reviews/service/{listing_id}  →  Reviews by service
# ============================================================
@router.get("/service/{listing_id}", response_model=list[ReviewForServiceResponse])
def get_reviews_by_service(
    listing_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Get all reviews for a specific service listing."""
    service = ReviewService(db)
    return service.list_reviews_by_listing(listing_id, skip=skip, limit=limit)


# ============================================================
#  GET /reviews/{id}  →  Single review details
# ============================================================
@router.get("/{id}", response_model=ReviewResponse)
def get_review(
    id: UUID,
    db: Session = Depends(get_db)
):
    """Fetch details of a single review."""
    service = ReviewService(db)
    return service.get_review(id)


# ============================================================
#  DELETE /reviews/{id}  →  Delete a review
# ============================================================
@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_review(
    id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a review. 
    
    Only the author of the review can perform this action.
    """
    service = ReviewService(db)
    service.delete_review(id, current_user.id)
    return None
