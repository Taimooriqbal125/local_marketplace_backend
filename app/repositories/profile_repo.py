"""
Profile Repository — handles direct database operations for the Profile model.
Contains geospatial data bridging and safe mapping from snake_case to mixed case DB columns.
"""

from typing import Optional, List
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session, joinedload, selectinload
from geoalchemy2.elements import WKTElement

from app.models.profile import Profile
from app.models.user import User
from app.schemas.profile import ProfileCreate, ProfileUpdate


# Map snake_case schema keys to camelCase SQLAlchemy model properties
PROFILE_MODEL_MAP = {
    "user_id": "userId",
    "seller_completed_orders_count": "sellerCompletedOrdersCount",
    "photo_url": "photoUrl",
    "seller_rating_avg": "sellerRatingAvg",
    "seller_rating_count": "sellerRatingCount",
    "seller_status": "sellerStatus",
    "is_banned": "isBanned"
}


class ProfileRepository:
    """Class-based repository for Profile database operations."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_user_id(self, user_id: UUID) -> Optional[Profile]:
        """Fetch a single profile by user ID with its user and service listings."""
        stmt = (
            select(Profile)
            .options(
                joinedload(Profile.user),
                selectinload(Profile.user, User.service_listings)
            )
            .where(Profile.userId == user_id)
        )
        return self.db.execute(stmt).scalar_one_or_none()

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
        stmt = select(Profile).options(joinedload(Profile.user))
        
        if is_banned is not None:
            stmt = stmt.where(Profile.isBanned == is_banned)
        if seller_status is not None:
            stmt = stmt.where(Profile.sellerStatus == seller_status)

        # Sorting logic
        if top_selling:
            stmt = stmt.order_by(Profile.sellerCompletedOrdersCount.desc())
        elif top_rating:
            stmt = stmt.order_by(Profile.sellerRatingAvg.desc(), Profile.sellerRatingCount.desc())

        stmt = stmt.offset(skip).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def create(self, obj_in: ProfileCreate) -> Profile:
        """Insert a new profile into the database with explicit mapping."""
        data = obj_in.model_dump()
        db_data = {}
        
        for key, value in data.items():
            model_key = PROFILE_MODEL_MAP.get(key, key)
            db_data[model_key] = value

        # Convert simple dict location to PostGIS WKTElement
        for geokey in ("last_location_point", "default_location_point"):
            val = db_data.get(geokey)
            if isinstance(val, dict):
                lat, lon = val.get("latitude"), val.get("longitude")
                if lat is not None and lon is not None:
                    db_data[geokey] = WKTElement(f"POINT({lon} {lat})", srid=4326)

        db_profile = Profile(**db_data)
        self.db.add(db_profile)
        self.db.commit()
        self.db.refresh(db_profile)
        return db_profile

    def update(self, db_profile: Profile, obj_in: ProfileUpdate) -> Profile:
        """Apply a partial update with explicit key mapping and Geo conversion."""
        update_data = obj_in.model_dump(exclude_unset=True)
        
        for key, value in update_data.items():
            model_key = PROFILE_MODEL_MAP.get(key, key)
            
            # Sub-dictionary to WKTElement conversion
            if key in ("last_location_point", "default_location_point") and isinstance(value, dict):
                lat = value.get("latitude")
                lon = value.get("longitude")
                if lat is not None and lon is not None:
                    value = WKTElement(f"POINT({lon} {lat})", srid=4326)
            
            setattr(db_profile, model_key, value)

        self.db.commit()
        self.db.refresh(db_profile)
        return db_profile

    def delete(self, db_profile: Profile) -> None:
        """Permanently remove a profile from the database."""
        self.db.delete(db_profile)
        self.db.commit()

    def increment_seller_orders_count(self, user_id: UUID) -> None:
        """Atomically increment the sellerCompletedOrdersCount."""
        stmt = (
            update(Profile)
            .where(Profile.userId == user_id)
            .values(sellerCompletedOrdersCount=Profile.sellerCompletedOrdersCount + 1)
        )
        self.db.execute(stmt)
        self.db.commit()

    def update_seller_rating(self, user_id: UUID, new_rating: int) -> None:
        """Update sellerRatingAvg and sellerRatingCount for a profile."""
        profile = self.get_by_user_id(user_id)
        if not profile:
            return

        current_count = profile.sellerRatingCount or 0
        current_avg = float(profile.sellerRatingAvg or 0.0)

        new_count = current_count + 1
        new_avg = ((current_avg * current_count) + new_rating) / new_count

        profile.sellerRatingAvg = new_avg
        profile.sellerRatingCount = new_count

        self.db.commit()
        self.db.refresh(profile)
