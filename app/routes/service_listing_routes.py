"""
ServiceListing Routes — API endpoints for Service Listings.
"""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.services_listing import (
    ServiceListingCreate,
    ServiceListingListResponse,
    ServiceListingResponse,
    ServiceListingUpdate,
)
from app.services.service_listing_service import ServiceListingService

router = APIRouter(
    prefix="/services",
    tags=["Services"],
)


@router.get("/", response_model=ServiceListingListResponse)
def list_listings(
    status: Optional[str] = Query("active", description="Filter by status (default: active)"),
    category_id: Optional[int] = Query(None, description="Filter by category ID"),
    city_id: Optional[uuid.UUID] = Query(None, description="Filter by city ID"),
    seller_id: Optional[uuid.UUID] = Query(None, description="Filter by seller ID"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """
    Browse service listings with optional filters.
    By default, only 'active' listings are returned.
    """
    service = ServiceListingService(db)
    return service.list_listings(
        status=status,
        category_id=category_id,
        city_id=city_id,
        seller_id=seller_id,
        page=page,
        page_size=page_size,
    )


@router.get("/me", response_model=ServiceListingListResponse)
def list_my_listings(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retrieve all listings belonging to the authenticated user.
    Includes drafts, active, paused, etc.
    """
    service = ServiceListingService(db)
    return service.list_my_listings(
        seller_id=current_user.id,
        page=page,
        page_size=page_size,
    )


@router.get("/{listing_id}", response_model=ServiceListingResponse)
def get_listing(
    listing_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """
    Get detailed information for a single service listing.
    """
    service = ServiceListingService(db)
    return service.get_listing(listing_id)


@router.post("/", response_model=ServiceListingResponse, status_code=status.HTTP_201_CREATED)
def create_listing(
    listing_in: ServiceListingCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a new service listing.
    The seller ID is automatically set to the authenticated user's ID.
    """
    service = ServiceListingService(db)
    return service.create_listing(listing_in, seller_id=current_user.id)


@router.patch("/{listing_id}", response_model=ServiceListingResponse)
def update_listing(
    listing_id: uuid.UUID,
    listing_in: ServiceListingUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Update an existing listing.
    Only the owner of the listing can update it.
    """
    service = ServiceListingService(db)
    return service.update_listing(
        listing_id=listing_id,
        obj_in=listing_in,
        current_seller_id=current_user.id,
    )


@router.delete("/{listing_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_listing(
    listing_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Delete a service listing permanently.
    Only the owner of the listing can delete it.
    """
    service = ServiceListingService(db)
    service.delete_listing(listing_id=listing_id, current_seller_id=current_user.id)
    return None


@router.post("/{listing_id}/publish", response_model=ServiceListingResponse)
def publish_listing(
    listing_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Activate a draft listing, making it visible to everyone.
    """
    service = ServiceListingService(db)
    return service.publish_listing(listing_id=listing_id, current_seller_id=current_user.id)


@router.post("/{listing_id}/pause", response_model=ServiceListingResponse)
def pause_listing(
    listing_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Temporarily hide an active listing.
    """
    service = ServiceListingService(db)
    return service.pause_listing(listing_id=listing_id, current_seller_id=current_user.id)
