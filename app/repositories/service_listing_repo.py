"""
ServiceListing Repository — the *only* layer that talks to the DB for listings.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Optional

import sqlalchemy as sa
from geoalchemy2.elements import WKTElement
from geoalchemy2.functions import ST_DWithin, ST_Distance
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.service_listing import ServiceListing
from app.schemas.services_listing import ServiceListingCreate, ServiceListingUpdate


def _to_wkt(lat: float, lon: float) -> WKTElement:
    """Convert lat/lon → PostGIS WKTElement. Note: PostGIS is (lon lat) order."""
    return WKTElement(f"POINT({lon} {lat})", srid=4326)


class ServiceListingRepository:
    """Class-based repository: instantiated once per request with a DB session."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ── Single-record Lookups ────────────────────────────────────────────────

    def get(self, listing_id: uuid.UUID) -> Optional[ServiceListing]:
        from sqlalchemy.orm import joinedload
        return (
            self.db.query(ServiceListing)
            .options(joinedload(ServiceListing.seller))
            .filter(ServiceListing.id == listing_id)
            .first()
        )

    def get_by_seller_and_id(
        self, listing_id: uuid.UUID, seller_id: uuid.UUID
    ) -> Optional[ServiceListing]:
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
        return (
            self.db.query(ServiceListing)
            .order_by(ServiceListing.createdAt.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_seller(
        self, seller_id: uuid.UUID, skip: int = 0, limit: int = 20
    ) -> list[ServiceListing]:
        return (
            self.db.query(ServiceListing)
            .filter(ServiceListing.sellerId == seller_id)
            .order_by(ServiceListing.createdAt.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_category(
        self, category_id: uuid.UUID, skip: int = 0, limit: int = 20
    ) -> list[ServiceListing]:
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
        self, city_id: uuid.UUID, skip: int = 0, limit: int = 20
    ) -> list[ServiceListing]:
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
        category_id: Optional[uuid.UUID] = None,
        city_id: Optional[uuid.UUID] = None,
        seller_id: Optional[uuid.UUID] = None,
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
    ) -> tuple[list[ServiceListing], int]:
        from app.models.profile import Profile
        from app.models.cities import City
        from app.models.category import Category

        query = self.db.query(ServiceListing)

        if top_selling or top_rating:
            query = query.join(Profile, ServiceListing.sellerId == Profile.userId)
        
        if city_slug:
            query = query.join(City, ServiceListing.cityId == City.id).filter(City.slug == city_slug)
            
        if category_slug:
            query = query.join(Category, ServiceListing.categoryId == Category.id).filter(Category.slug == category_slug)

        if status is not None:
            query = query.filter(ServiceListing.status == status)
        if category_id is not None:
            query = query.filter(ServiceListing.categoryId == category_id)
        if city_id is not None:
            query = query.filter(ServiceListing.cityId == city_id)
        if seller_id is not None:
            query = query.filter(ServiceListing.sellerId == seller_id)
        if is_negotiable is not None:
            query = query.filter(ServiceListing.isNegotiable == is_negotiable)
        if price_type is not None:
            query = query.filter(ServiceListing.priceType == price_type)
        if min_price is not None:
            query = query.filter(
                ServiceListing.priceAmount.isnot(None),
                ServiceListing.priceAmount >= min_price,
            )
        if max_price is not None:
            query = query.filter(
                ServiceListing.priceAmount.isnot(None),
                ServiceListing.priceAmount <= max_price,
            )
        if search is not None:
            term = f"%{search.strip()}%"
            query = query.filter(
                sa.or_(
                    ServiceListing.title.ilike(term),
                    ServiceListing.description.ilike(term),
                )
            )

        total = query.count()

        # Sorting logic
        if top_selling:
            query = query.order_by(Profile.sellerCompletedOrdersCount.desc())
        elif top_rating:
            query = query.order_by(Profile.sellerRatingAvg.desc(), Profile.sellerRatingCount.desc())
        else:
            query = query.order_by(ServiceListing.createdAt.desc())

        results = query.offset(skip).limit(limit).all()
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
        is_negotiable: Optional[bool] = None,
        price_type: Optional[str] = None,
        min_price: Optional[Decimal] = None,
        max_price: Optional[Decimal] = None,
        search: Optional[str] = None,
        top_selling: bool = False,
        top_rating: bool = False,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[tuple[ServiceListing, float]], int]:
        """
        Find active listings where the customer's location falls within
        the service's coverage radius.

        Logic:
            ST_DWithin(service_location, customer_point, serviceRadiusKm * 1000)

        Returns: list of (ServiceListing, distance_km) tuples, sorted closest first.
        """
        from app.models.profile import Profile
        customer_point = _to_wkt(latitude, longitude)

        # Distance in meters from customer to service location point
        distance_m = ST_Distance(
            ServiceListing.service_location,
            customer_point,
        )

        query = self.db.query(
            ServiceListing,
            # Cast ST_Distance (double precision) → Numeric, then divide by 1000 for km
            func.round(
                func.cast(distance_m, sa.Numeric(12, 4)) / 1000, 2
            ).label("distance_km"),
        )

        if top_selling or top_rating:
            query = query.join(Profile, ServiceListing.sellerId == Profile.userId)

        query = query.filter(
            # Only listings that HAVE a location point set
            ServiceListing.service_location.isnot(None),
            # ✅ Check if the service is within the USER'S requested search radius
            ST_DWithin(
                ServiceListing.service_location,
                customer_point,
                radius_km * 1000,  # km → meters (using argument radius_km)
            ),
        )

        if status is not None:
            query = query.filter(ServiceListing.status == status)

        if category_id is not None:
            query = query.filter(ServiceListing.categoryId == category_id)
        if is_negotiable is not None:
            query = query.filter(ServiceListing.isNegotiable == is_negotiable)
        if price_type is not None:
            query = query.filter(ServiceListing.priceType == price_type)
        if min_price is not None:
            query = query.filter(
                ServiceListing.priceAmount.isnot(None),
                ServiceListing.priceAmount >= min_price,
            )
        if max_price is not None:
            query = query.filter(
                ServiceListing.priceAmount.isnot(None),
                ServiceListing.priceAmount <= max_price,
            )
        if search is not None:
            term = f"%{search.strip()}%"
            query = query.filter(
                sa.or_(
                    ServiceListing.title.ilike(term),
                    ServiceListing.description.ilike(term),
                )
            )

        total = query.count()

        # Sorting logic
        if top_selling:
            query = query.order_by(Profile.sellerCompletedOrdersCount.desc())
        elif top_rating:
            query = query.order_by(Profile.sellerRatingAvg.desc(), Profile.sellerRatingCount.desc())
        else:
            query = query.order_by("distance_km")  # default: closest first

        results = query.offset(skip).limit(limit).all()
        return results, total

    # ── Write Operations ─────────────────────────────────────────────────────

    def create(
        self,
        obj_in: ServiceListingCreate,
        seller_id: uuid.UUID,
    ) -> ServiceListing:
        """
        Insert a new listing.
        Converts service_location_point → WKTElement for PostGIS storage.
        """
        # ✅ Convert lat/lon → PostGIS WKTElement if provided
        geo_point = None
        if obj_in.service_location_point is not None:
            geo_point = _to_wkt(
                obj_in.service_location_point.latitude,
                obj_in.service_location_point.longitude,
            )

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
            service_location=geo_point,  # ✅ PostGIS Geography
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
        Apply partial updates. Handles service_location_point → WKTElement conversion.
        """
        update_data = obj_in.model_dump(exclude_unset=True)

        # ✅ Handle geography field separately — needs WKTElement conversion
        location_point = update_data.pop("service_location_point", None)
        if location_point is not None:
            db_obj.service_location = _to_wkt(
                location_point["latitude"],
                location_point["longitude"],
            )

        for field, value in update_data.items():
            setattr(db_obj, field, value)

        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def delete(self, db_obj: ServiceListing) -> None:
        self.db.delete(db_obj)
        self.db.commit()

    # ── Count Helpers ────────────────────────────────────────────────────────

    def count_by_seller(self, seller_id: uuid.UUID) -> int:
        return (
            self.db.query(ServiceListing)
            .filter(ServiceListing.sellerId == seller_id)
            .count()
        )

    def get_by_title_and_description(
        self, title: str, description: Optional[str]
    ) -> Optional[ServiceListing]:
        return (
            self.db.query(ServiceListing)
            .filter(
                ServiceListing.title == title,
                ServiceListing.description == description,
            )
            .first()
        )