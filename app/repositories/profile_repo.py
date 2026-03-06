"""
Profile Repository — the *only* layer that talks to the database.

Why a separate repository?
  - Routes shouldn't write raw SQL / ORM queries
  - Services contain business logic but delegate DB work here
  - Makes it easy to swap databases or add caching later
"""

from sqlalchemy.orm import Session
from typing import Optional
from uuid import UUID

from app.models.profile import Profile
from geoalchemy2.elements import WKTElement


def get_profile_by_user_id(db: Session, user_id: UUID) -> Optional[Profile]:
    """Fetch a single profile by user ID (which is the primary key)."""
    return db.query(Profile).filter(Profile.userId == user_id).first()


def get_all_profiles(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    is_banned: Optional[bool] = None,
    seller_status: Optional[str] = None,
    top_selling: bool = False,
    top_rating: bool = False,
) -> list[Profile]:
    """Get a paginated and filtered list of all profiles."""
    query = db.query(Profile)
    if is_banned is not None:
        query = query.filter(Profile.isBanned == is_banned)
    if seller_status is not None:
        query = query.filter(Profile.sellerStatus == seller_status)

    # Sorting logic
    if top_selling:
        query = query.order_by(Profile.sellerCompletedOrdersCount.desc())
    if top_rating:
        query = query.order_by(Profile.sellerRatingAvg.desc(), Profile.sellerRatingCount.desc())

    return query.offset(skip).limit(limit).all()


def create_profile(db: Session, profile: Profile) -> Profile:
    """Insert a new profile into the database."""
    # Note: If the profile object already has WKTElement fields, this works fine.
    # If we were building it from a schema here, we'd need conversion.
    # Usually, Service layer builds the Profile object.
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def update_profile(db: Session, db_profile: Profile, update_data: dict) -> Profile:
    """
    Apply a dict of changes to an existing profile.
    Converts LocationPoint dicts to PostGIS WKTElement before writing.
    """
    for key, value in update_data.items():
        if key in ("last_location_point", "default_location_point") and isinstance(value, dict):
            lat = value.get("latitude")
            lon = value.get("longitude")
            if lat is not None and lon is not None:
                value = WKTElement(f"POINT({lon} {lat})", srid=4326)
        setattr(db_profile, key, value)

    db.commit()
    db.refresh(db_profile)
    return db_profile


def delete_profile(db: Session, db_profile: Profile) -> None:
    """Permanently remove a profile from the database."""
    db.delete(db_profile)
    db.commit()


def increment_seller_orders_count(db: Session, user_id: UUID) -> None:
    """
    Atomically increment the sellerCompletedOrdersCount for the given user's profile.
    """
    db.query(Profile).filter(Profile.userId == user_id).update(
        {Profile.sellerCompletedOrdersCount: Profile.sellerCompletedOrdersCount + 1}
    )
    db.commit()


def update_seller_rating(db: Session, user_id: UUID, new_rating: int) -> None:
    """
    Update sellerRatingAvg and sellerRatingCount for a profile.
    Calculates moving average: ((old_avg * old_count) + new_rating) / (old_count + 1)
    """
    profile = get_profile_by_user_id(db, user_id)
    if not profile:
        return

    # 1. Get current values
    current_count = profile.sellerRatingCount or 0
    current_avg = float(profile.sellerRatingAvg or 0)

    # 2. Calculate new average
    new_count = current_count + 1
    new_avg = ((current_avg * current_count) + new_rating) / new_count

    # 3. Update profile
    profile.sellerRatingAvg = new_avg
    profile.sellerRatingCount = new_count

    db.commit()
    db.refresh(profile)
