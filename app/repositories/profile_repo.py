"""
Profile Repository — the *only* layer that talks to the database.
"""

from sqlalchemy.orm import Session, joinedload, selectinload
from typing import Optional, List
from uuid import UUID

from app.models.profile import Profile
from app.models.user import User
from geoalchemy2.elements import WKTElement


class ProfileRepository:
    """Class-based repository for Profile database operations."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_user_id(self, user_id: UUID) -> Optional[Profile]:
        """Fetch a single profile by user ID with its user and service listings."""
        return (
            self.db.query(Profile)
            .options(
                joinedload(Profile.user),
                selectinload(Profile.user, User.service_listings)
            )
            .filter(Profile.userId == user_id)
            .first()
        )

    def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        is_banned: Optional[bool] = None,
        seller_status: Optional[str] = None,
        top_selling: bool = False,
        top_rating: bool = False,
    ) -> List[Profile]:
        """Get a paginated and filtered list of all profiles."""
        query = self.db.query(Profile).options(joinedload(Profile.user))
        if is_banned is not None:
            query = query.filter(Profile.isBanned == is_banned)
        if seller_status is not None:
            query = query.filter(Profile.sellerStatus == seller_status)

        # Sorting logic
        if top_selling:
            query = query.order_by(Profile.sellerCompletedOrdersCount.desc())
        elif top_rating:
            query = query.order_by(Profile.sellerRatingAvg.desc(), Profile.sellerRatingCount.desc())

        return query.offset(skip).limit(limit).all()

    def create(self, profile: Profile) -> Profile:
        """Insert a new profile into the database."""
        self.db.add(profile)
        self.db.commit()
        self.db.refresh(profile)
        return profile

    def update(self, db_profile: Profile, update_data: dict) -> Profile:
        """Apply a dict of changes to an existing profile."""
        for key, value in update_data.items():
            if key in ("last_location_point", "default_location_point") and isinstance(value, dict):
                lat = value.get("latitude")
                lon = value.get("longitude")
                if lat is not None and lon is not None:
                    value = WKTElement(f"POINT({lon} {lat})", srid=4326)
            setattr(db_profile, key, value)

        self.db.commit()
        self.db.refresh(db_profile)
        return db_profile

    def delete(self, db_profile: Profile) -> None:
        """Permanently remove a profile from the database."""
        self.db.delete(db_profile)
        self.db.commit()

    def increment_seller_orders_count(self, user_id: UUID) -> None:
        """Atomically increment the sellerCompletedOrdersCount."""
        self.db.query(Profile).filter(Profile.userId == user_id).update(
            {Profile.sellerCompletedOrdersCount: Profile.sellerCompletedOrdersCount + 1}
        )
        self.db.commit()

    def update_seller_rating(self, user_id: UUID, new_rating: int) -> None:
        """Update sellerRatingAvg and sellerRatingCount for a profile."""
        profile = self.get_by_user_id(user_id)
        if not profile:
            return

        current_count = profile.sellerRatingCount or 0
        current_avg = float(profile.sellerRatingAvg or 0)

        new_count = current_count + 1
        new_avg = ((current_avg * current_count) + new_rating) / new_count

        profile.sellerRatingAvg = new_avg
        profile.sellerRatingCount = new_count

        self.db.commit()
        self.db.refresh(profile)
