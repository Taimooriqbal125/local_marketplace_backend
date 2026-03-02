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
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.repositories.service_listing_repo import ServiceListingRepository
from app.schemas.services_listing import (
    ServiceListingCreate,
    ServiceListingListResponse,
    ServiceListingResponse,
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

    def get_listing(self, listing_id: uuid.UUID) -> ServiceListingResponse:
        """Fetch a single listing by ID. Raises 404 if not found."""
        listing = self.repo.get(listing_id)
        if not listing:
            raise ListingNotFoundError(listing_id)
        return ServiceListingResponse.model_validate(listing)

    def list_listings(
        self,
        *,
        status: Optional[str] = "active",
        category_id: Optional[int] = None,
        city_id: Optional[uuid.UUID] = None,
        seller_id: Optional[uuid.UUID] = None,
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
        page: int = 1,
        page_size: int = 20,
    ) -> ServiceListingListResponse:
        """
        Return all listings for the authenticated seller (all statuses).
        Uses get_filtered with no status filter so drafts/paused are included.
        """
        skip = (page - 1) * page_size
        results, total = self.repo.get_filtered(
            seller_id=seller_id,
            status=None,            # seller can see their own non-active listings
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
    ) -> ServiceListingResponse:
        """
        Partially update a listing.
        - 404 if listing doesn't exist
        - 403 if the requester is not the owner
        """
        listing = self.repo.get(listing_id)
        if not listing:
            raise ListingNotFoundError(listing_id)
        if listing.sellerId != current_seller_id:
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
        current_seller_id: uuid.UUID,
    ) -> None:
        """
        Hard-delete a listing.
        - 404 if listing doesn't exist
        - 403 if the requester is not the owner
        """
        listing = self.repo.get(listing_id)
        if not listing:
            raise ListingNotFoundError(listing_id)
        if listing.sellerId != current_seller_id:
            raise ListingForbiddenError()
        self.repo.delete(listing)

    # ── Status Transitions ───────────────────────────────────────────────────

    def publish_listing(
        self,
        listing_id: uuid.UUID,
        current_seller_id: uuid.UUID,
    ) -> ServiceListingResponse:
        """
        Transition a listing from 'draft' → 'active'.
        Only the owner can publish their own listing.
        """
        listing = self.repo.get(listing_id)
        if not listing:
            raise ListingNotFoundError(listing_id)
        if listing.sellerId != current_seller_id:
            raise ListingForbiddenError()
        if listing.status == "active":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Listing is already active.",
            )
        update = ServiceListingUpdate(status="active")
        updated = self.repo.update(listing, update)
        return ServiceListingResponse.model_validate(updated)

    def pause_listing(
        self,
        listing_id: uuid.UUID,
        current_seller_id: uuid.UUID,
    ) -> ServiceListingResponse:
        """
        Transition a listing to 'paused' (temporarily hidden).
        Only the owner can pause their own listing.
        """
        listing = self.repo.get(listing_id)
        if not listing:
            raise ListingNotFoundError(listing_id)
        if listing.sellerId != current_seller_id:
            raise ListingForbiddenError()
        if listing.status not in ("active", "draft"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot pause a listing with status '{listing.status}'.",
            )
        update = ServiceListingUpdate(status="paused")
        updated = self.repo.update(listing, update)
        return ServiceListingResponse.model_validate(updated)

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
