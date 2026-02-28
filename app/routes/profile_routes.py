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
from app.schemas.profile import ProfileCreate, ProfileUpdate, ProfileResponse
from app.services import profile as profile_service

router = APIRouter(
    prefix="/profiles",
    tags=["Profiles"],
)


@router.post("/", response_model=ProfileResponse, status_code=status.HTTP_201_CREATED)
def create_profile(profile_data: ProfileCreate, db: Session = Depends(get_db)):
    """Register a new profile."""
    return profile_service.create_profile(db, profile_data)


@router.get("/", response_model=list[ProfileResponse])
def get_all_profiles(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Retrieve a list of profiles."""
    return profile_service.get_all_profiles(db, skip=skip, limit=limit)


@router.get("/{user_id}", response_model=ProfileResponse)
def get_profile(user_id: UUID, db: Session = Depends(get_db)):
    """Retrieve a single profile by user ID."""
    return profile_service.get_profile(db, user_id)


@router.put("/{user_id}", response_model=ProfileResponse)
def update_profile(user_id: UUID, profile_data: ProfileUpdate, db: Session = Depends(get_db)):
    """Update profile information. Send only the fields you want to change."""
    return profile_service.update_profile(db, user_id, profile_data)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_profile(user_id: UUID, db: Session = Depends(get_db)):
    """Permanently delete a profile."""
    profile_service.delete_profile(db, user_id)
