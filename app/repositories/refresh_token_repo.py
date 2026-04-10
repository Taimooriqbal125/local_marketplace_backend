"""Refresh Token Repository — database operations for refresh tokens."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from app.models.refresh_token import RefreshToken


class RefreshTokenRepository:
	"""Class-based repository for RefreshToken."""

	def __init__(self, db: Session) -> None:
		self.db = db

	# ---- Read operations -------------------------------------------------

	def get(self, token_id: uuid.UUID) -> Optional[RefreshToken]:
		"""Fetch a refresh token by primary key."""
		return self.db.query(RefreshToken).filter(RefreshToken.id == token_id).first()

	def get_by_token_hash(self, token_hash: str) -> Optional[RefreshToken]:
		"""Fetch a refresh token by its hashed token value."""
		return (
			self.db.query(RefreshToken)
			.filter(RefreshToken.token_hash == token_hash)
			.first()
		)

	def get_valid_by_token_hash(self, token_hash: str) -> Optional[RefreshToken]:
		"""Fetch a token only if it is not revoked and not expired."""
		return (
			self.db.query(RefreshToken)
			.filter(
				RefreshToken.token_hash == token_hash,
				RefreshToken.revoked.is_(False),
				RefreshToken.expires_at > func.now(),
			)
			.first()
		)

	def get_by_user(
		self,
		user_id: uuid.UUID,
		include_revoked: bool = True,
		skip: int = 0,
		limit: int = 100,
	) -> list[RefreshToken]:
		"""Return refresh tokens for a specific user."""
		query = self.db.query(RefreshToken).filter(RefreshToken.user_id == user_id)
		if not include_revoked:
			query = query.filter(RefreshToken.revoked.is_(False))

		return (
			query
			.order_by(RefreshToken.created_at.desc())
			.offset(skip)
			.limit(limit)
			.all()
		)

	def get_all(self, skip: int = 0, limit: int = 100) -> list[RefreshToken]:
		"""Return a paginated list of all refresh tokens."""
		return (
			self.db.query(RefreshToken)
			.order_by(RefreshToken.created_at.desc())
			.offset(skip)
			.limit(limit)
			.all()
		)

	# ---- Write operations ------------------------------------------------

	def create(self, token: RefreshToken) -> RefreshToken:
		"""Insert a new refresh token row."""
		self.db.add(token)
		self.db.commit()
		self.db.refresh(token)
		return token

	def update(self, db_token: RefreshToken, update_data: dict) -> RefreshToken:
		"""Apply updates to a refresh token record."""
		for key, value in update_data.items():
			setattr(db_token, key, value)
		self.db.commit()
		self.db.refresh(db_token)
		return db_token

	def revoke(
		self, db_token: RefreshToken, revoked_at: Optional[datetime] = None
	) -> RefreshToken:
		"""Mark a refresh token as revoked."""
		db_token.revoked = True
		db_token.revoked_at = revoked_at or datetime.now(timezone.utc)
		self.db.commit()
		self.db.refresh(db_token)
		return db_token

	def revoke_all_for_user(self, user_id: uuid.UUID) -> int:
		"""Revoke all active refresh tokens for a user. Returns affected row count."""
		count = (
			self.db.query(RefreshToken)
			.filter(
				RefreshToken.user_id == user_id,
				RefreshToken.revoked.is_(False),
			)
			.update(
				{
					RefreshToken.revoked: True,
					RefreshToken.revoked_at: datetime.now(timezone.utc),
				},
				synchronize_session=False,
			)
		)
		self.db.commit()
		return count

	def delete(self, db_token: RefreshToken) -> None:
		"""Delete a refresh token record."""
		self.db.delete(db_token)
		self.db.commit()
