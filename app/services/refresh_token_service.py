"""Refresh Token Service — business logic for refresh token lifecycle."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.refresh_token import RefreshToken
from app.repositories import RefreshTokenRepository


class InvalidTokenError(HTTPException):
    def __init__(self, detail: str = "Invalid or expired refresh token"):
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


class TokenForbiddenError(HTTPException):
    def __init__(self, detail: str = "You are not allowed to revoke this refresh token"):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


class RefreshTokenService:
    """Service layer for refresh token issuance, validation, and revocation."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = RefreshTokenRepository(db)

    def _hash_token(self, raw_token: str) -> str:
        """Hash refresh token before storing/lookup."""
        return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    def _build_expiry(self, expires_in_days: Optional[int] = None) -> datetime:
        """Compute refresh token expiry timestamp."""
        days = expires_in_days
        if days is None:
            days = getattr(settings, "REFRESH_TOKEN_EXPIRE_DAYS", 7)
        return datetime.now(timezone.utc) + timedelta(days=days)

    def issue_token(
        self,
        user_id: uuid.UUID,
        expires_in_days: Optional[int] = None,
    ) -> tuple[str, RefreshToken]:
        """Create a new refresh token for a user. Returns raw token and persisted row."""
        raw_token = secrets.token_urlsafe(64)
        db_token = RefreshToken(
            user_id=user_id,
            token_hash=self._hash_token(raw_token),
            expires_at=self._build_expiry(expires_in_days),
            revoked=False,
        )
        created = self.repo.create(db_token)
        return raw_token, created

    def get_valid_token(self, raw_token: str) -> RefreshToken:
        """Return a valid token row or raise Unathorized error."""
        token_hash = self._hash_token(raw_token)
        db_token = self.repo.get_valid_by_token_hash(token_hash)
        if not db_token:
            raise InvalidTokenError()
        return db_token

    def rotate_token(
        self,
        raw_token: str,
        expires_in_days: Optional[int] = None,
    ) -> tuple[str, RefreshToken]:
        """Rotate a refresh token safely generating a new issuance."""
        current = self.get_valid_token(raw_token)
        self.repo.revoke(current)
        return self.issue_token(current.user_id, expires_in_days)

    def revoke_token(self, raw_token: str) -> bool:
        """Revoke a single refresh token by raw token value."""
        token_hash = self._hash_token(raw_token)
        db_token = self.repo.get_by_token_hash(token_hash)
        if not db_token:
            return False
        if db_token.revoked:
            return True
        self.repo.revoke(db_token)
        return True

    def revoke_token_for_user(self, raw_token: str, user_id: uuid.UUID) -> bool:
        """Revoke a refresh token only if it belongs to the provided user."""
        token_hash = self._hash_token(raw_token)
        db_token = self.repo.get_by_token_hash(token_hash)
        if not db_token:
            return False
            
        if db_token.user_id != user_id:
            raise TokenForbiddenError()
            
        if db_token.revoked:
            return True
        self.repo.revoke(db_token)
        return True

    def revoke_token_by_id(self, token_id: uuid.UUID) -> bool:
        """Revoke a single refresh token by database ID."""
        db_token = self.repo.get(token_id)
        if not db_token:
            return False
        if db_token.revoked:
            return True
        self.repo.revoke(db_token)
        return True

    def revoke_all_for_user(self, user_id: uuid.UUID) -> int:
        """Revoke all active refresh tokens for a user."""
        return self.repo.revoke_all_for_user(user_id)

    def list_user_tokens(
        self,
        user_id: uuid.UUID,
        include_revoked: bool = True,
        skip: int = 0,
        limit: int = 100,
    ) -> list[RefreshToken]:
        """List refresh tokens for a user."""
        return self.repo.get_by_user(
            user_id=user_id,
            include_revoked=include_revoked,
            skip=skip,
            limit=limit,
        )
