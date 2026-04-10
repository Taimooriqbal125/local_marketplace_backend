"""OTP Token Repository — database operations for OTP tokens."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from app.models.otp_token import OTPToken


class OTPTokenRepository:
    """Class-based repository for OTPToken."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ---- Read operations -------------------------------------------------

    def get(self, token_id: uuid.UUID) -> Optional[OTPToken]:
        """Fetch an OTP token by primary key."""
        return self.db.query(OTPToken).filter(OTPToken.id == token_id).first()

    def get_by_email_and_purpose(
        self, email: str, purpose: str, include_used: bool = False
    ) -> Optional[OTPToken]:
        """Fetch the latest OTP token for a specific email and purpose."""
        query = self.db.query(OTPToken).filter(
            OTPToken.email == email,
            OTPToken.purpose == purpose
        )
        if not include_used:
            query = query.filter(OTPToken.used.is_(False))
        
        return query.order_by(OTPToken.created_at.desc()).first()

    def get_valid_otp(self, email: str, purpose: str) -> Optional[OTPToken]:
        """Fetch a token only if it is not used, not expired, and attempts are within limit."""
        return (
            self.db.query(OTPToken)
            .filter(
                OTPToken.email == email,
                OTPToken.purpose == purpose,
                OTPToken.used.is_(False),
                OTPToken.expires_at > func.now(),
                OTPToken.attempts < 5 # Standard attempt limit
            )
            .order_by(OTPToken.created_at.desc())
            .first()
        )

    # ---- Write operations ------------------------------------------------

    def create(self, otp_token: OTPToken) -> OTPToken:
        """Insert a new OTP token record."""
        self.db.add(otp_token)
        self.db.commit()
        self.db.refresh(otp_token)
        return otp_token

    def update(self, db_otp: OTPToken, update_data: dict) -> OTPToken:
        """Apply updates to an OTP token record."""
        for key, value in update_data.items():
            setattr(db_otp, key, value)
        self.db.commit()
        self.db.refresh(db_otp)
        return db_otp

    def mark_as_used(self, db_otp: OTPToken) -> OTPToken:
        """Mark an OTP token as used."""
        db_otp.used = True
        db_otp.used_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(db_otp)
        return db_otp

    def increment_attempts(self, db_otp: OTPToken) -> OTPToken:
        """Increment the failed attempts counter for an OTP."""
        db_otp.attempts += 1
        self.db.commit()
        self.db.refresh(db_otp)
        return db_otp

    def delete_expired(self, email: str, purpose: str) -> int:
        """Delete all expired/used tokens for an email and purpose. Returns count."""
        count = (
            self.db.query(OTPToken)
            .filter(
                OTPToken.email == email,
                OTPToken.purpose == purpose,
                (OTPToken.expires_at < func.now()) | (OTPToken.used.is_(True))
            )
            .delete(synchronize_session=False)
        )
        self.db.commit()
        return count
