"""
Review Routes — API endpoints for reviews.
"""

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.review import ReviewCreate, ReviewResponse, ReviewReceivedResponse, ReviewForServiceResponse, ReviewCreateResponse, ReviewGivenResponse
from app.services.review_service import ReviewService

router = APIRouter(prefix="/reviews", tags=["Reviews"])


@router.post("/", response_model=ReviewCreateResponse, status_code=status.HTTP_201_CREATED)
def create_review(
    obj_in: ReviewCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Leave a review for an order.
    
    Validation:
    - Order must be completed.
    - User must be a participant in the order.
    - User cannot review the same order twice.
    """
    service = ReviewService(db)
    return service.create_review(obj_in, current_user.id)


@router.get("/me/received", response_model=List[ReviewReceivedResponse])
def get_my_received_reviews(
    rating: Optional[int] = Query(None, ge=1, le=5, description="Filter by star rating"),
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all reviews received by the authenticated user."""
    service = ReviewService(db)
    return service.list_received_reviews(current_user.id, rating=rating, skip=skip, limit=limit)


@router.get("/me/given", response_model=List[ReviewGivenResponse])
def get_my_given_reviews(
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all reviews written by the authenticated user."""
    service = ReviewService(db)
    return service.list_given_reviews(current_user.id, skip=skip, limit=limit)



@router.get("/service/{listing_id}", response_model=List[ReviewForServiceResponse])
def get_reviews_by_service(
    listing_id: uuid.UUID,
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """Get all reviews for a specific service listing."""
    service = ReviewService(db)
    return service.list_reviews_by_listing(listing_id, skip=skip, limit=limit)


@router.get("/{id}", response_model=ReviewResponse)
def get_review(
    id: uuid.UUID,
    db: Session = Depends(get_db)
):
    """Fetch details of a single review."""
    service = ReviewService(db)
    return service.get_review(id)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_review(
    id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a review. Only the author can perform this action."""
    service = ReviewService(db)
    service.delete_review(id, current_user.id)
    return None
