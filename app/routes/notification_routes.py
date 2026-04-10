"""
Notification Routes — API endpoints for user notifications.
"""

import uuid
from typing import List

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core import security
from app.db.session import get_db
from app.models.user import User
from app.schemas.notification import NotificationResponse, NotificationMarkReadResponse, NotificationListResponse
from app.services.notification_service import NotificationService

router = APIRouter(
    prefix="/notifications",
    tags=["Notifications"],
)

@router.get("/", response_model=List[NotificationListResponse])
def list_notifications(
    only_unread: bool = Query(False, description="Filter for unread notifications only"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(security.get_current_user),
):
    """
    Retrieve notifications for the current authenticated user.
    """
    return NotificationService(db).list_notifications(
        user_id=current_user.id, 
        only_unread=only_unread, 
        skip=skip, 
        limit=limit
    )

@router.patch("/mark-all-as-read", response_model=List[NotificationMarkReadResponse])
def mark_all_as_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(security.get_current_user),
):
    """
    Mark all unread notifications for the current user as read.
    """
    return NotificationService(db).mark_all_as_read(current_user_id=current_user.id)

@router.get("/{notification_id}", response_model=NotificationResponse)
def get_notification_by_id(
    notification_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(security.get_current_user),
):
    """
    Retrieve a specific notification by ID for the current authenticated user.
    """
    return NotificationService(db).get_notification_by_id(notification_id, current_user_id=current_user.id)

@router.patch("/{notification_id}", response_model=NotificationMarkReadResponse)
def mark_as_read(
    notification_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(security.get_current_user),
):
    """
    Mark a specific notification as read.
    """
    return NotificationService(db).mark_as_read(notification_id, current_user_id=current_user.id)

@router.delete("/{notification_id}", status_code=status.HTTP_200_OK)
def delete_notification(
    notification_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(security.get_current_user),
):
    """
    Delete a specific notification record.
    """
    return NotificationService(db).delete_notification(notification_id, current_user_id=current_user.id)
