"""
ListingMedia Service — business logic layer for service listing media.
"""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.repositories.listing_media import ListingMediaRepository
from app.repositories.service_listing_repo import ServiceListingRepository
from app.schemas.listing_media import (
    ListingMediaCreate,
    ListingMediaResponse,
    ListingMediaUpdate,
)
from app.storage.cloudinary_service import cloudinary_service


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
        Add a new image record to a listing using an already-hosted URL.
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

    async def upload_and_add_media(
        self,
        listing_id: uuid.UUID,
        file: UploadFile,
        sort_order: int,
        current_seller_id: uuid.UUID,
        folder: Optional[str] = None,
    ) -> ListingMediaResponse:
        """
        Upload an image file to Cloudinary, then persist a ListingMedia record.

        Steps
        -----
        1. Verify listing exists and belongs to the caller.
        2. Upload the file to Cloudinary (async, non-blocking).
        3. Save the returned URL + public_id in the database.

        Parameters
        ----------
        listing_id        : UUID of the target service listing.
        file              : Raw UploadFile from the multipart request.
        sort_order        : Display order (0 = primary thumbnail).
        current_seller_id : ID of the authenticated user.
        folder            : Optional Cloudinary sub-folder override.
        """
        # 1. Auth / existence check
        listing = self.listing_repo.get(listing_id)
        if not listing:
            raise ListingNotFoundError(listing_id)
        if listing.sellerId != current_seller_id:
            raise ListingForbiddenError()

        # 2. Upload to Cloudinary
        upload_result = await cloudinary_service.upload_image(
            file=file,
            folder=folder or f"marketplace/listings/{listing_id}",
        )

        # 3. Persist the media record
        payload = ListingMediaCreate(
            listingId=listing_id,
            imageUrl=upload_result["url"],
            cloudinaryPublicId=upload_result["public_id"],
            sortOrder=sort_order,
        )
        media = self.repo.create(payload)
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

    async def delete_media(
        self, media_id: uuid.UUID, current_seller_id: uuid.UUID, is_admin: bool = False
    ) -> None:
        """
        Delete a media record and its corresponding Cloudinary asset (if any).
        - 404 if media or associated listing doesn't exist
        - 403 if requester is not the listing owner (and not admin)
        """
        media = self.repo.get(media_id)
        if not media:
            raise MediaNotFoundError(media_id)

        listing = self.listing_repo.get(media.listingId)
        if not listing:
            raise ListingNotFoundError(media.listingId)
        
        # Admin can delete anything, otherwise check ownership
        if not is_admin and listing.sellerId != current_seller_id:
            raise ListingForbiddenError()

        # Remove asset from Cloudinary first (best-effort; DB row is removed regardless)
        if media.cloudinaryPublicId:
            await cloudinary_service.delete_image(media.cloudinaryPublicId)

        self.repo.delete(media)
