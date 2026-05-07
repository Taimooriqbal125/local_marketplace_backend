"""
Unit tests for Notification Service.
Focuses on permission checks, notification logic, and real-time WebSocket broadcasting.
"""

import uuid
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock, patch

import pytest
from sqlalchemy.orm import Session

from app.services.notification_service import (
    NotificationService,
    NotificationNotFoundError,
    NotificationForbiddenError
)
from app.schemas.notification import NotificationCreate


class MockNotification:
    """
    Mock Notification database model.
    Includes attributes required for Pydantic mapping and service logic.
    """
    def __init__(self, **kwargs):
        self.id = kwargs.get("id", uuid.uuid4())
        self.userId = kwargs.get("userId", uuid.uuid4())
        self.type = kwargs.get("type", "order_update")
        self.title = kwargs.get("title", "Test Notification")
        self.body = kwargs.get("body", "Test Content")
        self.isRead = kwargs.get("isRead", False)
        self.created_at = kwargs.get("created_at", datetime.now())
        # Add any other kwargs directly to the instance
        for key, value in kwargs.items():
            setattr(self, key, value)


@pytest.fixture
def db_session():
    return MagicMock(spec=Session)


@pytest.fixture
def notification_service(db_session):
    """Provides a NotificationService instance with a mocked repository."""
    service = NotificationService(db_session)
    service.repo = MagicMock()
    return service


# ── PERMISSION & FETCH Tests ──────────────────────────────────────────────

def test_get_notification_by_id_success(notification_service):
    """Test fetching a notification by ID successfully with ownership check."""
    # Arrange
    notif_id = uuid.uuid4()
    user_id = uuid.uuid4()
    mock_notif = MockNotification(id=notif_id, userId=user_id)
    notification_service.repo.get.return_value = mock_notif

    # Act
    result = notification_service.get_notification_by_id(notif_id, user_id)

    # Assert
    assert result.id == notif_id
    assert result.userId == user_id
    notification_service.repo.get.assert_called_once_with(notif_id)


def test_get_notification_not_found(notification_service):
    """Test fetching a non-existent notification raises NotificationNotFoundError."""
    # Arrange
    notification_service.repo.get.return_value = None

    # Act & Assert
    with pytest.raises(NotificationNotFoundError):
        notification_service.get_notification_by_id(uuid.uuid4(), uuid.uuid4())


def test_get_notification_forbidden(notification_service):
    """Test that a user cannot access another user's notification."""
    # Arrange
    notif_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    thief_id = uuid.uuid4()
    mock_notif = MockNotification(id=notif_id, userId=owner_id)
    notification_service.repo.get.return_value = mock_notif

    # Act & Assert
    with pytest.raises(NotificationForbiddenError):
        notification_service.get_notification_by_id(notif_id, thief_id)


def test_list_notifications(notification_service):
    """Test listing notifications for a user."""
    # Arrange
    user_id = uuid.uuid4()
    mock_list = [MockNotification(userId=user_id), MockNotification(userId=user_id)]
    notification_service.repo.get_all_by_user.return_value = mock_list

    # Act
    result = notification_service.list_notifications(user_id)

    # Assert
    assert len(result) == 2
    notification_service.repo.get_all_by_user.assert_called_once_with(user_id, skip=0, limit=20)


def test_list_unread_notifications(notification_service):
    """Test listing only unread notifications."""
    # Arrange
    user_id = uuid.uuid4()
    notification_service.repo.get_unread_by_user.return_value = []

    # Act
    notification_service.list_notifications(user_id, only_unread=True)

    # Assert
    notification_service.repo.get_unread_by_user.assert_called_once_with(user_id, skip=0, limit=20)


# ── BROADCAST Tests ───────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_send_notification_success(notification_service):
    """Test persisting a notification and broadcasting it via WebSocket."""
    # Arrange
    user_id = uuid.uuid4()
    mock_notif = MockNotification(id=uuid.uuid4(), userId=user_id, title="Broadcast Test")
    notification_service.repo.create.return_value = mock_notif

    with patch("app.services.notification_service.manager", new_callable=AsyncMock) as mock_manager:
        # Act
        result = await notification_service.send_notification(
            user_id=user_id,
            type="test_event",
            title="Broadcast Test",
            body="Check your messages"
        )

        # Assert
        assert result.id == mock_notif.id
        notification_service.repo.create.assert_called_once()
        
        # Verify WebSocket broadcast
        mock_manager.send_personal_message.assert_called_once()
        call_kwargs = mock_manager.send_personal_message.call_args[1]
        assert call_kwargs["user_id"] == user_id
        assert call_kwargs["message"]["event"] == "notification"
        assert call_kwargs["message"]["data"]["title"] == "Broadcast Test"


# ── UPDATE & DELETE Tests ─────────────────────────────────────────────────

def test_mark_as_read_success(notification_service):
    """Test marking a specific notification as read."""
    # Arrange
    notif_id = uuid.uuid4()
    user_id = uuid.uuid4()
    mock_notif = MockNotification(id=notif_id, userId=user_id, isRead=False)
    notification_service.repo.get.return_value = mock_notif
    notification_service.repo.mark_as_read.return_value = MockNotification(id=notif_id, isRead=True)

    # Act
    result = notification_service.mark_as_read(notif_id, user_id)

    # Assert
    assert result.isRead is True
    notification_service.repo.mark_as_read.assert_called_once()


def test_delete_notification_success(notification_service):
    """Test deleting a notification successfully."""
    # Arrange
    notif_id = uuid.uuid4()
    user_id = uuid.uuid4()
    mock_notif = MockNotification(id=notif_id, userId=user_id)
    notification_service.repo.get.return_value = mock_notif

    # Act
    result = notification_service.delete_notification(notif_id, user_id)

    # Assert
    assert result["message"] == "Notification deleted successfully"
    notification_service.repo.delete.assert_called_once_with(mock_notif)


# ── CLEANUP Tests ─────────────────────────────────────────────────────────

def test_cleanup_expired_notifications(notification_service):
    """Test triggering the cleanup of old notifications."""
    # Arrange
    notification_service.repo.delete_expired_notifications.return_value = 15

    # Act
    result = notification_service.cleanup_expired_notifications(read_days=10, unread_days=20)

    # Assert
    assert result["deleted_count"] == 15
    notification_service.repo.delete_expired_notifications.assert_called_once_with(
        read_days=10, unread_days=20
    )
