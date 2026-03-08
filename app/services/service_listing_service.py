"""
ServiceListing Service — business logic layer.

Sits between the route handlers and the repository.
Responsibilities:
  - Enforce ownership rules (only a seller can mutate their own listing)
  - Raise meaningful HTTP-friendly exceptions
  - Orchestrate calls to the repository
  - Map ORM objects → Pydantic response schemas
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.repositories.service_listing_repo import ServiceListingRepository
from geoalchemy2.shape import to_shape
from app.schemas.services_listing import (
    ServiceListingCreate,
    ServiceListingListResponse,
    ServiceListingNearbyListResponse,
    ServiceListingNearbyResponse,
    ServiceListingResponse,
    ServiceListingDetailResponse,
    ServiceListingUpdate,
)


# ---------------------------------------------------------------------------
# Domain Exceptions — raised here, caught in route handlers or exception handlers
# ---------------------------------------------------------------------------

class ListingNotFoundError(HTTPException):
    """Raised when a listing ID does not exist in the database."""

    def __init__(self, listing_id: uuid.UUID) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service listing '{listing_id}' not found.",
        )


class ListingForbiddenError(HTTPException):
    """Raised when a user tries to mutate a listing they don't own."""

    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to modify this listing.",
        )


class DuplicateListingError(HTTPException):
    """Raised when a listing with the same title and description already exists."""

    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail="A service listing with this title and description already exists.",
        )


# ---------------------------------------------------------------------------
# Service Class
# ---------------------------------------------------------------------------

