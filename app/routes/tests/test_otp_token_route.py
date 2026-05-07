from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.rate_limiter import forgot_password_rate_limit
from app.db.session import get_db
from app.routes.otp_token_route import router
from app.schemas.otp_token import OTPPurpose
from app.services.otp_token_service import (
    InvalidOTPError,
    OTPTokenService,
)


def _build_test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)

    def _override_get_db():
        yield object()

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[forgot_password_rate_limit] = lambda: None
    return app


@pytest.fixture
def client() -> TestClient:
    return TestClient(_build_test_app())


def test_verify_otp_returns_200_for_signup_verify(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    email = "user@example.com"
    otp = "123456"

    def _fake_process_verify_otp(self, email, otp, purpose):
        assert email == email
        assert otp == otp
        assert purpose == OTPPurpose.SIGNUP_VERIFY
        return "OTP verified successfully. Your email is now verified."

    monkeypatch.setattr(OTPTokenService, "process_verify_otp", _fake_process_verify_otp)

    payload = {
        "email": email,
        "otp": otp,
        "purpose": "signup_verify",
    }
    response = client.post("/auth/verify-otp", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "OTP verified successfully. Your email is now verified."


def test_verify_otp_returns_200_for_password_reset(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    email = "user@example.com"
    otp = "654321"

    def _fake_process_verify_otp(self, email, otp, purpose):
        assert purpose == OTPPurpose.RESET_PASSWORD
        return "OTP verified successfully."

    monkeypatch.setattr(OTPTokenService, "process_verify_otp", _fake_process_verify_otp)

    payload = {
        "email": email,
        "otp": otp,
        "purpose": "reset_password",
    }
    response = client.post("/auth/verify-otp", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "OTP verified successfully."


def test_verify_otp_returns_400_for_invalid_otp(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    email = "user@example.com"
    otp = "000000"

    def _fake_process_verify_otp(self, email, otp, purpose):
        raise InvalidOTPError("Incorrect OTP code.")

    monkeypatch.setattr(OTPTokenService, "process_verify_otp", _fake_process_verify_otp)

    payload = {
        "email": email,
        "otp": otp,
        "purpose": "signup_verify",
    }
    response = client.post("/auth/verify-otp", json=payload)

    assert response.status_code == 400
    assert "Incorrect OTP" in response.json()["detail"]


def test_verify_otp_returns_400_for_expired_otp(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    email = "user@example.com"
    otp = "123456"

    def _fake_process_verify_otp(self, email, otp, purpose):
        raise InvalidOTPError("Invalid or expired OTP.")

    monkeypatch.setattr(OTPTokenService, "process_verify_otp", _fake_process_verify_otp)

    payload = {
        "email": email,
        "otp": otp,
        "purpose": "signup_verify",
    }
    response = client.post("/auth/verify-otp", json=payload)

    assert response.status_code == 400
    assert "Invalid or expired OTP" in response.json()["detail"]


def test_resend_otp_returns_200_for_signup(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    email = "user@example.com"

    def _fake_process_resend_otp(self, email, purpose):
        assert email == email
        assert purpose == OTPPurpose.SIGNUP_VERIFY
        return "A new verification code has been sent to your email."

    monkeypatch.setattr(OTPTokenService, "process_resend_otp", _fake_process_resend_otp)

    payload = {
        "email": email,
        "purpose": "signup_verify",
    }
    response = client.post("/auth/resend-otp", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "A new verification code has been sent to your email."


def test_resend_otp_returns_200_for_password_reset(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    email = "user@example.com"

    def _fake_process_resend_otp(self, email, purpose):
        assert purpose == OTPPurpose.RESET_PASSWORD
        return "A new verification code has been sent to your email."

    monkeypatch.setattr(OTPTokenService, "process_resend_otp", _fake_process_resend_otp)

    payload = {
        "email": email,
        "purpose": "reset_password",
    }
    response = client.post("/auth/resend-otp", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "A new verification code has been sent to your email."


def test_forgot_password_returns_200_for_existing_user(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    email = "user@example.com"

    def _fake_process_forgot_password(self, email):
        assert email == email
        return "A password reset code has been sent to your email."

    monkeypatch.setattr(OTPTokenService, "process_forgot_password", _fake_process_forgot_password)

    payload = {
        "email": email,
    }
    response = client.post("/auth/forgot-password", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "A password reset code has been sent to your email."


def test_forgot_password_returns_404_for_nonexistent_user(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fastapi import HTTPException, status
    
    email = "nonexistent@example.com"

    def _fake_process_forgot_password(self, email):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    monkeypatch.setattr(OTPTokenService, "process_forgot_password", _fake_process_forgot_password)

    payload = {
        "email": email,
    }
    response = client.post("/auth/forgot-password", json=payload)

    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"


def test_reset_password_returns_200_for_valid_otp_and_password(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    email = "user@example.com"
    otp = "123456"
    new_password = "NewSecurePassword123!"

    def _fake_process_reset_password(self, email, otp, new_password):
        assert email == email
        assert otp == otp
        assert new_password == new_password
        return "Your password has been reset successfully. You can now login with your new password."

    monkeypatch.setattr(OTPTokenService, "process_reset_password", _fake_process_reset_password)

    payload = {
        "email": email,
        "otp": otp,
        "new_password": new_password,
    }
    response = client.post("/auth/reset-password", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert "successfully" in body["message"].lower()


def test_reset_password_returns_400_for_invalid_otp(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    email = "user@example.com"
    otp = "000000"
    new_password = "NewSecurePassword123!"

    def _fake_process_reset_password(self, email, otp, new_password):
        raise InvalidOTPError("Incorrect or expired reset code.")

    monkeypatch.setattr(OTPTokenService, "process_reset_password", _fake_process_reset_password)

    payload = {
        "email": email,
        "otp": otp,
        "new_password": new_password,
    }
    response = client.post("/auth/reset-password", json=payload)

    assert response.status_code == 400
    assert "Incorrect or expired" in response.json()["detail"]


def test_reset_password_returns_404_for_nonexistent_user(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fastapi import HTTPException, status
    
    email = "nonexistent@example.com"
    otp = "123456"
    new_password = "NewSecurePassword123!"

    def _fake_process_reset_password(self, email, otp, new_password):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    monkeypatch.setattr(OTPTokenService, "process_reset_password", _fake_process_reset_password)

    payload = {
        "email": email,
        "otp": otp,
        "new_password": new_password,
    }
    response = client.post("/auth/reset-password", json=payload)

    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"


def test_reset_password_returns_400_when_same_as_old_password(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fastapi import HTTPException, status
    
    email = "user@example.com"
    otp = "123456"
    same_password = "OldPassword123!"

    def _fake_process_reset_password(self, email, otp, new_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The new password cannot be the same as your old password."
        )

    monkeypatch.setattr(OTPTokenService, "process_reset_password", _fake_process_reset_password)

    payload = {
        "email": email,
        "otp": otp,
        "new_password": same_password,
    }
    response = client.post("/auth/reset-password", json=payload)

    assert response.status_code == 400
    assert "cannot be the same" in response.json()["detail"]


def test_verify_otp_validates_email_format(
    client: TestClient,
) -> None:
    """Test that invalid email format is rejected."""
    payload = {
        "email": "invalid-email",
        "otp": "123456",
        "purpose": "signup_verify",
    }
    response = client.post("/auth/verify-otp", json=payload)

    assert response.status_code == 422
    assert "valid email" in response.json()["detail"][0]["msg"].lower()


def test_verify_otp_validates_otp_length(
    client: TestClient,
) -> None:
    """Test that OTP length is validated (must be exactly 6 digits)."""
    payload = {
        "email": "user@example.com",
        "otp": "12345",  # Only 5 digits
        "purpose": "signup_verify",
    }
    response = client.post("/auth/verify-otp", json=payload)

    assert response.status_code == 422


def test_resend_otp_validates_email_format(
    client: TestClient,
) -> None:
    """Test that invalid email format is rejected."""
    payload = {
        "email": "invalid-email",
        "purpose": "signup_verify",
    }
    response = client.post("/auth/resend-otp", json=payload)

    assert response.status_code == 422


def test_forgot_password_validates_email_format(
    client: TestClient,
) -> None:
    """Test that invalid email format is rejected."""
    payload = {
        "email": "invalid-email",
    }
    response = client.post("/auth/forgot-password", json=payload)

    assert response.status_code == 422


def test_reset_password_validates_email_format(
    client: TestClient,
) -> None:
    """Test that invalid email format is rejected."""
    payload = {
        "email": "invalid-email",
        "otp": "123456",
        "new_password": "NewPassword123!",
    }
    response = client.post("/auth/reset-password", json=payload)

    assert response.status_code == 422


def test_reset_password_validates_password_min_length(
    client: TestClient,
) -> None:
    """Test that password must meet minimum length requirement (8 chars)."""
    payload = {
        "email": "user@example.com",
        "otp": "123456",
        "new_password": "Short1!",  # Only 7 characters
    }
    response = client.post("/auth/reset-password", json=payload)

    assert response.status_code == 422


def test_reset_password_validates_otp_length(
    client: TestClient,
) -> None:
    """Test that OTP length is validated (must be exactly 6 digits)."""
    payload = {
        "email": "user@example.com",
        "otp": "12345",  # Only 5 digits
        "new_password": "NewPassword123!",
    }
    response = client.post("/auth/reset-password", json=payload)

    assert response.status_code == 422
