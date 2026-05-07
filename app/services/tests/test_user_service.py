"""
Unit tests for User Service.
Focuses on registration rules (uniqueness), secure auth flow, and admin vs owner authorization.
"""

import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.services.user_service import (
    UserService,
    UserNotFoundError,
    UserConflictError,
    PhoneConflictError,
    UserForbiddenError
)
from app.schemas.user import UserCreate, UserUpdate


class MockUser:
    """Mock User database model."""
    def __init__(self, **kwargs):
        self.id = kwargs.get("id", uuid.uuid4())
        self.email = kwargs.get("email", "test@example.com")
        self.phone = kwargs.get("phone", "+923001234567")
        self.hashed_password = kwargs.get("hashed_password", "hashed_secret")
        self.is_admin = kwargs.get("is_admin", False)
        self.is_active = kwargs.get("is_active", True)
        # Add any other fields dynamically
        for key, value in kwargs.items():
            setattr(self, key, value)


@pytest.fixture
def db_session():
    return MagicMock(spec=Session)


@pytest.fixture
def user_service(db_session):
    """Provides a UserService instance with dependencies mocked."""
    service = UserService(db_session)
    service.repo = MagicMock()
    service.otp_service = MagicMock()
    return service


# ── REGISTRATION Tests ────────────────────────────────────────────────────

def test_create_user_success(user_service):
    """Test successful user registration with OTP trigger."""
    # Arrange
    user_data = UserCreate(
        email="new@example.com",
        password="password123",
        phone="+923001111111"
    )
    user_service.repo.get_by_email.return_value = None
    user_service.repo.get_by_phone.return_value = None
    
    mock_user = MockUser(email="new@example.com", id=uuid.uuid4())
    user_service.repo.create.return_value = mock_user
    user_service.otp_service.create_otp.return_value = "123456"

    # Act
    result = user_service.create_user(user_data)

    # Assert
    assert result.email == "new@example.com"
    user_service.repo.create.assert_called_once()
    user_service.otp_service.create_otp.assert_called_once()


def test_create_user_email_conflict(user_service):
    """Test that duplicate emails are rejected."""
    # Arrange
    user_data = UserCreate(email="exists@example.com", password="password123")
    user_service.repo.get_by_email.return_value = MockUser()

    # Act & Assert
    with pytest.raises(UserConflictError):
        user_service.create_user(user_data)


def test_create_user_phone_conflict(user_service):
    """Test that duplicate phone numbers are rejected."""
    # Arrange
    user_data = UserCreate(email="new@example.com", password="password123", phone="+923001234567")
    user_service.repo.get_by_email.return_value = None
    user_service.repo.get_by_phone.return_value = MockUser()

    # Act & Assert
    with pytest.raises(PhoneConflictError):
        user_service.create_user(user_data)


# ── AUTHENTICATION Tests ──────────────────────────────────────────────────

def test_login_success(user_service):
    """Test successful login returns access and refresh tokens."""
    # Arrange
    email = "user@example.com"
    password = "correct_password"
    mock_user = MockUser(email=email, hashed_password="hashed_password")
    user_service.repo.get_by_email.return_value = mock_user
    user_service.repo.touch_last_active_if_stale.return_value = mock_user

    with patch("app.core.security.verify_password", return_value=True), \
         patch("app.core.security.create_access_token", return_value="access_token_123"), \
         patch("app.services.refresh_token_service.RefreshTokenService") as MockRefresh:
        
        MockRefresh.return_value.issue_token.return_value = ("refresh_token_456", MagicMock())

        # Act
        result = user_service.login(email, password)

        # Assert
        assert result["access_token"] == "access_token_123"
        assert result["refresh_token"] == "refresh_token_456"
        assert result["user"] == mock_user


def test_login_invalid_password(user_service):
    """Test login failure with incorrect password."""
    # Arrange
    user_service.repo.get_by_email.return_value = MockUser()
    with patch("app.core.security.verify_password", return_value=False):
        # Act & Assert
        with pytest.raises(HTTPException) as exc:
            user_service.login("test@example.com", "wrong")
        assert exc.value.status_code == 401


# ── UPDATE & AUTHORIZATION Tests ──────────────────────────────────────────

def test_update_user_owner_success(user_service):
    """Test that a user can update their own profile."""
    # Arrange
    user_id = uuid.uuid4()
    current_user = MockUser(id=user_id, is_admin=False)
    db_user = MockUser(id=user_id)
    user_service.repo.get.return_value = db_user
    
    update_data = UserUpdate(phone="+929999999999")
    user_service.repo.get_by_phone.return_value = None

    # Act
    user_service.update_user(user_id, update_data, current_user)

    # Assert
    user_service.repo.update.assert_called_once()


def test_update_user_forbidden(user_service):
    """Test that a regular user cannot update someone else's profile."""
    # Arrange
    user_id = uuid.uuid4()
    other_user_id = uuid.uuid4()
    current_user = MockUser(id=user_id, is_admin=False)

    # Act & Assert
    with pytest.raises(UserForbiddenError):
        user_service.update_user(other_user_id, UserUpdate(), current_user)


def test_update_user_admin_privilege_success(user_service):
    """Test that an admin can update any user's active/admin flags."""
    # Arrange
    user_id = uuid.uuid4()
    admin_user = MockUser(id=uuid.uuid4(), is_admin=True)
    db_user = MockUser(id=user_id)
    user_service.repo.get.return_value = db_user
    
    update_data = UserUpdate(is_active=False, is_admin=True)

    # Act
    user_service.update_user(user_id, update_data, admin_user)

    # Assert
    user_service.repo.update.assert_called_once()


def test_update_user_admin_flag_forbidden(user_service):
    """Test that a regular user cannot promote themselves to admin."""
    # Arrange
    user_id = uuid.uuid4()
    current_user = MockUser(id=user_id, is_admin=False)
    
    update_data = UserUpdate(is_admin=True)

    # Act & Assert
    with pytest.raises(UserForbiddenError, match="Only admins"):
        user_service.update_user(user_id, update_data, current_user)
