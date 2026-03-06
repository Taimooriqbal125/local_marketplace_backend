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
from fastapi import HTTPException, status, UploadFile, BackgroundTasks
from datetime import datetime
from uuid import UUID
from decimal import Decimal
from typing import Optional

from geoalchemy2.elements import WKTElement

from app.models.profile import Profile
from app.models.user import User
from app.schemas.profile import ProfileCreate, ProfileUpdate
from app.repositories import profile_repo
from app.storage.cloudinary_service import cloudinary_service
from app.core.config import settings


def _to_wkt(location_point) -> WKTElement | None:
    """Convert a LocationPoint Pydantic model or dict to a PostGIS WKTElement."""
    if location_point is None:
        return None
    if hasattr(location_point, "latitude"):
        lat, lon = location_point.latitude, location_point.longitude
    elif isinstance(location_point, dict):
        lat, lon = location_point["latitude"], location_point["longitude"]
    else:
        return None
    return WKTElement(f"POINT({lon} {lat})", srid=4326)


async def create_profile(db: Session, profile_data: ProfileCreate, file: Optional[UploadFile] = None) -> Profile:
    """Register a new profile. Raises 400 if profile for user already exists or userId is invalid."""
    # Check if user exists
    user = db.query(User).filter(User.id == profile_data.userId).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User does not exist"
        )
    
    if profile_repo.get_profile_by_user_id(db, profile_data.userId):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A profile for this user already exists"
        )

    # Image upload if file provided
    if file:
        folder_path = f"{settings.CLOUDINARY_FOLDER}/profiles/{profile_data.userId}"
        upload_result = await cloudinary_service.upload_image(file, folder=folder_path)
        profile_data.photoUrl = upload_result["url"]
        profile_data.cloudinary_public_id = upload_result["public_id"]

    new_profile = Profile(
        **profile_data.model_dump(exclude={"last_location_point", "default_location_point", "last_location_at"}),
        last_location_point=_to_wkt(profile_data.last_location_point),
        last_location_at=datetime.now() if profile_data.last_location_point else None,
        default_location_point=_to_wkt(profile_data.default_location_point),
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
    return profile_repo.get_all_profiles(
        db,
        skip=skip,
        limit=limit,
        is_banned=is_banned,
        seller_status=seller_status,
        top_selling=top_selling,
        top_rating=top_rating,
    )


async def update_profile(
    db: Session, 
    user_id: UUID, 
    profile_data: ProfileUpdate, 
    file: Optional[UploadFile] = None,
    background_tasks: Optional[BackgroundTasks] = None
) -> Profile:
    """Update a profile's info. Only fields that are sent get updated."""
    db_profile = get_profile(db, user_id)
    update_data = profile_data.model_dump(exclude_unset=True)
    
    # Image upload if file provided
    if file:
        folder_path = f"{settings.CLOUDINARY_FOLDER}/profiles/{user_id}"
        
        # Delete old image in the background if it exists
        if db_profile.cloudinary_public_id:
            if background_tasks:
                background_tasks.add_task(cloudinary_service.delete_image, db_profile.cloudinary_public_id)
            else:
                await cloudinary_service.delete_image(db_profile.cloudinary_public_id)

        upload_result = await cloudinary_service.upload_image(file, folder=folder_path)
        update_data["photoUrl"] = upload_result["url"]
        update_data["cloudinary_public_id"] = upload_result["public_id"]

    # Handle location fields
    if "last_location_point" in update_data:
        update_data["last_location_at"] = datetime.now()
        update_data["last_location_point"] = _to_wkt(update_data["last_location_point"])
    
    if "default_location_point" in update_data:
        update_data["default_location_point"] = _to_wkt(update_data["default_location_point"])
        
    return profile_repo.update_profile(db, db_profile, update_data)


async def delete_profile(db: Session, user_id: UUID, background_tasks: Optional[BackgroundTasks] = None) -> None:
    """Delete a profile by user ID. Raises 404 if not found."""
    db_profile = get_profile(db, user_id)
    
    # Delete image from Cloudinary in the background
    if db_profile.cloudinary_public_id:
        if background_tasks:
            background_tasks.add_task(cloudinary_service.delete_image, db_profile.cloudinary_public_id)
        else:
            await cloudinary_service.delete_image(db_profile.cloudinary_public_id)
    
    profile_repo.delete_profile(db, db_profile)
