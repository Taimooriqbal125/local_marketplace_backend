"""
ListingMedia Routes — API endpoints for managing service listing media.
"""

import uuid
# removed incorrect typing import

from fastapi import APIRouter, Depends, status
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


@router.post("/", response_model=ListingMediaResponse, status_code=status.HTTP_201_CREATED)
def add_media(
    obj_in: ListingMediaCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(security.get_current_user),
):
    """
    Add a new image to a service listing.
    Only the listing owner can add media.
    """
    service = ListingMediaService(db)
    return service.add_media(obj_in, current_seller_id=current_user.id)


@router.get("/listing/{listing_id}", response_model=list[ListingMediaResponse])
def get_listing_media(
    listing_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """Fetch all media associated with a specific listing."""
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


@router.delete("/{media_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_media(
    media_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(security.get_current_user),
):
    """
    Delete a media record.
    Only the listing owner can delete its media.
    """
    service = ListingMediaService(db)
    service.delete_media(media_id, current_seller_id=current_user.id)
