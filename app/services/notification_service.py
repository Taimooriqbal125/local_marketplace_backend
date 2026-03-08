"""
Notification Service — encapsulates business logic for notifications.
"""

from __future__ import annotations

import uuid
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.repositories.notification_repo import NotificationRepository
from app.schemas.notification import NotificationCreate, NotificationUpdate
from app.websocket import manager


class NotificationService:
    """Service layer for Notification business logic."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = NotificationRepository(db)

    def list_notifications(
        self, 
        user_id: uuid.UUID, 
        only_unread: bool = False, 
        skip: int = 0, 
        limit: int = 20
    ):
        """
        Fetch notifications for a user.
        Can be filtered to show only unread ones.
        """
        if only_unread:
            return self.repo.get_unread_by_user(user_id, skip=skip, limit=limit)
        return self.repo.get_all_by_user(user_id, skip=skip, limit=limit)

    def mark_as_read(self, notification_id: uuid.UUID, current_user_id: uuid.UUID):
        """
        Mark a notification as read.
        Enforces ownership check so users can only mark their own notifications.
        """
        notification = self.repo.get(notification_id)
        if not notification:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found",
            )
        
        if notification.userId != current_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to access this notification",
            )
        
        return self.repo.mark_as_read(notification)

    def mark_all_as_read(self, current_user_id: uuid.UUID):
        """
        Mark all unread notifications for a user as read.
        """
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
        Create and send a notification to a specific user.
        This handles both database persistence and real-time triggers.
        """
        # Ensure user_id is a UUID object
        if isinstance(user_id, str):
            user_id = uuid.UUID(user_id)
        
        # 1. Persist to Database
        obj_in = NotificationCreate(
            userId=user_id,
            senderId=sender_id,
            orderId=order_id,
            listingId=listing_id,
            type=type,
            title=title,
            body=body
        )
        notification = self.repo.create(obj_in)

        # 2. Real-time broadcast via WebSocket
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
                    "createdAt": notification.createdAt.isoformat()
                }
            }
        )
        
        return notification

    def delete_notification(self, notification_id: uuid.UUID, current_user_id: uuid.UUID):
        """Delete a single notification with ownership enforcement."""
        notification = self.repo.get(notification_id)
        if not notification:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found",
            )
        
        if notification.userId != current_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to delete this notification",
            )
        
        self.repo.delete(notification)
        return {"message": "Notification deleted successfully"}

    def cleanup_expired_notifications(self, read_days: int = 60, unread_days: int = 180):
        """
        Triggers cleanup of old notifications based on retention rules.
        """
        deleted_count = self.repo.delete_expired_notifications(
            read_days=read_days, 
            unread_days=unread_days
        )
        return {"deleted_count": deleted_count}