class ServiceListingService:
    """
    Business logic for service listings.
    Instantiated per-request via FastAPI dependency injection.
    """

    def __init__(self, db: Session) -> None:
        self.repo = ServiceListingRepository(db)

    # ── Read Operations ──────────────────────────────────────────────────────

    def get_listing(self, listing_id: uuid.UUID) -> ServiceListingDetailResponse:
        """Fetch a single listing by ID. Raises 404 if not found."""
        listing = self.repo.get(listing_id)
        if not listing:
            raise ListingNotFoundError(listing_id)
        return ServiceListingDetailResponse.model_validate(listing)

    def list_listings(
        self,
        *,
        status: Optional[str] = "active",
        category_id: Optional[int] = None,
        city_id: Optional[uuid.UUID] = None,
        seller_id: Optional[uuid.UUID] = None,
        is_negotiable: Optional[bool] = None,
        price_type: Optional[str] = None,
        min_price: Optional[Decimal] = None,
        max_price: Optional[Decimal] = None,
        search: Optional[str] = None,
        top_selling: bool = False,
        top_rating: bool = False,
        city_slug: Optional[str] = None,
        category_slug: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> ServiceListingListResponse:
        """
        Browse listings with optional filters.
        Returns a paginated response with total count metadata.
        """
        skip = (page - 1) * page_size
        results, total = self.repo.get_filtered(
            status=status,
            category_id=category_id,
            city_id=city_id,
            seller_id=seller_id,
            is_negotiable=is_negotiable,
            price_type=price_type,
            min_price=min_price,
            max_price=max_price,
            search=search,
            top_selling=top_selling,
            top_rating=top_rating,
            city_slug=city_slug,
            category_slug=category_slug,
            skip=skip,
            limit=page_size,
        )
        return ServiceListingListResponse(
            total=total,
            page=page,
            pageSize=page_size,
            results=[ServiceListingResponse.model_validate(r) for r in results],
        )

    def list_my_listings(
        self,
        seller_id: uuid.UUID,
        status: Optional[str] = None,
        category_id: Optional[int] = None,
        is_negotiable: Optional[bool] = None,
        price_type: Optional[str] = None,
        min_price: Optional[Decimal] = None,
        max_price: Optional[Decimal] = None,
        search: Optional[str] = None,
        top_selling: bool = False,
        top_rating: bool = False,
        city_slug: Optional[str] = None,
        category_slug: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> ServiceListingListResponse:
        """
        Return all listings for the authenticated seller.
        Pass status=None to see all (drafts, paused, active, etc.).
        """
        skip = (page - 1) * page_size
        results, total = self.repo.get_filtered(
            seller_id=seller_id,
            status=status,            # seller can filter by their own status
            category_id=category_id,
            is_negotiable=is_negotiable,
            price_type=price_type,
            min_price=min_price,
            max_price=max_price,
            search=search,
            top_selling=top_selling,
            top_rating=top_rating,
            city_slug=city_slug,
            category_slug=category_slug,
            skip=skip,
            limit=page_size,
        )
        return ServiceListingListResponse(
            total=total,
            page=page,
            pageSize=page_size,
            results=[ServiceListingResponse.model_validate(r) for r in results],
        )

    # ── Write Operations ─────────────────────────────────────────────────────

    def create_listing(
        self,
        obj_in: ServiceListingCreate,
        seller_id: uuid.UUID,
    ) -> ServiceListingResponse:
        """
        Create a new service listing for the authenticated seller.
        seller_id is always taken from the auth context, never from the body.
        Checks for uniqueness of title and description.
        """
        existing = self.repo.get_by_title_and_description(
            title=obj_in.title, description=obj_in.description
        )
        if existing:
            raise DuplicateListingError()

        listing = self.repo.create(obj_in, seller_id=seller_id)
        return ServiceListingResponse.model_validate(listing)

    def update_listing(
        self,
        listing_id: uuid.UUID,
        obj_in: ServiceListingUpdate,
        current_seller_id: uuid.UUID,
        is_admin: bool = False,
    ) -> ServiceListingResponse:
        """
        Partially update a listing.
        - 404 if listing doesn't exist
        - 403 if the requester is not the owner (unless admin)
        - 403 if trying to set status to 'banned' or modify a 'banned' listing without admin
        """
        listing = self.repo.get(listing_id)
        if not listing:
            raise ListingNotFoundError(listing_id)

        # ✅ Basic permission: Owner or Admin
        if listing.sellerId != current_seller_id and not is_admin:
            raise ListingForbiddenError()

        # ✅ Security Rule: Only admin can set 'banned' status
        if obj_in.status == "banned" and not is_admin:
            raise ListingForbiddenError()

        # ✅ Security Rule: If already banned, only admin can edit/unban
        if listing.status == "banned" and not is_admin:
            raise ListingForbiddenError()

        # Check for uniqueness if title or description is being updated
        if obj_in.title is not None or obj_in.description is not None:
            new_title = obj_in.title if obj_in.title is not None else listing.title
            new_description = (
                obj_in.description
                if obj_in.description is not None
                else listing.description
            )

            # Only check if the content actually changed
            if new_title != listing.title or new_description != listing.description:
                existing = self.repo.get_by_title_and_description(
                    title=new_title, description=new_description
                )
                if existing:
                    raise DuplicateListingError()

        updated = self.repo.update(listing, obj_in)
        return ServiceListingResponse.model_validate(updated)

    def delete_listing(
        self,
        listing_id: uuid.UUID,
        current_user_id: uuid.UUID,
        is_admin: bool = False,
    ) -> None:
        """
        Hard-delete a listing.
        - 404 if listing doesn't exist
        - 403 if the requester is not the owner (unless admin)
        """
        listing = self.repo.get(listing_id)
        if not listing:
            raise ListingNotFoundError(listing_id)
        
        # ✅ Allow deletion if user is the owner OR if they are an admin
        if listing.sellerId != current_user_id and not is_admin:
            raise ListingForbiddenError()
            
        self.repo.delete(listing)

    # ── Admin Operations ─────────────────────────────────────────────────────

    def admin_get_all(
        self, page: int = 1, page_size: int = 20
    ) -> ServiceListingListResponse:
        """Admin-only: list ALL listings regardless of status."""
        skip = (page - 1) * page_size
        results, total = self.repo.get_filtered(
            status=None,
            skip=skip,
            limit=page_size,
        )
        return ServiceListingListResponse(
            total=total,
            page=page,
            pageSize=page_size,
            results=[ServiceListingResponse.model_validate(r) for r in results],
        )

    def admin_ban_listing(self, listing_id: uuid.UUID) -> ServiceListingResponse:
        """Admin-only: mark a listing as 'banned'."""
        listing = self.repo.get(listing_id)
        if not listing:
            raise ListingNotFoundError(listing_id)
        update = ServiceListingUpdate(status="banned")
        updated = self.repo.update(listing, update)
        return ServiceListingResponse.model_validate(updated)

    # ── Nearby Search ────────────────────────────────────────────────────────

    def search_nearby(
        self,
        *,
        latitude: float,
        longitude: float,
        radius_km: float = 10.0,
        status: Optional[str] = "active",
        category_id: Optional[int] = None,
        is_negotiable: Optional[bool] = None,
        price_type: Optional[str] = None,
        min_price: Optional[Decimal] = None,
        max_price: Optional[Decimal] = None,
        search: Optional[str] = None,
        top_selling: bool = False,
        top_rating: bool = False,
        page: int = 1,
        page_size: int = 20,
    ) -> ServiceListingNearbyListResponse:
        """
        Find active listings whose coverage radius includes the given point.
        Returns results sorted closest-first with distance_km attached.
        """
        skip = (page - 1) * page_size
        results, total = self.repo.get_nearby(
            latitude=latitude,
            longitude=longitude,
            radius_km=radius_km,
            status=status,
            category_id=category_id,
            is_negotiable=is_negotiable,
            price_type=price_type,
            min_price=min_price,
            max_price=max_price,
            search=search,
            top_selling=top_selling,
            top_rating=top_rating,
            skip=skip,
            limit=page_size,
        )
        items = [
            ServiceListingNearbyResponse.model_validate({
                **listing.__dict__,
                "distance_km": float(distance_km),
                "city": listing.city,
                "category": listing.category,
                "seller": listing.seller,
                "media": listing.media
            })
            for listing, distance_km in results
        ]
        return ServiceListingNearbyListResponse(
            total=total,
            page=page,
            pageSize=page_size,
            radius_km=radius_km,
            results=items,
        )

    def search_nearby_from_profile(
        self,
        *,
        user_id: uuid.UUID,
        db: Session,
        radius_km: float = 10.0,
        status: Optional[str] = "active",
        category_id: Optional[int] = None,
        is_negotiable: Optional[bool] = None,
        price_type: Optional[str] = None,
        min_price: Optional[Decimal] = None,
        max_price: Optional[Decimal] = None,
        search: Optional[str] = None,
        top_selling: bool = False,
        top_rating: bool = False,
        page: int = 1,
        page_size: int = 20,
    ) -> ServiceListingNearbyListResponse:
        """
        Same as search_nearby but reads lat/lng from the user's
        profile.last_location_point automatically.
        Raises 404 if profile not found, 400 if location not set.
        """
        profile = get_profile_by_user_id(db, user_id)
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Profile not found. Create a profile first.",
            )
        if profile.last_location_point is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No location saved on your profile. Update your location first via PATCH /profile/me/location",
            )
        # Convert PostGIS WKBElement → lat/lng
        shape = to_shape(profile.last_location_point)
        return self.search_nearby(
            latitude=shape.y,
            longitude=shape.x,
            radius_km=radius_km,
            status=status,
            category_id=category_id,
            is_negotiable=is_negotiable,
            price_type=price_type,
            min_price=min_price,
            max_price=max_price,
            search=search,
            top_selling=top_selling,
            top_rating=top_rating,
            page=page,
            page_size=page_size,
        )
