"""
Unit tests for Refresh Token Service.
Focuses on token issuance, secure rotation, and revocation logic.
"""

import uuid
import hashlib
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from app.services.refresh_token_service import (
    RefreshTokenService,
    InvalidTokenError,
    TokenForbiddenError
)


class MockRefreshToken:
    """Mock RefreshToken database model."""
    def __init__(self, **kwargs):
        self.id = kwargs.get("id", uuid.uuid4())
        self.user_id = kwargs.get("user_id", uuid.uuid4())
        self.token_hash = kwargs.get("token_hash", "some_hash")
        self.expires_at = kwargs.get("expires_at", datetime.now(timezone.utc) + timedelta(days=7))
        self.revoked = kwargs.get("revoked", False)
        for k, v in kwargs.items():
            setattr(self, k, v)


@pytest.fixture
def db_session():
    return MagicMock(spec=Session)


@pytest.fixture
def refresh_service(db_session):
    """Provides a RefreshTokenService instance with a mocked repository."""
    service = RefreshTokenService(db_session)
    service.repo = MagicMock()
    return service


# ── ISSUANCE & HASHING Tests ──────────────────────────────────────────────

def test_hash_token(refresh_service):
    """Test consistent SHA256 hashing of tokens."""
    token = "test_token_123"
    expected = hashlib.sha256(token.encode("utf-8")).hexdigest()
    assert refresh_service._hash_token(token) == expected


def test_issue_token_success(refresh_service):
    """Test issuing a new refresh token for a user."""
    # Arrange
    user_id = uuid.uuid4()
    refresh_service.repo.create.side_effect = lambda x: x # Return the passed object

    # Act
    raw_token, db_token = refresh_service.issue_token(user_id)

    # Assert
    assert len(raw_token) >= 64
    assert db_token.user_id == user_id
    assert db_token.revoked is False
    assert db_token.expires_at > datetime.now(timezone.utc)
    refresh_service.repo.create.assert_called_once()


# ── VALIDATION & ROTATION Tests ───────────────────────────────────────────

def test_get_valid_token_success(refresh_service):
    """Test retrieving a valid token row by its raw value."""
    # Arrange
    raw_token = "secret_token"
    mock_token = MockRefreshToken(user_id=uuid.uuid4())
    refresh_service.repo.get_valid_by_token_hash.return_value = mock_token

    # Act
    result = refresh_service.get_valid_token(raw_token)

    # Assert
    assert result == mock_token
    refresh_service.repo.get_valid_by_token_hash.assert_called_once()


def test_get_valid_token_invalid_or_expired(refresh_service):
    """Test that invalid/expired tokens raise InvalidTokenError (401)."""
    # Arrange
    refresh_service.repo.get_valid_by_token_hash.return_value = None

    # Act & Assert
    with pytest.raises(InvalidTokenError):
        refresh_service.get_valid_token("fake_token")


def test_rotate_token_success(refresh_service):
    """Test token rotation: revokes old, issues new."""
    # Arrange
    old_raw = "old_token"
    user_id = uuid.uuid4()
    mock_old = MockRefreshToken(user_id=user_id)
    
    refresh_service.repo.get_valid_by_token_hash.return_value = mock_old
    refresh_service.repo.create.side_effect = lambda x: x

    # Act
    new_raw, new_db = refresh_service.rotate_token(old_raw)

    # Assert
    assert new_raw != old_raw
    assert new_db.user_id == user_id
    refresh_service.repo.revoke.assert_called_once_with(mock_old)
    refresh_service.repo.create.assert_called_once()


# ── REVOCATION Tests ──────────────────────────────────────────────────────

def test_revoke_token_for_user_success(refresh_service):
    """Test revoking a token that belongs to the user."""
    # Arrange
    user_id = uuid.uuid4()
    mock_token = MockRefreshToken(user_id=user_id, revoked=False)
    refresh_service.repo.get_by_token_hash.return_value = mock_token

    # Act
    result = refresh_service.revoke_token_for_user("token", user_id)

    # Assert
    assert result is True
    refresh_service.repo.revoke.assert_called_once_with(mock_token)


def test_revoke_token_for_user_forbidden(refresh_service):
    """Test that users cannot revoke tokens belonging to others."""
    # Arrange
    owner_id = uuid.uuid4()
    attacker_id = uuid.uuid4()
    mock_token = MockRefreshToken(user_id=owner_id)
    refresh_service.repo.get_by_token_hash.return_value = mock_token

    # Act & Assert
    with pytest.raises(TokenForbiddenError):
        refresh_service.revoke_token_for_user("token", attacker_id)


def test_revoke_all_for_user(refresh_service):
    """Test bulk revocation for a user."""
    # Arrange
    user_id = uuid.uuid4()
    refresh_service.repo.revoke_all_for_user.return_value = 5

    # Act
    result = refresh_service.revoke_all_for_user(user_id)

    # Assert
    assert result == 5
    refresh_service.repo.revoke_all_for_user.assert_called_once_with(user_id)


# ── CLEANUP Tests ─────────────────────────────────────────────────────────

def test_cleanup_stale_tokens(refresh_service):
    """Test triggering the deletion of expired/revoked tokens."""
    # Arrange
    refresh_service.repo.delete_stale_tokens.return_value = 100

    # Act
    result = refresh_service.cleanup_stale_tokens(revoked_days=30, expired_days=60)

    # Assert
    assert result["deleted_count"] == 100
    refresh_service.repo.delete_stale_tokens.assert_called_once()
