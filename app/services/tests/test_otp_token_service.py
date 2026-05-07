"""
Unit tests for OTP Token Service.
Focuses on OTP lifecycle, security hashing, and state updates (email verification/password reset).
"""

import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.services.otp_token_service import OTPTokenService, InvalidOTPError
from app.models.otp_token import OTPToken, OTPPurpose


class MockOTPToken:
    """Mock OTPToken database model."""
    def __init__(self, **kwargs):
        self.id = kwargs.get("id", uuid.uuid4())
        self.email = kwargs.get("email", "test@example.com")
        self.otp_hash = kwargs.get("otp_hash", "hashed_otp")
        self.purpose = kwargs.get("purpose", OTPPurpose.SIGNUP_VERIFY)
        self.expires_at = kwargs.get("expires_at", datetime.now(timezone.utc) + timedelta(minutes=10))
        self.used = kwargs.get("used", False)
        for k, v in kwargs.items():
            setattr(self, k, v)


@pytest.fixture
def db_session():
    return MagicMock(spec=Session)


@pytest.fixture
def otp_service(db_session):
    """Provides an OTPTokenService instance with mocked repository."""
    service = OTPTokenService(db_session)
    service.repo = MagicMock()
    return service


# ── GENERATION Tests ──────────────────────────────────────────────────────

def test_create_otp_success(otp_service):
    """Test generating a new OTP and persisting its hash."""
    # Arrange
    email = "test@example.com"
    purpose = OTPPurpose.SIGNUP_VERIFY
    otp_service.repo.get_by_email_and_purpose.return_value = None

    with patch("app.services.otp_token_service.hash_password") as mock_hash:
        mock_hash.return_value = "hashed_123456"
        
        # Act
        plain_otp = otp_service.create_otp(email, purpose)

        # Assert
        assert len(plain_otp) == 6
        assert plain_otp.isdigit()
        otp_service.repo.create.assert_called_once()
        # Verify it invalidated previous ones
        otp_service.repo.delete_expired.assert_called_once_with(email, purpose)


# ── VERIFICATION Tests ────────────────────────────────────────────────────

def test_verify_otp_success(otp_service):
    """Test successful OTP verification."""
    # Arrange
    email = "test@example.com"
    plain_otp = "123456"
    purpose = OTPPurpose.SIGNUP_VERIFY
    mock_db_otp = MockOTPToken(otp_hash="hashed_val")
    
    otp_service.repo.get_valid_otp.return_value = mock_db_otp

    with patch("app.services.otp_token_service.verify_password") as mock_verify:
        mock_verify.return_value = True
        
        # Act
        result = otp_service.verify_otp(email, plain_otp, purpose)

        # Assert
        assert result is True
        otp_service.repo.mark_as_used.assert_called_once_with(mock_db_otp)


def test_verify_otp_incorrect_code(otp_service):
    """Test that incorrect OTP returns False and increments attempts."""
    # Arrange
    email = "test@example.com"
    mock_db_otp = MockOTPToken()
    otp_service.repo.get_valid_otp.return_value = mock_db_otp

    with patch("app.services.otp_token_service.verify_password") as mock_verify:
        mock_verify.return_value = False
        
        # Act
        result = otp_service.verify_otp(email, "000000", OTPPurpose.SIGNUP_VERIFY)

        # Assert
        assert result is False
        otp_service.repo.increment_attempts.assert_called_once_with(mock_db_otp)


def test_verify_otp_expired_or_missing(otp_service):
    """Test that missing or expired OTP raises InvalidOTPError."""
    # Arrange
    otp_service.repo.get_valid_otp.return_value = None

    # Act & Assert
    with pytest.raises(InvalidOTPError):
        otp_service.verify_otp("test@example.com", "123456", OTPPurpose.SIGNUP_VERIFY)


# ── BUSINESS PROCESS Tests ────────────────────────────────────────────────

def test_process_verify_otp_signup_success(otp_service, db_session):
    """Test full signup verification process including user state update."""
    # Arrange
    email = "test@example.com"
    otp_service.repo.get_valid_otp.return_value = MockOTPToken()
    
    with patch("app.services.otp_token_service.verify_password", return_value=True), \
         patch("app.repositories.user_repo.UserRepository") as mock_user_repo_cls:
        
        mock_user_repo = mock_user_repo_cls.return_value
        mock_user = MagicMock(email=email)
        mock_user_repo.get_by_email.return_value = mock_user

        # Act
        result = otp_service.process_verify_otp(email, "123456", OTPPurpose.SIGNUP_VERIFY)

        # Assert
        assert "now verified" in result
        mock_user_repo.update.assert_called_once()
        # Verify update fields
        update_data = mock_user_repo.update.call_args[0][1]
        assert update_data["is_email_verified"] is True


def test_process_reset_password_same_password_error(otp_service):
    """Test that resetting to the same password raises an error."""
    # Arrange
    email = "test@example.com"
    otp_service.repo.get_valid_otp.return_value = MockOTPToken()
    
    with patch("app.services.otp_token_service.verify_password") as mock_verify, \
         patch("app.repositories.user_repo.UserRepository") as mock_user_repo_cls:
        
        # mock_verify called twice: once for OTP, once for password comparison
        mock_verify.side_effect = [True, True] 
        
        mock_user_repo = mock_user_repo_cls.return_value
        mock_user_repo.get_by_email.return_value = MagicMock(hashed_password="old_hash")

        # Act & Assert
        with pytest.raises(HTTPException) as exc:
            otp_service.process_reset_password(email, "123456", "same_password")
        
        assert exc.value.status_code == 400
        assert "cannot be the same" in exc.value.detail


def test_process_resend_otp(otp_service):
    """Test resending an OTP."""
    # Arrange
    email = "test@example.com"
    otp_service.repo.get_by_email_and_purpose.return_value = None

    # Act
    result = otp_service.process_resend_otp(email, OTPPurpose.SIGNUP_VERIFY)

    # Assert
    assert "sent to your email" in result
    otp_service.repo.create.assert_called_once()
