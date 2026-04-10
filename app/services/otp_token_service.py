"""
OTP Token Service — handles business logic for One-Time Password lifecycle.
"""

import random
import string
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.otp_token import OTPToken, OTPPurpose
from app.repositories.otp_token_repo import OTPTokenRepository
from app.services.email_service import email_service
from app.core.security import hash_password, verify_password


class InvalidOTPError(HTTPException):
    """Raised when an OTP is either incorrect, expired, or previously used."""
    def __init__(self, detail: str = "Invalid or expired OTP."):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


class OTPTokenService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = OTPTokenRepository(db)

    def _generate_numeric_otp(self, length: int = 6) -> str:
        """Generate a random numeric OTP string."""
        return "".join(random.choices(string.digits, k=length))

    def create_otp(
        self, email: str, purpose: OTPPurpose, user_id: Optional[UUID] = None
    ) -> str:
        """
        Generates a new OTP, saves the hash to the database, and returns the plain OTP.
        It also invalidates any existing unused OTPs for the same email and purpose.
        """
        # 1. Invalidate previous unused tokens for this email + purpose
        self.repo.delete_expired(email, purpose)
        existing = self.repo.get_by_email_and_purpose(email, purpose)
        if existing:
            self.repo.update(existing, {"used": True, "used_at": datetime.now(timezone.utc)})

        # 2. Generate plain OTP and hash it
        plain_otp = self._generate_numeric_otp()
        otp_hash = hash_password(plain_otp)

        # 3. Create new OTP record
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=10) # Configurable
        otp_token = OTPToken(
            email=email,
            user_id=user_id,
            otp_hash=otp_hash,
            purpose=purpose,
            expires_at=expires_at,
        )
        self.repo.create(otp_token)

        return plain_otp

    def send_otp_email(self, email: str, otp: str, purpose: OTPPurpose):
        """Send the OTP to the user's email."""
        subject = "Your Verification Code"
        if purpose == OTPPurpose.RESET_PASSWORD:
            subject = "Password Reset Code"
        
        html_content = f"""
        <div style="font-family: Arial, sans-serif; padding: 20px;">
            <h2>Verification Code</h2>
            <p>Your verification code is: <strong style="font-size: 24px; color: #4A90E2;">{otp}</strong></p>
            <p>This code will expire in 10 minutes.</p>
            <p>If you didn't request this, please ignore this email.</p>
        </div>
        """

        # Testing mode: print OTP in console instead of sending real email.
        # email_service.send_email(to_email=email, subject=subject, html_content=html_content)
        print(f"[OTP-TEST] {subject} for {email}: {otp} (purpose={purpose.value})")

    def verify_otp(self, email: str, otp: str, purpose: OTPPurpose) -> bool:
        """
        Verifies the provided OTP against the stored hash.
        Returns True if valid, False if verification failed (but format is okay),
        or raises InvalidOTPError if the token does not exist or expired.
        """
        db_otp = self.repo.get_valid_otp(email, purpose)
        
        if not db_otp:
            raise InvalidOTPError()

        # Check hash
        if not verify_password(otp, db_otp.otp_hash):
            self.repo.increment_attempts(db_otp)
            return False

        # Mark as used
        self.repo.mark_as_used(db_otp)
        
        return True

    def process_verify_otp(self, email: str, otp: str, purpose: OTPPurpose) -> str:
        """Orchestrates OTP verification and updates associated user state."""
        if not self.verify_otp(email, otp, purpose):
            raise InvalidOTPError("Incorrect OTP code.")

        if purpose == OTPPurpose.SIGNUP_VERIFY:
            from app.repositories.user_repo import UserRepository
            user_repo = UserRepository(self.db)
            user = user_repo.get_by_email(email)
            if user:
                user_repo.update(user, {
                    "is_email_verified": True,
                    "email_verified_at": datetime.now(timezone.utc)
                })
            return "OTP verified successfully. Your email is now verified."
            
        return "OTP verified successfully."

    def process_forgot_password(self, email: str) -> str:
        from app.repositories.user_repo import UserRepository
        user_repo = UserRepository(self.db)
        user = user_repo.get_by_email(email)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
            
        plain_otp = self.create_otp(email=user.email, purpose=OTPPurpose.RESET_PASSWORD, user_id=user.id)
        self.send_otp_email(email=user.email, otp=plain_otp, purpose=OTPPurpose.RESET_PASSWORD)
        return "A password reset code has been sent to your email."

    def process_reset_password(self, email: str, otp: str, new_password: str) -> str:
        if not self.verify_otp(email, otp, OTPPurpose.RESET_PASSWORD):
            raise InvalidOTPError("Incorrect or expired reset code.")

        from app.repositories.user_repo import UserRepository
        user_repo = UserRepository(self.db)
        user = user_repo.get_by_email(email)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        if verify_password(new_password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The new password cannot be the same as your old password."
            )

        user_repo.update(user, {"hashed_password": hash_password(new_password)})
        return "Your password has been reset successfully. You can now login with your new password."

    def process_resend_otp(self, email: str, purpose: OTPPurpose) -> str:
        plain_otp = self.create_otp(email=email, purpose=purpose)
        self.send_otp_email(email=email, otp=plain_otp, purpose=purpose)
        return "A new verification code has been sent to your email."