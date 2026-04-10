"""
Notification Service — encapsulates business logic for notifications.
"""

from __future__ import annotations

import uuid
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.repositories.notification_repo import NotificationRepository
from app.schemas.notification import NotificationCreate
from app.models.notification import Notification
from app.websocket import manager


class NotificationNotFoundError(HTTPException):
    def __init__(self, detail: str = "Notification not found"):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


class NotificationForbiddenError(HTTPException):
    def __init__(self, detail: str = "You are not authorized to access this notification"):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


class NotificationService:
    """Service layer for Notification business logic."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = NotificationRepository(db)

    def _get_notification_or_404(self, notification_id: uuid.UUID, current_user_id: uuid.UUID) -> Notification:
        """Internal helper to fetch and enforce possession of a notification."""
        notification = self.repo.get(notification_id)
        if not notification:
            raise NotificationNotFoundError()

        if notification.userId != current_user_id:
            raise NotificationForbiddenError()
            
        return notification

    def list_notifications(
        self, 
        user_id: uuid.UUID, 
        only_unread: bool = False, 
        skip: int = 0, 
        limit: int = 20
    ):
        """Fetch notifications optionally filtered by read status."""
        if only_unread:
            return self.repo.get_unread_by_user(user_id, skip=skip, limit=limit)
        return self.repo.get_all_by_user(user_id, skip=skip, limit=limit)

    def get_notification_by_id(self, notification_id: uuid.UUID, current_user_id: uuid.UUID):
        """Fetch a single notification enforcing ownership."""
        return self._get_notification_or_404(notification_id, current_user_id)

    def mark_as_read(self, notification_id: uuid.UUID, current_user_id: uuid.UUID):
        """Mark a specific notification as read."""
        notification = self._get_notification_or_404(notification_id, current_user_id)
        return self.repo.mark_as_read(notification)

    def mark_all_as_read(self, current_user_id: uuid.UUID):
        """Mark all unread notifications for a user as read."""
        return self.repo.mark_all_as_read(current_user_id)

    async def send_notification(
        self, 
        user_id: uuid.UUID | str, 
        type: str, 
        title: str, 
        body: str, 
        sender_id: Optional[uuid.UUID | str] = None,
        order_id: Optional[uuid.UUID | str] = None,
        listing_id: Optional[uuid.UUID | str] = None
    ):
        """
        Create and persist a notification, then broadcast sequentially over WebSocket.
        """
        if isinstance(user_id, str):
            user_id = uuid.UUID(user_id)
        
        # Persist to Database with Pydantic properties using native snake_case format
        obj_in = NotificationCreate(
            user_id=user_id,
            sender_id=sender_id,
            order_id=order_id,
            listing_id=listing_id,
            type=type,
            title=title,
            body=body
        )
        notification = self.repo.create(obj_in)

        # Real-time broadcast
        await manager.send_personal_message(
            user_id=user_id,
            message={
                "event": "notification",
                "data": {
                    "id": str(notification.id),
                    "type": notification.type,
                    "title": notification.title,
                    "body": notification.body,
                    "isRead": notification.isRead,
                    "createdAt": notification.created_at.isoformat()
                }
            }
        )
        
        return notification

    def delete_notification(self, notification_id: uuid.UUID, current_user_id: uuid.UUID):
        """Permanently delete a notification enforcing ownership."""
        notification = self._get_notification_or_404(notification_id, current_user_id)
        self.repo.delete(notification)
        return {"message": "Notification deleted successfully"}

    def cleanup_expired_notifications(self, read_days: int = 60, unread_days: int = 180):
        """Trigger cleanup of old notifications based on retention period rules."""
        deleted_count = self.repo.delete_expired_notifications(
            read_days=read_days, 
            unread_days=unread_days
        )
        return {"deleted_count": deleted_count}
