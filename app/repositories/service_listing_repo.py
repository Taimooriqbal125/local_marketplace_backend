"""
ServiceListing Repository — the *only* layer that talks to the DB for listings.

Responsibilities:
  - Raw ORM queries (select, insert, update, delete)
  - Filtering / pagination helpers
  - No business logic — that belongs in the service layer
"""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.models.service_listing import ServiceListing
from app.schemas.services_listing import ServiceListingCreate, ServiceListingUpdate


class ServiceListingRepository:
    """Class-based repository: instantiated once per request with a DB session."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ── Single-record Lookups ────────────────────────────────────────────────

    def get(self, listing_id: uuid.UUID) -> Optional[ServiceListing]:
        """Fetch a listing by its primary key; returns None if not found."""
        return (
            self.db.query(ServiceListing)
            .filter(ServiceListing.id == listing_id)
            .first()
        )

    def get_by_seller_and_id(
        self, listing_id: uuid.UUID, seller_id: uuid.UUID
    ) -> Optional[ServiceListing]:
        """
        Fetch a listing only if it belongs to a specific seller.
        Used in ownership-guarded update / delete endpoints.
        """
        return (
            self.db.query(ServiceListing)
            .filter(
                ServiceListing.id == listing_id,
                ServiceListing.sellerId == seller_id,
            )
            .first()
        )

    # ── Collection Queries ───────────────────────────────────────────────────

    def get_all(self, skip: int = 0, limit: int = 20) -> list[ServiceListing]:
        """Return a paginated list of ALL listings (admin use)."""
        return (
            self.db.query(ServiceListing)
            .order_by(ServiceListing.createdAt.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_seller(
        self,
        seller_id: uuid.UUID,
        skip: int = 0,
        limit: int = 20,
    ) -> list[ServiceListing]:
        """Return all listings belonging to a specific seller, newest first."""
        return (
            self.db.query(ServiceListing)
            .filter(ServiceListing.sellerId == seller_id)
            .order_by(ServiceListing.createdAt.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_category(
        self,
        category_id: int,
        skip: int = 0,
        limit: int = 20,
    ) -> list[ServiceListing]:
        """Return active listings for a given category, newest first."""
        return (
            self.db.query(ServiceListing)
            .filter(
                ServiceListing.categoryId == category_id,
                ServiceListing.status == "active",
            )
            .order_by(ServiceListing.createdAt.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_city(
        self,
        city_id: uuid.UUID,
        skip: int = 0,
        limit: int = 20,
    ) -> list[ServiceListing]:
        """Return active listings for a given city (MVP filter)."""
        return (
            self.db.query(ServiceListing)
            .filter(
                ServiceListing.cityId == city_id,
                ServiceListing.status == "active",
            )
            .order_by(ServiceListing.createdAt.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_filtered(
        self,
        *,
        status: Optional[str] = None,
        category_id: Optional[int] = None,
        city_id: Optional[uuid.UUID] = None,
        seller_id: Optional[uuid.UUID] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[ServiceListing], int]:
        """
        Flexible multi-filter query used by the public browse endpoint.
        Returns (results, total_count) for pagination metadata.
        """
        query = self.db.query(ServiceListing)

        if status is not None:
            query = query.filter(ServiceListing.status == status)
        if category_id is not None:
            query = query.filter(ServiceListing.categoryId == category_id)
        if city_id is not None:
            query = query.filter(ServiceListing.cityId == city_id)
        if seller_id is not None:
            query = query.filter(ServiceListing.sellerId == seller_id)

        total = query.count()
        results = (
            query.order_by(ServiceListing.createdAt.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return results, total

    # ── Write Operations ─────────────────────────────────────────────────────

    def create(
        self,
        obj_in: ServiceListingCreate,
        seller_id: uuid.UUID,
    ) -> ServiceListing:
        """
        Insert a new listing.
        seller_id is passed explicitly — never taken from the request body.
        """
        db_obj = ServiceListing(
            sellerId=seller_id,
            cityId=obj_in.cityId,
            categoryId=obj_in.categoryId,
            title=obj_in.title,
            description=obj_in.description,
            priceType=obj_in.priceType,
            priceAmount=obj_in.priceAmount,
            isNegotiable=obj_in.isNegotiable,
            serviceLocation=obj_in.serviceLocation,
            serviceRadiusKm=obj_in.serviceRadiusKm,
            status=obj_in.status,
        )
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def update(
        self,
        db_obj: ServiceListing,
        obj_in: ServiceListingUpdate,
    ) -> ServiceListing:
        """
        Apply partial updates to an existing listing.
        Uses model_dump(exclude_unset=True) so only provided fields are touched.
        """
        update_data = obj_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_obj, field, value)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def delete(self, db_obj: ServiceListing) -> None:
        """Hard-delete a listing from the database."""
        self.db.delete(db_obj)
        self.db.commit()

    # ── Count Helpers ────────────────────────────────────────────────────────

    def count_by_seller(self, seller_id: uuid.UUID) -> int:
        """Total number of listings owned by a seller (all statuses)."""
        return (
            self.db.query(ServiceListing)
            .filter(ServiceListing.sellerId == seller_id)
            .count()
        )

    def get_by_title_and_description(
        self, title: str, description: Optional[str]
    ) -> Optional[ServiceListing]:
        """Fetch a listing by its title and description to check for uniqueness."""
        return (
            self.db.query(ServiceListing)
            .filter(
                ServiceListing.title == title,
                ServiceListing.description == description,
            )
            .first()
        )
