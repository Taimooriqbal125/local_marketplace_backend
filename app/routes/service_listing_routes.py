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
    ServiceListingMeListResponse,
    ServiceListingNearbyFilterParams,
    ServiceListingNearbyListResponse,
    ServiceListingResponse,
    ServiceListingDetailResponse,
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
    filters: ServiceListingNearbyFilterParams = Depends(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Find nearby services using your saved profile location.
    No need to send lat/lng — reads from your last_location_point automatically.
    Update your location first via PATCH /profile/me/location.
    """
    service = ServiceListingService(db)
    return service.search_nearby_from_profile(
        user_id=current_user.id,
        db=db,
        radius_km=radius_km,
        status=filters.status,
        is_negotiable=filters.is_negotiable,
        price_type=filters.price_type,
        category_id=filters.category_id,
        top_selling=filters.top_selling,
        top_rating=filters.top_rating,
        page=filters.page,
        page_size=filters.page_size,
    )


@router.get("/nearby", response_model=ServiceListingNearbyListResponse)
def get_nearby_listings(
    latitude: float = Query(..., ge=-90, le=90, description="Your current latitude"),
    longitude: float = Query(..., ge=-180, le=180, description="Your current longitude"),
    radius_km: float = Query(10.0, ge=0.1, le=100.0, description="Search radius in km"),
    filters: ServiceListingNearbyFilterParams = Depends(),
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
        status=filters.status,
        is_negotiable=filters.is_negotiable,
        price_type=filters.price_type,
        category_id=filters.category_id,
        top_selling=filters.top_selling,
        top_rating=filters.top_rating,
        page=filters.page,
        page_size=filters.page_size,
    )


@router.get("/", response_model=ServiceListingListResponse)
def list_listings(
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
    - `?categoryId=UUID` — specific category
    - `?status=pasused` — listings by status
    - `?topSelling=true` — sort by top selling sellers
    - `?topRating=true` — sort by top rated sellers
    """
    service = ServiceListingService(db)
    return service.list_listings(
        status=filters.status,
        category_id=filters.category_id,
        city_id=filters.city_id,
        seller_id=filters.seller_id,
        is_negotiable=filters.is_negotiable,
        price_type=filters.price_type,
        min_price=filters.min_price,
        max_price=filters.max_price,
        search=filters.search,
        top_selling=filters.top_selling,
        top_rating=filters.top_rating,
        city_slug=filters.city_slug,
        category_slug=filters.category_slug,
        page=filters.page,
        page_size=filters.page_size,
    )


@router.get("/me", response_model=ServiceListingMeListResponse)
def list_my_listings(
    filters: ServiceListingFilterParams = Depends(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retrieve listings belonging to the authenticated user.
    Includes 'active' listings by default. Use `?status=` to filter.

    **Filter examples**
    - `?status=active` — only your active listings
    - `?status=draft` — only your drafts
    - `?isNegotiable=true` — your negotiable listings
    - `?search=logo` — keyword search in your listings
    """
    service = ServiceListingService(db)
    # For /me, if status is not explicitly provided, we might want to default to None (all) 
    # instead of "active" if defined that way in the schema.
    # But filters.status defaults to "active" currently.
    return service.list_my_listings(
        seller_id=current_user.id,
        status=filters.status,
        category_id=filters.category_id,
        is_negotiable=filters.is_negotiable,
        price_type=filters.price_type,
        min_price=filters.min_price,
        max_price=filters.max_price,
        search=filters.search,
        top_selling=filters.top_selling,
        top_rating=filters.top_rating,
        city_slug=filters.city_slug,
        category_slug=filters.category_slug,
        page=filters.page,
        page_size=filters.page_size,
    )


@router.get("/{listing_id}", response_model=ServiceListingDetailResponse)
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
        is_admin=current_user.is_admin,
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
