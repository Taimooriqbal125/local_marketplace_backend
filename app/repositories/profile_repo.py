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


def get_profile_by_user_id(db: Session, user_id: UUID) -> Optional[Profile]:
    """Fetch a single profile by user ID (which is the primary key)."""
    return db.query(Profile).filter(Profile.userId == user_id).first()


def get_all_profiles(db: Session, skip: int = 0, limit: int = 100) -> list[Profile]:
    """Return a paginated list of profiles."""
    return db.query(Profile).offset(skip).limit(limit).all()


def create_profile(db: Session, profile: Profile) -> Profile:
    """Insert a new profile into the database."""
    db.add(profile)
    db.commit()
    db.refresh(profile)  # reload to get the auto-generated timestamps, etc.
    return profile


def update_profile(db: Session, db_profile: Profile, update_data: dict) -> Profile:
    """
    Apply a dict of changes to an existing profile.
    Only keys present in update_data are updated.
    """
    for key, value in update_data.items():
        setattr(db_profile, key, value)
    db.commit()
    db.refresh(db_profile)
    return db_profile


def delete_profile(db: Session, db_profile: Profile) -> None:
    """Permanently remove a profile from the database."""
    db.delete(db_profile)
    db.commit()
