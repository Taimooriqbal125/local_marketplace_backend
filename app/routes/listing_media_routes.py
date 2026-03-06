"""
ListingMedia Routes — API endpoints for managing service listing media.
"""

import uuid

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.core import security
from app.db.session import get_db
from app.models.user import User
from app.schemas.listing_media import (
    ListingMediaCreate,
    ListingMediaResponse,
    ListingMediaUpdate,
)
from app.services.listing_media_service import ListingMediaService

router = APIRouter(
    prefix="/listingmedia",
    tags=["Listing Media"],
)


# ── Upload (file → Cloudinary → DB) ──────────────────────────────────────────

@router.post(
    "/{listing_id}/upload",
    response_model=ListingMediaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload an image file for a listing",
)
async def upload_media(
    listing_id: uuid.UUID,
    file: UploadFile = File(..., description="Image file (JPEG / PNG / WebP / GIF, max 5 MB)"),
    sort_order: int = Query(default=0, ge=0, description="Display order (0 = primary thumbnail)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(security.get_current_user),
):
    """
    Upload an image directly to Cloudinary and create a ListingMedia record.

    - Validates file type (JPEG, PNG, WebP, GIF) and size (≤ 5 MB).
    - Stores the image under `marketplace/listings/{listing_id}/` in Cloudinary.
    - Returns the new media record including the hosted image URL.
    - Only the listing owner can upload media.
    """
    service = ListingMediaService(db)
    return await service.upload_and_add_media(
        listing_id=listing_id,
        file=file,
        sort_order=sort_order,
        current_seller_id=current_user.id,
    )


# ── Manual create (URL already known) ────────────────────────────────────────

@router.post(
    "/",
    response_model=ListingMediaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Attach an already-hosted image URL to a listing",
)
def add_media(
    obj_in: ListingMediaCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(security.get_current_user),
):
    """
    Add a media record using an existing image URL (e.g. from a prior Cloudinary upload
    or an external CDN).  For direct file uploads use POST /{listing_id}/upload instead.
    Only the listing owner can add media.
    """
    service = ListingMediaService(db)
    return service.add_media(obj_in, current_seller_id=current_user.id)


# ── Read ──────────────────────────────────────────────────────────────────────

@router.get("/listing/{listing_id}", response_model=list[ListingMediaResponse])
def get_listing_media(
    listing_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """Fetch all media associated with a specific listing, ordered by sort_order."""
    service = ListingMediaService(db)
    return service.get_listing_media(listing_id)


@router.get("/{media_id}", response_model=ListingMediaResponse)
def get_media(
    media_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """Fetch a single media record by ID."""
    service = ListingMediaService(db)
    return service.get_media(media_id)


# ── Update ────────────────────────────────────────────────────────────────────

@router.patch("/{media_id}", response_model=ListingMediaResponse)
def update_media(
    media_id: uuid.UUID,
    obj_in: ListingMediaUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(security.get_current_user),
):
    """
    Update a media record (e.g. change sortOrder or imageUrl).
    Only the listing owner can update its media.
    """
    service = ListingMediaService(db)
    return service.update_media(media_id, obj_in, current_seller_id=current_user.id)


# ── Delete ────────────────────────────────────────────────────────────────────

@router.delete("/{media_id}", status_code=status.HTTP_200_OK)
async def delete_media(
    media_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(security.get_current_user),
):
    """
    Delete a media record and its Cloudinary asset (if one exists).
    
    Permissions:
    - Listing Owner: Can delete.
    - Admin: Can delete any media.
    """
    service = ListingMediaService(db)
    await service.delete_media(
        media_id=media_id, 
        current_seller_id=current_user.id, 
        is_admin=current_user.is_admin
    )
    return {"success": True, "message": "Media deleted successfully"}

