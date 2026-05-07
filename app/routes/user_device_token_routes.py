"""
UserDeviceToken Routes — API endpoints for managing device push notification tokens.
"""

import uuid
from typing import List

from fastapi import APIRouter, Depends, status, Body
from sqlalchemy.orm import Session

from app.core import security
from app.db.session import get_db
from app.models.user import User
from app.schemas.user_device_tokens import UserDeviceTokenResponse, UserDeviceTokenCreate
from app.services.user_device_token_service import UserDeviceTokenService

router = APIRouter(
    prefix="/device-tokens",
    tags=["Device Tokens"],
)

@router.post("/", response_model=UserDeviceTokenResponse, status_code=status.HTTP_201_CREATED)
def register_device_token(
    obj_in: UserDeviceTokenCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(security.get_current_user),
):
    """
    Register a new device token or update an existing one for the current user.
    """
    return UserDeviceTokenService(db).register_token(user_id=current_user.id, obj_in=obj_in)

@router.get("/", response_model=List[UserDeviceTokenResponse])
def list_my_device_tokens(
    active_only: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(security.get_current_user),
):
    """
    Retrieve all registered device tokens for the current authenticated user.
    """
    return UserDeviceTokenService(db).get_user_tokens(user_id=current_user.id, active_only=active_only)

@router.delete("/{token_id}", status_code=status.HTTP_200_OK)
def delete_device_token(
    token_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(security.get_current_user),
):
    """
    Delete a specific device token record.
    """
    return UserDeviceTokenService(db).delete_token(token_id=token_id, user_id=current_user.id)

@router.patch("/deactivate", status_code=status.HTTP_200_OK)
def deactivate_device_token(
    expo_push_token: str = Body(..., embed=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(security.get_current_user),
):
    """
    Deactivate a specific device token (e.g., on logout).
    """
    success = UserDeviceTokenService(db).deactivate_token(expo_push_token=expo_push_token)
    if not success:
        return {"message": "Token not found or already inactive", "success": False}
    return {"message": "Token deactivated successfully", "success": True}
