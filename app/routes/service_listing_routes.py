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
    ServiceListingFilterParams,
    ServiceListingListResponse,
    ServiceListingNearbyListResponse,
    ServiceListingResponse,
    ServiceListingUpdate,
)
from app.services.service_listing_service import ServiceListingService

router = APIRouter(
    prefix="/services",
    tags=["Services"],
)


@router.get("/nearby/me", response_model=ServiceListingNearbyListResponse)
def get_nearby_listings_from_profile(
    radius_km: float = Query(10.0, ge=0.1, le=100.0, description="Search radius in km"),
    filters: ServiceListingFilterParams = Depends(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Find nearby services using your saved profile location.
    No need to send lat/lng — reads from your last_location_point automatically.
    Update your location first via PATCH /profiles/me/location.
    """
    service = ServiceListingService(db)
    return service.search_nearby_from_profile(
        user_id=current_user.id,
        db=db,
        radius_km=radius_km,
        category_id=filters.category_id,
        is_negotiable=filters.is_negotiable,
        price_type=filters.price_type,
        min_price=filters.min_price,
        max_price=filters.max_price,
        search=filters.search,
        page=filters.page,
        page_size=filters.page_size,
    )


@router.get("/nearby", response_model=ServiceListingNearbyListResponse)
def get_nearby_listings(
    latitude: float = Query(..., ge=-90, le=90, description="Your current latitude"),
    longitude: float = Query(..., ge=-180, le=180, description="Your current longitude"),
    radius_km: float = Query(10.0, ge=0.1, le=100.0, description="Search radius in km"),
    filters: ServiceListingFilterParams = Depends(),
    db: Session = Depends(get_db),
):
    """
    Find active service listings near a given location.
    Returns listings whose coverage radius overlaps your position, sorted closest-first.
    """
    service = ServiceListingService(db)
    return service.search_nearby(
        latitude=latitude,
        longitude=longitude,
        radius_km=radius_km,
        category_id=filters.category_id,
        is_negotiable=filters.is_negotiable,
        price_type=filters.price_type,
        min_price=filters.min_price,
        max_price=filters.max_price,
        search=filters.search,
        page=filters.page,
        page_size=filters.page_size,
    )


@router.get("/", response_model=ServiceListingListResponse)
def list_listings(
    listing_status: Optional[str] = Query(
        "active",
        alias="status",
        description="Filter by status (default: active)",
    ),
    city_id: Optional[uuid.UUID] = Query(
        None, alias="cityId", description="Filter by city ID"
    ),
    seller_id: Optional[uuid.UUID] = Query(
        None, alias="sellerId", description="Filter by seller ID"
    ),
    filters: ServiceListingFilterParams = Depends(),
    db: Session = Depends(get_db),
):
    """
    Browse service listings with optional filters.
    By default, only 'active' listings are returned.

    **Filter examples**
    - `?isNegotiable=true` — only negotiable listings
    - `?priceType=fixed` — only fixed-price listings
    - `?minPrice=10&maxPrice=100` — price range
    - `?search=plumbing` — keyword in title or description
    - `?categoryId=3` — specific category
    - `?status=paused` — listings by status
    """
    service = ServiceListingService(db)
    return service.list_listings(
        status=listing_status,
        category_id=filters.category_id,
        city_id=city_id,
        seller_id=seller_id,
        is_negotiable=filters.is_negotiable,
        price_type=filters.price_type,
        min_price=filters.min_price,
        max_price=filters.max_price,
        search=filters.search,
        page=filters.page,
        page_size=filters.page_size,
    )


@router.get("/me", response_model=ServiceListingListResponse)
def list_my_listings(
    listing_status: Optional[str] = Query(
        None,
        alias="status",
        description="Filter by status. Omit to see all (drafts, active, paused, etc.)",
    ),
    filters: ServiceListingFilterParams = Depends(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retrieve listings belonging to the authenticated user.
    Includes all statuses by default (drafts, active, paused, closed).

    **Filter examples**
    - `?status=active` — only your active listings
    - `?status=draft` — only your drafts
    - `?isNegotiable=true` — your negotiable listings
    - `?search=logo` — keyword search in your listings
    """
    service = ServiceListingService(db)
    return service.list_my_listings(
        seller_id=current_user.id,
        status=listing_status,
        category_id=filters.category_id,
        is_negotiable=filters.is_negotiable,
        price_type=filters.price_type,
        min_price=filters.min_price,
        max_price=filters.max_price,
        search=filters.search,
        page=filters.page,
        page_size=filters.page_size,
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


@router.delete("/{listing_id}", status_code=status.HTTP_200_OK)
def delete_listing(
    listing_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Delete a service listing permanently.
    Admin can delete any listing; Sellers can delete only their own.
    """
    service = ServiceListingService(db)
    service.delete_listing(
        listing_id=listing_id, 
        current_user_id=current_user.id,
        is_admin=current_user.is_admin
    )
    return {"message": "Service listing deleted successfully."}


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
