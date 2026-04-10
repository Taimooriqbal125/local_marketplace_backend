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
    ReviewByUserResponse,
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
    return await ReviewService(db).create_review(obj_in, current_user.id)


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
    return ReviewService(db).list_all_reviews(current_user=current_user, days=days, skip=skip, limit=limit)


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
    return ReviewService(db).list_received_reviews(current_user.id, rating=rating, skip=skip, limit=limit)


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
    return ReviewService(db).list_given_reviews(current_user.id, skip=skip, limit=limit)


# ============================================================
#  GET /reviews/byuserid/{user_id}  →  Reviews received by user id
# ============================================================
@router.get("/byuserid/{user_id}", response_model=list[ReviewByUserResponse])
def get_reviews_by_user_id(
    user_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    rating: Optional[int] = Query(None, ge=1, le=5, description="Filter by star rating"),
    db: Session = Depends(get_db)
):
    """Get all reviews received by a specific user id (not reviews written by that user)."""
    return ReviewService(db).list_received_reviews(user_id=user_id, rating=rating, skip=skip, limit=limit)


# ============================================================
#  GET /reviews/{id}  →  Single review details
# ============================================================
@router.get("/{id}", response_model=ReviewResponse)
def get_review(
    id: UUID,
    db: Session = Depends(get_db)
):
    """Fetch details of a single review."""
    return ReviewService(db).get_review(id)


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
    ReviewService(db).delete_review(id, current_user.id)
    return None
