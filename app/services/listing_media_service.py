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


class MediaNotFoundError(HTTPException):
    def __init__(self, media_id: uuid.UUID) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Media record '{media_id}' not found.",
        )


class ListingNotFoundError(HTTPException):
    def __init__(self, listing_id: uuid.UUID) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service listing '{listing_id}' not found.",
        )


class ListingForbiddenError(HTTPException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to modify this listing's media.",
        )


class ListingMediaService:
    """Service handling lifecycle and storage of listing media."""

    def __init__(self, db: Session) -> None:
        self.repo = ListingMediaRepository(db)
        self.listing_repo = ServiceListingRepository(db)

    def get_media(self, media_id: uuid.UUID) -> ListingMediaResponse:
        media = self.repo.get(media_id)
        if not media:
            raise MediaNotFoundError(media_id)
        return ListingMediaResponse.model_validate(media)

    def get_listing_media(self, listing_id: uuid.UUID) -> list[ListingMediaResponse]:
        results = self.repo.get_by_listing(listing_id)
        return [ListingMediaResponse.model_validate(r) for r in results]

    def _ensure_listing_permissions(self, listing_id: uuid.UUID, seller_id: uuid.UUID, is_admin: bool = False) -> None:
        """Centralized check for listing existence and permission mapping."""
        listing = self.listing_repo.get(listing_id)
        if not listing:
            raise ListingNotFoundError(listing_id)
        if not is_admin and listing.sellerId != seller_id:
            raise ListingForbiddenError()

    def add_media(
        self, obj_in: ListingMediaCreate, current_seller_id: uuid.UUID
    ) -> ListingMediaResponse:
        self._ensure_listing_permissions(obj_in.listing_id, current_seller_id)
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
        self._ensure_listing_permissions(listing_id, current_seller_id)

        upload_result = await cloudinary_service.upload_image(
            file=file,
            folder=folder or f"marketplace/listings/{listing_id}",
        )

        payload = ListingMediaCreate(
            listing_id=listing_id,
            image_url=upload_result["url"],
            cloudinary_public_id=upload_result["public_id"],
            sort_order=sort_order,
        )
        media = self.repo.create(payload)
        return ListingMediaResponse.model_validate(media)

    def update_media(
        self,
        media_id: uuid.UUID,
        obj_in: ListingMediaUpdate,
        current_seller_id: uuid.UUID,
    ) -> ListingMediaResponse:
        media = self.repo.get(media_id)
        if not media:
            raise MediaNotFoundError(media_id)

        self._ensure_listing_permissions(media.listingId, current_seller_id)

        updated = self.repo.update(media, obj_in)
        return ListingMediaResponse.model_validate(updated)

    async def delete_media(
        self, media_id: uuid.UUID, current_seller_id: uuid.UUID, is_admin: bool = False
    ) -> None:
        media = self.repo.get(media_id)
        if not media:
            raise MediaNotFoundError(media_id)

        self._ensure_listing_permissions(media.listingId, current_seller_id, is_admin)

        if media.cloudinaryPublicId:
            await cloudinary_service.delete_image(media.cloudinaryPublicId)

        self.repo.delete(media)
