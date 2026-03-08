"""
Notification Repository — handles database operations for notifications.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.notification import Notification
from app.schemas.notification import NotificationCreate, NotificationUpdate
from app.core.config import settings

class NotificationRepository:
    """Class-based repository for Notification."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ── Single-record Lookups ────────────────────────────────────────────────

    def get(self, notification_id: uuid.UUID) -> Optional[Notification]:
        """Fetch a specific notification by its primary key."""
        return (
            self.db.query(Notification)
            .filter(Notification.id == notification_id)
            .first()
        )

    # ── Collection Queries ───────────────────────────────────────────────────

    def get_all_by_user(
        self, user_id: uuid.UUID, skip: int = 0, limit: int = 20
    ) -> list[Notification]:
        """Return all notifications for a specific user, sorted by most recent."""
        return (
            self.db.query(Notification)
            .filter(Notification.userId == user_id)
            .order_by(Notification.createdAt.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_unread_by_user(
        self, user_id: uuid.UUID, skip: int = 0, limit: int = 20
    ) -> list[Notification]:
        """Return only unread notifications for a specific user."""
        return (
            self.db.query(Notification)
            .filter(Notification.userId == user_id, Notification.isRead == False)
            .order_by(Notification.createdAt.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    # ── Write Operations ─────────────────────────────────────────────────────

    def create(self, obj_in: NotificationCreate) -> Notification:
        """Insert a new notification."""
        db_obj = Notification(
            userId=obj_in.userId,
            senderId=obj_in.senderId,
            orderId=obj_in.orderId,
            listingId=obj_in.listingId,
            type=obj_in.type,
            title=obj_in.title,
            body=obj_in.body,
            isRead=False
        )
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def update(self, db_obj: Notification, obj_in: NotificationUpdate) -> Notification:
        """Apply updates to an existing notification (e.g., mark as read)."""
        update_data = obj_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_obj, field, value)
            if field == "isRead" and value is True:
                db_obj.readAt = datetime.now(timezone.utc)
            elif field == "isRead" and value is False:
                db_obj.readAt = None
        
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def mark_as_read(self, notification: Notification) -> Notification:
        """Mark a single notification as read."""
        notification.isRead = True
        notification.readAt = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(notification)
        return notification

    def mark_all_as_read(self, user_id: uuid.UUID) -> list[Notification]:
        """Mark all unread notifications for a user as read. Returns updated records."""
        now = datetime.now(timezone.utc)
        
        # 1. Fetch unread notifications
        unread = self.db.query(Notification).filter(
            Notification.userId == user_id, 
            Notification.isRead == False
        ).all()
        
        if not unread:
            return []
            
        # 2. Update them
        for n in unread:
            n.isRead = True
            n.readAt = now
            
        self.db.commit()
        # 3. Refresh and return
        for n in unread:
            self.db.refresh(n)
        return unread

    def delete(self, db_obj: Notification) -> None:
        """Remove a notification record."""
        self.db.delete(db_obj)
        self.db.commit()

    def delete_all_for_user(self, user_id: uuid.UUID) -> int:
        """Delete all notifications for a specific user."""
        result = (
            self.db.query(Notification)
            .filter(Notification.userId == user_id)
            .delete(synchronize_session=False)
        )
        self.db.commit()
        return result

    def delete_expired_notifications(
        self, 
        read_days: int = settings.DELETE_READ_NOTIFICATIONS_IN_DAYS, 
        unread_days: int = settings.DELETE_UNREAD_NOTIFICATIONS_IN_DAYS
    ) -> int:
        """
        Delete notifications based on the retention policy:
        - Read notifications older than read_days.
        - Unread notifications older than unread_days.
        Returns total count of deleted records.
        """
        from datetime import timedelta
        now = datetime.now(timezone.utc)
        
        read_cutoff = now - timedelta(days=read_days)
        unread_cutoff = now - timedelta(days=unread_days)

        # 1. Delete expired READ notifications
        read_deleted = (
            self.db.query(Notification)
            .filter(Notification.isRead == True, Notification.readAt < read_cutoff)
            .delete(synchronize_session=False)
        )

        # 2. Delete expired UNREAD notifications
        unread_deleted = (
            self.db.query(Notification)
            .filter(Notification.isRead == False, Notification.createdAt < unread_cutoff)
            .delete(synchronize_session=False)
        )

        self.db.commit()
        return read_deleted + unread_deleted
