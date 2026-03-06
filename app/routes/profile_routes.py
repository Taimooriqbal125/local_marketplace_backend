"""
Profile Routes — API endpoints for profile resource.

This is the *thinnest* layer. A route should:
  1. Accept the request
  2. Call the service
  3. Return the response

All business logic is in the service, all DB work is in the repository.
"""

from fastapi import APIRouter, Depends, status, Query, HTTPException, File, UploadFile, Form, BackgroundTasks
from sqlalchemy.orm import Session
from uuid import UUID
from typing import Annotated, Optional
import json

from app.db.session import get_db
from app.schemas.profile import ProfileCreate, ProfileUpdate, ProfileResponse, LocationPoint
from app.services import profile_service
from app.core.security import get_current_user
from app.models.user import User

router = APIRouter(
    prefix="/profiles",
    tags=["Profiles"],
)


@router.post("", response_model=ProfileResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=ProfileResponse, status_code=status.HTTP_201_CREATED, include_in_schema=False)
async def create_profile(
    profile_data: Annotated[str, Form(description="JSON string of profile data")],
    photoUrl: Annotated[Optional[UploadFile], File()] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Register a new profile for the authenticated user.
    """
    try:
        data = json.loads(profile_data)
        profile_obj = ProfileCreate(**data)
    except (json.JSONDecodeError, TypeError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid profile_data JSON format: {str(e)}"
        )

    # Automatically use the ID of the authenticated user
    profile_obj.userId = current_user.id
    return await profile_service.create_profile(db, profile_obj, photoUrl)


@router.get("/me", response_model=ProfileResponse)
def get_my_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieve the authenticated user's profile."""
    return profile_service.get_profile(db, current_user.id)


@router.patch("/me/location", response_model=ProfileResponse)
async def update_my_location(
    location: LocationPoint,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update only the authenticated user's location.
    Optimized for high-frequency updates.
    """
    update_data = ProfileUpdate(last_location_point=location)
    return await profile_service.update_profile(db, current_user.id, update_data)


@router.get("/", response_model=list[ProfileResponse])
def get_all_profiles(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    is_banned: Optional[bool] = Query(None, alias="isBanned"),
    seller_status: Optional[str] = Query(None, alias="sellerStatus"),
    top_selling: bool = Query(False, alias="topSelling"),
    top_rating: bool = Query(False, alias="topRating"),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    """
    Retrieve a list of profiles (Public).

    - **skip**: number of records to skip
    - **limit**: max number of records to return
    - **isBanned**: filter by banned status (true/false)
    - **sellerStatus**: [ADMIN ONLY] filter by seller status (active/suspended)
    - **topSelling**: [ADMIN ONLY] sort by top selling
    - **topRating**: [ADMIN ONLY] sort by top rating
    """
    # Authorization check for admin-only filters
    if any([seller_status is not None, top_selling, top_rating]):
        if not current_user or not current_user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins can use these filters or sorting options"
            )

    return profile_service.get_all_profiles(
        db,
        skip=skip,
        limit=limit,
        is_banned=is_banned,
        seller_status=seller_status,
        top_selling=top_selling,
        top_rating=top_rating,
    )


@router.get("/{user_id}", response_model=ProfileResponse)
def get_profile(user_id: UUID, db: Session = Depends(get_db)):
    """Retrieve a single profile by user ID (Public)."""
    return profile_service.get_profile(db, user_id)


@router.patch("/{user_id}", response_model=ProfileResponse)
async def update_profile(
    user_id: UUID,
    profile_data: Annotated[str, Form(description="JSON string of profile update data")],
    photoUrl: Annotated[Optional[UploadFile], File()] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """
    Update profile information. 
    Only the owner or an admin can update.
    """
    if user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot update another user's profile"
        )
    
    try:
        data = json.loads(profile_data)
        update_obj = ProfileUpdate(**data)
    except (json.JSONDecodeError, TypeError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid profile_data JSON format: {str(e)}"
        )

    return await profile_service.update_profile(db, user_id, update_obj, photoUrl, background_tasks)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_profile(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """
    Permanently delete a profile.
    Only the owner or an admin can delete.
    """
    if user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete another user's profile"
        )
    await profile_service.delete_profile(db, user_id, background_tasks)
