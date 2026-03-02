"""
ListingMedia Repository — handles database operations for service listing media.
"""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.models.listing_media import ListingMedia
from app.schemas.listing_media import ListingMediaCreate, ListingMediaUpdate


class ListingMediaRepository:
    """Class-based repository for ListingMedia."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ── Single-record Lookups ────────────────────────────────────────────────

    def get(self, media_id: uuid.UUID) -> Optional[ListingMedia]:
        """Fetch a specific media record by its ID."""
        return (
            self.db.query(ListingMedia)
            .filter(ListingMedia.id == media_id)
            .first()
        )

    # ── Collection Queries ───────────────────────────────────────────────────

    def get_by_listing(self, listing_id: uuid.UUID) -> list[ListingMedia]:
        """Fetch all media associated with a listing, ordered by sortOrder."""
        return (
            self.db.query(ListingMedia)
            .filter(ListingMedia.listingId == listing_id)
            .order_by(ListingMedia.sortOrder.asc(), ListingMedia.createdAt.asc())
            .all()
        )

    # ── Write Operations ─────────────────────────────────────────────────────

    def create(self, obj_in: ListingMediaCreate) -> ListingMedia:
        """Insert a new media record for a listing."""
        db_obj = ListingMedia(
            listingId=obj_in.listingId,
            imageUrl=obj_in.imageUrl,
            sortOrder=obj_in.sortOrder,
        )
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def update(
        self, db_obj: ListingMedia, obj_in: ListingMediaUpdate
    ) -> ListingMedia:
        """Update an existing media record (e.g., change sortOrder or URL)."""
        update_data = obj_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_obj, field, value)
        
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def delete(self, db_obj: ListingMedia) -> None:
        """Remove a media record from the database."""
        self.db.delete(db_obj)
        self.db.commit()
