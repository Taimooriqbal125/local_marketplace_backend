"""
Profile Service — business logic for profile operations.
"""

from sqlalchemy.orm import Session
from fastapi import HTTPException, status, UploadFile, BackgroundTasks
from datetime import datetime
from uuid import UUID
from typing import Optional, List

from app.models.profile import Profile
from app.schemas.profile import ProfileCreate, ProfileUpdate
from app.repositories import ProfileRepository, UserRepository
from app.storage.cloudinary_service import cloudinary_service
from app.core.config import settings


class UserNotFoundError(HTTPException):
    def __init__(self, detail: str = "User does not exist"):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


class ProfileNotFoundError(HTTPException):
    def __init__(self, detail: str = "Profile not found"):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


class ProfileConflictError(HTTPException):
    def __init__(self, detail: str = "A profile for this user already exists"):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


class ProfileService:
    """Service layer for Profile business logic."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = ProfileRepository(db)
        self.user_repo = UserRepository(db)

    async def create_profile(self, profile_data: ProfileCreate, file: Optional[UploadFile] = None) -> Profile:
        """Register a new profile."""
        # 1. Check if user exists
        user = self.user_repo.get(profile_data.user_id)
        if not user:
            raise UserNotFoundError()
        
        # 2. Check if profile already exists
        if self.repo.get_by_user_id(profile_data.user_id):
            raise ProfileConflictError()

        # 3. Handle image upload
        if file:
            folder_path = f"{settings.CLOUDINARY_FOLDER}/profiles/{profile_data.user_id}"
            upload_result = await cloudinary_service.upload_image(file, folder=folder_path)
            profile_data.photo_url = upload_result["url"]
            profile_data.cloudinary_public_id = upload_result["public_id"]

        # 4. Set accurate initial tracking data if location is provided
        if profile_data.last_location_point:
            profile_data.last_location_at = datetime.now()

        # 5. Persist to Repository (Repo handles Geo WKT conversions and Model mapping)
        return self.repo.create(profile_data)

    def get_profile(self, user_id: UUID) -> Profile:
        """Get a profile by user ID. Raises 404 if not found."""
        profile = self.repo.get_by_user_id(user_id)
        if not profile:
            raise ProfileNotFoundError()
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
        """Update a profile's info with safe background image removal."""
        db_profile = self.get_profile(user_id)
        
        # 1. Handle image upload and replace logic
        if file:
            folder_path = f"{settings.CLOUDINARY_FOLDER}/profiles/{user_id}"
            
            # Delete old image safely
            if db_profile.cloudinary_public_id:
                if background_tasks:
                    background_tasks.add_task(cloudinary_service.delete_image, db_profile.cloudinary_public_id)
                else:
                    await cloudinary_service.delete_image(db_profile.cloudinary_public_id)

            # Upload new image
            upload_result = await cloudinary_service.upload_image(file, folder=folder_path)
            profile_data.photo_url = upload_result["url"]
            profile_data.cloudinary_public_id = upload_result["public_id"]

        # 2. Maintain freshness of timestamp if location is changed
        if profile_data.last_location_point:
            profile_data.last_location_at = datetime.now()
            
        # 3. Persist to Repository
        return self.repo.update(db_profile, profile_data)

    async def delete_profile(self, user_id: UUID, background_tasks: Optional[BackgroundTasks] = None) -> None:
        """Delete a profile safely removing cloud media dependencies."""
        db_profile = self.get_profile(user_id)
        
        if db_profile.cloudinary_public_id:
            if background_tasks:
                background_tasks.add_task(cloudinary_service.delete_image, db_profile.cloudinary_public_id)
            else:
                await cloudinary_service.delete_image(db_profile.cloudinary_public_id)
        
        self.repo.delete(db_profile)
