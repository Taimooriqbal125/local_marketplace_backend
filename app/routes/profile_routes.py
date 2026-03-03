"""
Profile Routes — API endpoints for profile resource.

This is the *thinnest* layer. A route should:
  1. Accept the request
  2. Call the service
  3. Return the response

All business logic is in the service, all DB work is in the repository.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from uuid import UUID

from app.db.session import get_db
from app.schemas.profile import ProfileCreate, ProfileUpdate, ProfileResponse, LocationPoint
from app.services import profile_service
from app.core.security import get_current_user
from app.models.user import User

router = APIRouter(
    prefix="/profiles",
    tags=["Profiles"],
)


@router.post("/", response_model=ProfileResponse, status_code=status.HTTP_201_CREATED)
def create_profile(
    profile_data: ProfileCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Register a new profile for the authenticated user."""
    # Automatically use the ID of the authenticated user
    profile_data.userId = current_user.id
    return profile_service.create_profile(db, profile_data)


@router.get("/me", response_model=ProfileResponse)
def get_my_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieve the authenticated user's profile."""
    return profile_service.get_profile(db, current_user.id)


@router.patch("/me/location", response_model=ProfileResponse)
def update_my_location(
    location: LocationPoint,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update only the authenticated user's location.
    Optimized for high-frequency updates.
    """
    update_data = ProfileUpdate(last_location_point=location)
    return profile_service.update_profile(db, current_user.id, update_data)


@router.get("/", response_model=list[ProfileResponse])
def get_all_profiles(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Retrieve a list of profiles (Public)."""
    return profile_service.get_all_profiles(db, skip=skip, limit=limit)


@router.get("/{user_id}", response_model=ProfileResponse)
def get_profile(user_id: UUID, db: Session = Depends(get_db)):
    """Retrieve a single profile by user ID (Public)."""
    return profile_service.get_profile(db, user_id)


@router.patch("/{user_id}", response_model=ProfileResponse)
def update_profile(
    user_id: UUID,
    profile_data: ProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update profile information. 
    Users can only update their own profile.
    """
    if user_id != current_user.id:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot update another user's profile"
        )
    return profile_service.update_profile(db, user_id, profile_data)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_profile(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Permanently delete a profile.
    Only the owner or an admin can delete.
    """
    if user_id != current_user.id and not current_user.is_admin:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete another user's profile"
        )
    profile_service.delete_profile(db, user_id)
