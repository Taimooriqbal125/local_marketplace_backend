"""
Profile Service — business logic for profile operations.
"""

from sqlalchemy.orm import Session
from fastapi import HTTPException, status, UploadFile, BackgroundTasks
from datetime import datetime
from uuid import UUID
from decimal import Decimal
from typing import Optional, List

from geoalchemy2.elements import WKTElement

from app.models.profile import Profile
from app.models.user import User
from app.schemas.profile import ProfileCreate, ProfileUpdate
from app.repositories import ProfileRepository, UserRepository
from app.storage.cloudinary_service import cloudinary_service
from app.core.config import settings


class ProfileService:
    """Service layer for Profile business logic."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = ProfileRepository(db)
        self.user_repo = UserRepository(db)

    def _to_wkt(self, location_point) -> WKTElement | None:
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

    async def create_profile(self, profile_data: ProfileCreate, file: Optional[UploadFile] = None) -> Profile:
        """Register a new profile."""
        # 1. Check if user exists
        user = self.user_repo.get(profile_data.userId)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User does not exist"
            )
        
        # 2. Check if profile already exists
        if self.repo.get_by_user_id(profile_data.userId):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A profile for this user already exists"
            )

        # 3. Handle image upload
        if file:
            folder_path = f"{settings.CLOUDINARY_FOLDER}/profiles/{profile_data.userId}"
            upload_result = await cloudinary_service.upload_image(file, folder=folder_path)
            profile_data.photoUrl = upload_result["url"]
            profile_data.cloudinary_public_id = upload_result["public_id"]

        # 4. Create profile object
        new_profile = Profile(
            **profile_data.model_dump(exclude={"last_location_point", "default_location_point", "last_location_at"}),
            last_location_point=self._to_wkt(profile_data.last_location_point),
            last_location_at=datetime.now() if profile_data.last_location_point else None,
            default_location_point=self._to_wkt(profile_data.default_location_point),
        )
        return self.repo.create(new_profile)

    def get_profile(self, user_id: UUID) -> Profile:
        """Get a profile by user ID. Raises 404 if not found."""
        profile = self.repo.get_by_user_id(user_id)
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Profile not found"
            )
        return profile

    def get_all_profiles(
        self,
        skip: int = 0,
        limit: int = 100,
        is_banned: Optional[bool] = None,
        seller_status: Optional[str] = None,
        top_selling: bool = False,
        top_rating: bool = False,
    ) -> List[Profile]:
        """Get a paginated and filtered list of all profiles."""
        return self.repo.get_all(
            skip=skip,
            limit=limit,
            is_banned=is_banned,
            seller_status=seller_status,
            top_selling=top_selling,
            top_rating=top_rating,
        )

    async def update_profile(
        self, 
        user_id: UUID, 
        profile_data: ProfileUpdate, 
        file: Optional[UploadFile] = None,
        background_tasks: Optional[BackgroundTasks] = None
    ) -> Profile:
        """Update a profile's info."""
        db_profile = self.get_profile(user_id)
        update_data = profile_data.model_dump(exclude_unset=True)
        
        if file:
            folder_path = f"{settings.CLOUDINARY_FOLDER}/profiles/{user_id}"
            if db_profile.cloudinary_public_id:
                if background_tasks:
                    background_tasks.add_task(cloudinary_service.delete_image, db_profile.cloudinary_public_id)
                else:
                    await cloudinary_service.delete_image(db_profile.cloudinary_public_id)

            upload_result = await cloudinary_service.upload_image(file, folder=folder_path)
            update_data["photoUrl"] = upload_result["url"]
            update_data["cloudinary_public_id"] = upload_result["public_id"]

        if "last_location_point" in update_data:
            update_data["last_location_at"] = datetime.now()
            update_data["last_location_point"] = self._to_wkt(update_data["last_location_point"])
        
        if "default_location_point" in update_data:
            update_data["default_location_point"] = self._to_wkt(update_data["default_location_point"])
            
        return self.repo.update(db_profile, update_data)

    async def delete_profile(self, user_id: UUID, background_tasks: Optional[BackgroundTasks] = None) -> None:
        """Delete a profile."""
        db_profile = self.get_profile(user_id)
        
        if db_profile.cloudinary_public_id:
            if background_tasks:
                background_tasks.add_task(cloudinary_service.delete_image, db_profile.cloudinary_public_id)
            else:
                await cloudinary_service.delete_image(db_profile.cloudinary_public_id)
        
        self.repo.delete(db_profile)
