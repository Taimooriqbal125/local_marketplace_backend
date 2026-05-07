"""
UserDeviceToken Repository — handles database operations for user device tokens.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.user_device_tokens import UserDeviceToken
from app.schemas.user_device_tokens import UserDeviceTokenCreate, UserDeviceTokenUpdate


USER_DEVICE_TOKEN_MODEL_MAP = {
    "user_id": "userId",
    "expo_push_token": "expo_push_token",
    "device_type": "deviceType",
    "device_name": "deviceName",
    "is_active": "isActive",
    "last_used_at": "lastUsedAt",
}

class UserDeviceTokenRepository:
    """Class-based repository for UserDeviceToken."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ── Single-record Lookups ────────────────────────────────────────────────

    def get(self, token_id: uuid.UUID) -> Optional[UserDeviceToken]:
        """Fetch a specific device token record by its primary key."""
        return (
            self.db.query(UserDeviceToken)
            .filter(UserDeviceToken.id == token_id)
            .first()
        )

    def get_by_token(self, expo_push_token: str) -> Optional[UserDeviceToken]:
        """Fetch a specific device token record by the token string."""
        return (
            self.db.query(UserDeviceToken)
            .filter(UserDeviceToken.expo_push_token == expo_push_token)
            .first()
        )

    # ── Collection Queries ───────────────────────────────────────────────────

    def get_all_by_user(
        self, user_id: uuid.UUID, active_only: bool = True
    ) -> list[UserDeviceToken]:
        """Return all device tokens for a specific user."""
        query = self.db.query(UserDeviceToken).filter(UserDeviceToken.userId == user_id)
        if active_only:
            query = query.filter(UserDeviceToken.isActive == True)
        return query.all()

    # ── Write Operations ─────────────────────────────────────────────────────

    def create(self, user_id: uuid.UUID, obj_in: UserDeviceTokenCreate) -> UserDeviceToken:
        """Insert a new device token."""
        data = obj_in.model_dump()
        db_data = {"userId": user_id, "isActive": True}
        for key, value in data.items():
            model_key = USER_DEVICE_TOKEN_MODEL_MAP.get(key, key)
            db_data[model_key] = value

        db_obj = UserDeviceToken(**db_data)
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def update(self, db_obj: UserDeviceToken, obj_in: UserDeviceTokenUpdate) -> UserDeviceToken:
        """Apply updates to an existing device token record."""
        update_data = obj_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            model_field = USER_DEVICE_TOKEN_MODEL_MAP.get(field, field)
            setattr(db_obj, model_field, value)
        
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def delete(self, db_obj: UserDeviceToken) -> None:
        """Remove a device token record."""
        self.db.delete(db_obj)
        self.db.commit()

    def deactivate_token(self, expo_push_token: str) -> bool:
        """Deactivate a specific token (e.g., on logout or invalid token error)."""
        db_obj = self.get_by_token(expo_push_token)
        if db_obj:
            db_obj.isActive = False
            self.db.commit()
            return True
        return False

    def update_last_used(self, expo_push_token: str) -> bool:
        """Update the last used timestamp for a token."""
        db_obj = self.get_by_token(expo_push_token)
        if db_obj:
            db_obj.lastUsedAt = datetime.now(timezone.utc)
            self.db.commit()
            return True
        return False

    def delete_inactive_tokens(self, before: datetime) -> int:
        """Delete device tokens that are inactive and older than the cutoff.

        - If `lastUsedAt` is present use it; otherwise fall back to `created_at`.
        """
        # Delete tokens where isActive is False and (lastUsedAt < before OR (lastUsedAt IS NULL and created_at < before))
        deleted_count = (
            self.db.query(UserDeviceToken)
            .filter(
                UserDeviceToken.isActive.is_(False),
                (
                    (UserDeviceToken.lastUsedAt.is_not(None) & (UserDeviceToken.lastUsedAt < before))
                    | ((UserDeviceToken.lastUsedAt.is_(None)) & (UserDeviceToken.created_at < before))
                ),
            )
            .delete(synchronize_session=False)
        )
        self.db.commit()
        return deleted_count
