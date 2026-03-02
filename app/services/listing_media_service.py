"""
ListingMedia Service — business logic layer for service listing media.
"""

from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.repositories.listing_media import ListingMediaRepository
from app.repositories.service_listing_repo import ServiceListingRepository
from app.schemas.listing_media import (
    ListingMediaCreate,
    ListingMediaResponse,
    ListingMediaUpdate,
)


# ---------------------------------------------------------------------------
# Domain Exceptions
# ---------------------------------------------------------------------------

class MediaNotFoundError(HTTPException):
    """Raised when a media ID does not exist."""

    def __init__(self, media_id: uuid.UUID) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Media record '{media_id}' not found.",
        )


class ListingNotFoundError(HTTPException):
    """Raised when a listing ID does not exist."""

    def __init__(self, listing_id: uuid.UUID) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service listing '{listing_id}' not found.",
        )


class ListingForbiddenError(HTTPException):
    """Raised when a user tries to mutate media for a listing they don't own."""

    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to modify this listing's media.",
        )


# ---------------------------------------------------------------------------
# Service Class
# ---------------------------------------------------------------------------

class ListingMediaService:
    """
    Business logic for listing media (images).
    """

    def __init__(self, db: Session) -> None:
        self.repo = ListingMediaRepository(db)
        self.listing_repo = ServiceListingRepository(db)

    def get_media(self, media_id: uuid.UUID) -> ListingMediaResponse:
        """Fetch a single media record. Raises 404 if not found."""
        media = self.repo.get(media_id)
        if not media:
            raise MediaNotFoundError(media_id)
        return ListingMediaResponse.model_validate(media)

    def get_listing_media(self, listing_id: uuid.UUID) -> list[ListingMediaResponse]:
        """Fetch all media for a specific listing."""
        results = self.repo.get_by_listing(listing_id)
        return [ListingMediaResponse.model_validate(r) for r in results]

    def add_media(
        self, obj_in: ListingMediaCreate, current_seller_id: uuid.UUID
    ) -> ListingMediaResponse:
        """
        Add a new image to a listing.
        - 404 if listing doesn't exist
        - 403 if requester is not the owner
        """
        listing = self.listing_repo.get(obj_in.listingId)
        if not listing:
            raise ListingNotFoundError(obj_in.listingId)
        if listing.sellerId != current_seller_id:
            raise ListingForbiddenError()

        media = self.repo.create(obj_in)
        return ListingMediaResponse.model_validate(media)

    def update_media(
        self,
        media_id: uuid.UUID,
        obj_in: ListingMediaUpdate,
        current_seller_id: uuid.UUID,
    ) -> ListingMediaResponse:
        """
        Update media record (e.g. sort order).
        - 404 if media or associated listing doesn't exist
        - 403 if requester is not the listing owner
        """
        media = self.repo.get(media_id)
        if not media:
            raise MediaNotFoundError(media_id)

        listing = self.listing_repo.get(media.listingId)
        if not listing:
            raise ListingNotFoundError(media.listingId)
        if listing.sellerId != current_seller_id:
            raise ListingForbiddenError()

        updated = self.repo.update(media, obj_in)
        return ListingMediaResponse.model_validate(updated)

    def delete_media(
        self, media_id: uuid.UUID, current_seller_id: uuid.UUID
    ) -> None:
        """
        Delete a media record.
        - 404 if media or associated listing doesn't exist
        - 403 if requester is not the listing owner
        """
        media = self.repo.get(media_id)
        if not media:
            raise MediaNotFoundError(media_id)

        listing = self.listing_repo.get(media.listingId)
        if not listing:
            raise ListingNotFoundError(media.listingId)
        if listing.sellerId != current_seller_id:
            raise ListingForbiddenError()

        self.repo.delete(media)
