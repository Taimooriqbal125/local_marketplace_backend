"""
ServiceListing Repository — the *only* layer that talks to the DB for listings.
Modernized to SQLAlchemy 2.0 select syntax and safely bridges snake_case schemas with camelCase DB colums.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Optional, List, Tuple

import sqlalchemy as sa
from sqlalchemy.orm import Session, joinedload
from geoalchemy2.elements import WKTElement
from geoalchemy2.functions import ST_DWithin, ST_Distance
from sqlalchemy import func, select, or_

from app.models.service_listing import ServiceListing
from app.models.profile import Profile
from app.models.cities import City
from app.models.category import Category
from app.schemas.services_listing import ServiceListingCreate, ServiceListingUpdate


# Map snake_case schema keys to camelCase SQLAlchemy model properties
SL_MODEL_MAP = {
    "seller_id": "sellerId",
    "city_id": "cityId",
    "category_id": "categoryId",
    "price_type": "priceType",
    "price_amount": "priceAmount",
    "is_negotiable": "isNegotiable",
    "service_location": "serviceLocation",  # String name
    "service_radius_km": "serviceRadiusKm",
}

def _to_wkt(lat: float, lon: float) -> WKTElement:
    """Convert lat/lon → PostGIS WKTElement. Note: PostGIS is (lon lat) order."""
    return WKTElement(f"POINT({lon} {lat})", srid=4326)


class ServiceListingRepository:
    """Class-based repository: instantiated once per request with a DB session."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ── Single-record Lookups ────────────────────────────────────────────────

    def get(self, listing_id: uuid.UUID) -> Optional[ServiceListing]:
        stmt = (
            select(ServiceListing)
            .options(joinedload(ServiceListing.seller))
            .where(ServiceListing.id == listing_id)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_seller_and_id(
        self, listing_id: uuid.UUID, seller_id: uuid.UUID
    ) -> Optional[ServiceListing]:
        stmt = select(ServiceListing).where(
            ServiceListing.id == listing_id,
            ServiceListing.sellerId == seller_id
        )
        return self.db.execute(stmt).scalar_one_or_none()

    # ── Collection Queries ───────────────────────────────────────────────────

    def get_all(self, skip: int = 0, limit: int = 20) -> List[ServiceListing]:
        stmt = (
            select(ServiceListing)
            .order_by(ServiceListing.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_by_seller(
        self, seller_id: uuid.UUID, skip: int = 0, limit: int = 20
    ) -> List[ServiceListing]:
        stmt = (
            select(ServiceListing)
            .where(ServiceListing.sellerId == seller_id)
            .order_by(ServiceListing.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_by_category(
        self, category_id: uuid.UUID, skip: int = 0, limit: int = 20
    ) -> List[ServiceListing]:
        stmt = (
            select(ServiceListing)
            .where(
                ServiceListing.categoryId == category_id,
                ServiceListing.status == "active"
            )
            .order_by(ServiceListing.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_by_city(
        self, city_id: uuid.UUID, skip: int = 0, limit: int = 20
    ) -> List[ServiceListing]:
        stmt = (
            select(ServiceListing)
            .where(
                ServiceListing.cityId == city_id,
                ServiceListing.status == "active"
            )
            .order_by(ServiceListing.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_filtered(
        self,
        *,
        status: Optional[str] = None,
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
        skip: int = 0,
        limit: int = 20,
    ) -> Tuple[List[ServiceListing], int]:
        
        stmt = select(ServiceListing)

        if top_selling or top_rating:
            stmt = stmt.join(Profile, ServiceListing.sellerId == Profile.userId)
        
        if city_slug:
            stmt = stmt.join(City, ServiceListing.cityId == City.id).where(City.slug == city_slug)
            
        if category_slug:
            stmt = stmt.join(Category, ServiceListing.categoryId == Category.id).where(Category.slug == category_slug)

        if status is not None:
            stmt = stmt.where(ServiceListing.status == status)
        if category_id is not None:
            stmt = stmt.where(ServiceListing.categoryId == category_id)
        if city_id is not None:
            stmt = stmt.where(ServiceListing.cityId == city_id)
        if seller_id is not None:
            stmt = stmt.where(ServiceListing.sellerId == seller_id)
        if exclude_seller_id is not None:
            stmt = stmt.where(ServiceListing.sellerId != exclude_seller_id)
        if is_negotiable is not None:
            stmt = stmt.where(ServiceListing.isNegotiable == is_negotiable)
        if price_type is not None:
            stmt = stmt.where(ServiceListing.priceType == price_type)
        if min_price is not None:
            stmt = stmt.where(
                ServiceListing.priceAmount.isnot(None),
                ServiceListing.priceAmount >= min_price,
            )
        if max_price is not None:
            stmt = stmt.where(
                ServiceListing.priceAmount.isnot(None),
                ServiceListing.priceAmount <= max_price,
            )
        if search is not None:
            term = f"%{search.strip()}%"
            stmt = stmt.where(
                or_(
                    ServiceListing.title.ilike(term),
                    ServiceListing.description.ilike(term),
                )
            )

        # To get total count, we construct a count query from the whereclauses
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = self.db.execute(count_stmt).scalar() or 0

        # Sorting logic
        if top_selling:
            stmt = stmt.order_by(Profile.sellerCompletedOrdersCount.desc())
        elif top_rating:
            stmt = stmt.order_by(Profile.sellerRatingAvg.desc(), Profile.sellerRatingCount.desc())
        else:
            stmt = stmt.order_by(ServiceListing.created_at.desc())

        results = list(self.db.execute(stmt.offset(skip).limit(limit)).scalars().all())
        return results, total

    # ── ✅ Proximity Search ───────────────────────────────────────────────────

    def get_nearby(
        self,
        *,
        latitude: float,
        longitude: float,
        radius_km: float,
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
        skip: int = 0,
        limit: int = 20,
    ) -> Tuple[List[Tuple[ServiceListing, float]], int]:
        """
        Find active listings where the customer's location falls within
        the service's coverage radius.
        Returns: list of (ServiceListing, distance_km) tuples, sorted closest first.
        """
        customer_point = _to_wkt(latitude, longitude)
        distance_m = ST_Distance(ServiceListing.service_location, customer_point)

        # Select both the listing and the calculated distance_km
        stmt = select(
            ServiceListing,
            func.round(func.cast(distance_m, sa.Numeric(12, 4)) / 1000, 2).label("distance_km")
        )

        if top_selling or top_rating:
            stmt = stmt.join(Profile, ServiceListing.sellerId == Profile.userId)

        stmt = stmt.where(
            ServiceListing.service_location.isnot(None),
            ST_DWithin(ServiceListing.service_location, customer_point, radius_km * 1000)
        )

        if status is not None:
            stmt = stmt.where(ServiceListing.status == status)
        if category_id is not None:
            stmt = stmt.where(ServiceListing.categoryId == category_id)
        if exclude_seller_id is not None:
            stmt = stmt.where(ServiceListing.sellerId != exclude_seller_id)
        if is_negotiable is not None:
            stmt = stmt.where(ServiceListing.isNegotiable == is_negotiable)
        if price_type is not None:
            stmt = stmt.where(ServiceListing.priceType == price_type)
        if min_price is not None:
            stmt = stmt.where(
                ServiceListing.priceAmount.isnot(None),
                ServiceListing.priceAmount >= min_price,
            )
        if max_price is not None:
            stmt = stmt.where(
                ServiceListing.priceAmount.isnot(None),
                ServiceListing.priceAmount <= max_price,
            )
        if search is not None:
            term = f"%{search.strip()}%"
            stmt = stmt.where(
                or_(
                    ServiceListing.title.ilike(term),
                    ServiceListing.description.ilike(term),
                )
            )

        # Count total matches
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = self.db.execute(count_stmt).scalar() or 0

        # Sorting logic
        if top_selling:
            stmt = stmt.order_by(Profile.sellerCompletedOrdersCount.desc())
        elif top_rating:
            stmt = stmt.order_by(Profile.sellerRatingAvg.desc(), Profile.sellerRatingCount.desc())
        else:
            stmt = stmt.order_by(sa.text("distance_km"))

        raw_results = self.db.execute(stmt.offset(skip).limit(limit)).all()
        
        # Unpack Row objects into (ServiceListing, float) tuples
        results = [(row[0], float(row[1])) for row in raw_results]
        return results, total

    # ── Write Operations ─────────────────────────────────────────────────────

    def create(
        self,
        obj_in: ServiceListingCreate,
        seller_id: uuid.UUID,
    ) -> ServiceListing:
        """
        Insert a new listing with manual schema-to-model mapping.
        """
        data = obj_in.model_dump()
        db_data = {"sellerId": seller_id}
        
        for key, value in data.items():
            if key == "service_location_point":
                if isinstance(value, dict):
                    lat, lon = value.get("latitude"), value.get("longitude")
                    if lat is not None and lon is not None:
                        db_data["service_location"] = _to_wkt(lat, lon)
                continue
            
            # Use mapped key if it exists, else use the raw key
            model_key = SL_MODEL_MAP.get(key, key)
            db_data[model_key] = value

        db_obj = ServiceListing(**db_data)
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
        Apply partial updates mapping snake_case seamlessly back to DB model fields.
        """
        update_data = obj_in.model_dump(exclude_unset=True)

        for key, value in update_data.items():
            if key == "service_location_point":
                if isinstance(value, dict):
                    lat, lon = value.get("latitude"), value.get("longitude")
                    if lat is not None and lon is not None:
                        db_obj.service_location = _to_wkt(lat, lon)
                continue
                
            model_key = SL_MODEL_MAP.get(key, key)
            setattr(db_obj, model_key, value)

        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def delete(self, db_obj: ServiceListing) -> None:
        self.db.delete(db_obj)
        self.db.commit()

    # ── Count Helpers ────────────────────────────────────────────────────────

    def count_by_seller(self, seller_id: uuid.UUID) -> int:
        stmt = select(func.count(ServiceListing.id)).where(ServiceListing.sellerId == seller_id)
        return self.db.execute(stmt).scalar() or 0

    def get_by_title_and_description(
        self, title: str, description: Optional[str]
    ) -> Optional[ServiceListing]:
        stmt = select(ServiceListing).where(
            ServiceListing.title == title,
            ServiceListing.description == description
        )
        return self.db.execute(stmt).scalar_one_or_none()