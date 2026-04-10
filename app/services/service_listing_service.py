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
from app.repositories.profile_repo import ProfileRepository
from geoalchemy2.shape import to_shape
from app.schemas.services_listing import (
    ServiceListingCreate,
    ServiceListingListResponse,
    ServiceListingMeListResponse,
    ServiceListingMeResponse,
    ServiceListingProfileSummaryListResponse,
    ServiceListingProfileSummaryResponse,
    ServiceListingPublicListResponse,
    ServiceListingPublicResponse,
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


class InvalidPricingRuleError(HTTPException):
    """Raised when pricing fields violate business rules."""
    def __init__(self, detail: str) -> None:
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
        )


class UserProfileNotFoundError(HTTPException):
    """Raised when searching nearby from a profile that doesn't exist."""
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found. Create a profile first.",
        )


class ProfileLocationMissingError(HTTPException):
    """Raised when a profile tries proximity search without location configuration."""
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No location saved on your profile. Update your location first via PATCH /profiles/me/location",
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

    @staticmethod
    def _validate_pricing_rules(*, price_type: str, is_negotiable: bool) -> None:
        allowed_price_types = {"fixed", "hourly", "daily"}
        if price_type not in allowed_price_types:
            raise InvalidPricingRuleError(
                "price_type must be one of: fixed, hourly, daily."
            )

        if price_type == "fixed" and is_negotiable:
            raise InvalidPricingRuleError(
                "price_type 'fixed' cannot be negotiable. Set is_negotiable to false or use 'hourly'/'daily'."
            )

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
        category_id: Optional[uuid.UUID] = None,
        city_id: Optional[uuid.UUID] = None,
        seller_id: Optional[uuid.UUID] = None,
        exclude_seller_id: Optional[uuid.UUID] = None,
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
    ) -> ServiceListingPublicListResponse:
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
            exclude_seller_id=exclude_seller_id,
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
        return ServiceListingPublicListResponse(
            total=total,
            page=page,
            page_size=page_size,
            results=[ServiceListingPublicResponse.model_validate(r) for r in results],
        )

    def list_profile_listing_summaries(
        self,
        *,
        profile_id: uuid.UUID,
        status: Optional[str] = "active",
        category_id: Optional[uuid.UUID] = None,
        city_id: Optional[uuid.UUID] = None,
        exclude_seller_id: Optional[uuid.UUID] = None,
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
    ) -> ServiceListingProfileSummaryListResponse:
        """
        Return lightweight listing cards for a specific profile/user.
        Useful for profile storefronts where only name/photo/price are needed.
        """
        skip = (page - 1) * page_size
        results, total = self.repo.get_filtered(
            status=status,
            category_id=category_id,
            city_id=city_id,
            seller_id=profile_id,
            exclude_seller_id=exclude_seller_id,
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
        return ServiceListingProfileSummaryListResponse(
            profile_id=profile_id,
            total_services=total,
            page=page,
            page_size=page_size,
            results=[
                ServiceListingProfileSummaryResponse.model_validate(r)
                for r in results
            ],
        )

    def list_my_listings(
        self,
        seller_id: uuid.UUID,
        status: Optional[str] = None,
        category_id: Optional[uuid.UUID] = None,
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
    ) -> ServiceListingMeListResponse:
        """
        Return all listings for the authenticated seller.
        Pass status=None to see all (drafts, paused, active, etc.).
        """
        skip = (page - 1) * page_size
        results, total = self.repo.get_filtered(
            seller_id=seller_id,
            status=status,
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
        return ServiceListingMeListResponse(
            total=total,
            page=page,
            page_size=page_size,
            results=[ServiceListingMeResponse.model_validate(r) for r in results],
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
        self._validate_pricing_rules(
            price_type=obj_in.price_type,
            is_negotiable=obj_in.is_negotiable,
        )

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

        if listing.sellerId != current_seller_id and not is_admin:
            raise ListingForbiddenError()

        if obj_in.status == "banned" and not is_admin:
            raise ListingForbiddenError()

        if listing.status == "banned" and not is_admin:
            raise ListingForbiddenError()

        effective_price_type = (
            obj_in.price_type if obj_in.price_type is not None else listing.priceType
        )
        effective_is_negotiable = (
            obj_in.is_negotiable
            if obj_in.is_negotiable is not None
            else listing.isNegotiable
        )
        self._validate_pricing_rules(
            price_type=effective_price_type,
            is_negotiable=effective_is_negotiable,
        )

        if obj_in.title is not None or obj_in.description is not None:
            new_title = obj_in.title if obj_in.title is not None else listing.title
            new_description = (
                obj_in.description
                if obj_in.description is not None
                else listing.description
            )

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
            page_size=page_size,
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
        category_id: Optional[uuid.UUID] = None,
        exclude_seller_id: Optional[uuid.UUID] = None,
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
            exclude_seller_id=exclude_seller_id,
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
            page_size=page_size,
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
        category_id: Optional[uuid.UUID] = None,
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
        """
        profile = ProfileRepository(db).get_by_user_id(user_id)
        if not profile:
            raise UserProfileNotFoundError()
            
        if profile.last_location_point is None:
            raise ProfileLocationMissingError()
            
        # Convert PostGIS WKBElement → lat/lng
        shape = to_shape(profile.last_location_point)
        return self.search_nearby(
            latitude=shape.y,
            longitude=shape.x,
            radius_km=radius_km,
            status=status,
            category_id=category_id,
            exclude_seller_id=user_id,
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
