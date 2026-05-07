"""
UserDeviceToken Service — encapsulates business logic for managing device tokens.
"""

from __future__ import annotations

import uuid
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.repositories.user_device_token_repo import UserDeviceTokenRepository
from app.schemas.user_device_tokens import UserDeviceTokenCreate, UserDeviceTokenUpdate
from app.models.user_device_tokens import UserDeviceToken


class UserDeviceTokenNotFoundError(HTTPException):
    def __init__(self, detail: str = "Device token not found"):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


class UserDeviceTokenService:
    """Service layer for UserDeviceToken business logic."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = UserDeviceTokenRepository(db)

    def register_token(self, user_id: uuid.UUID, obj_in: UserDeviceTokenCreate) -> UserDeviceToken:
        """
        Register a new device token or update an existing one.
        If the token already exists, update its ownership to the current user and ensure it's active.
        """
        existing_token = self.repo.get_by_token(obj_in.expo_push_token)
        
        if existing_token:
            # Update existing token info and ownership
            update_data = UserDeviceTokenUpdate(
                is_active=True,
                last_used_at=None # Reset or update as needed
            )
            # Manually update fields not in UserDeviceTokenUpdate if needed
            existing_token.userId = user_id
            existing_token.deviceType = obj_in.device_type
            existing_token.deviceName = obj_in.device_name
            
            return self.repo.update(existing_token, update_data)
        
        # Create new token record
        return self.repo.create(user_id, obj_in)

    def get_user_tokens(self, user_id: uuid.UUID, active_only: bool = True) -> List[UserDeviceToken]:
        """Fetch all device tokens for a specific user."""
        return self.repo.get_all_by_user(user_id, active_only=active_only)

    def deactivate_token(self, expo_push_token: str) -> bool:
        """Mark a device token as inactive (e.g., on logout)."""
        return self.repo.deactivate_token(expo_push_token)

    def delete_token(self, token_id: uuid.UUID, user_id: uuid.UUID):
        """Delete a specific device token record, ensuring it belongs to the user."""
        token = self.repo.get(token_id)
        if not token or token.userId != user_id:
            raise UserDeviceTokenNotFoundError()
        
        self.repo.delete(token)
        return {"message": "Device token deleted successfully"}

    def update_activity(self, expo_push_token: str):
        """Update the last used timestamp for a token."""
        return self.repo.update_last_used(expo_push_token)

    def cleanup_inactive_tokens(self, retention_days: int | None = None) -> dict[str, int]:
        """Delete inactive device tokens older than the retention window."""
        from app.core.config import settings
        from datetime import datetime, timezone, timedelta

        if retention_days is None:
            retention_days = settings.DELETE_INACTIVE_DEVICE_TOKENS_IN_DAYS

        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        deleted = self.repo.delete_inactive_tokens(before=cutoff)
        return {"deleted_count": deleted}
