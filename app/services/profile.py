"""
Profile Service — business logic for profile operations.

This layer sits between Routes and Repositories:
  Route  →  Service  →  Repository  →  Database

The service:
  ✅ Validates business rules (e.g. no duplicate profile for user)
  ✅ Raises HTTPExceptions with proper status codes
  ❌ Does NOT write raw DB queries (that's the repo's job)
  ❌ Does NOT know about HTTP requests/responses (that's the route's job)
"""

from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from uuid import UUID
from decimal import Decimal


from app.models.profile import Profile
from app.models.user import User
from app.schemas.profile import ProfileCreate, ProfileUpdate
from app.repositories import profile_repo
from app.repositories import user_repo


def create_profile(db: Session, profile_data: ProfileCreate) -> Profile:
    """Register a new profile. Raises 400 if profile for user already exists or userId is invalid."""
    # Check if user exists
    user = db.query(User).filter(User.id == profile_data.userId).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User does not exist"
        )
    existing = profile_repo.get_profile_by_user_id(db, profile_data.userId)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A profile for this user already exists"
        )
    new_profile = Profile(
        userId=profile_data.userId,
        name=profile_data.name,
        bio=profile_data.bio,
        photoUrl=profile_data.photoUrl,
        sellerStatus=profile_data.sellerStatus,
        lastLocation=profile_data.lastLocation,
        isBanned=profile_data.isBanned,
        sellerRatingAvg=profile_data.sellerRatingAvg or Decimal("0.00"),
        sellerRatingCount=profile_data.sellerRatingCount or 0,
        sellerCompletedOrdersCount=profile_data.sellerCompletedOrdersCount or 0,
    )
    return profile_repo.create_profile(db, new_profile)


def get_profile(db: Session, user_id: UUID) -> Profile:
    """Get a profile by user ID. Raises 404 if not found."""
    profile = profile_repo.get_profile_by_user_id(db, user_id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found"
        )
    return profile


def get_all_profiles(db: Session, skip: int = 0, limit: int = 100) -> list[Profile]:
    """Get a paginated list of all profiles."""
    return profile_repo.get_all_profiles(db, skip=skip, limit=limit)


def update_profile(db: Session, user_id: UUID, profile_data: ProfileUpdate) -> Profile:
    """Update a profile's info. Only fields that are sent get updated."""
    db_profile = get_profile(db, user_id)  # reuse the 404 check from above
    update_data = profile_data.model_dump(exclude_unset=True)
    return profile_repo.update_profile(db, db_profile, update_data)


def delete_profile(db: Session, user_id: UUID) -> None:
    """Delete a profile by user ID. Raises 404 if not found."""
    db_profile = get_profile(db, user_id)  # 404 check
    profile_repo.delete_profile(db, db_profile)
