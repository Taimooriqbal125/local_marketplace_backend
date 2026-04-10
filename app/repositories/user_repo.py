"""
User Repository — handles direct database operations for the User model.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, List

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User


class UserRepository:
    """Class-based repository for User database operations."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, user_id: uuid.UUID) -> Optional[User]:
        """Fetch a single user by primary key."""
        stmt = select(User).where(User.id == user_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_email(self, email: str) -> Optional[User]:
        """Fetch a single user by email."""
        stmt = select(User).where(User.email == email)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_phone(self, phone: str) -> Optional[User]:
        """Fetch a single user by phone number."""
        stmt = select(User).where(User.phone == phone)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        is_active: Optional[bool] = None,
        is_admin: Optional[bool] = None,
    ) -> List[User]:
        """Return a paginated and optionally filtered list of users."""
        stmt = select(User)
        if is_active is not None:
            stmt = stmt.where(User.is_active == is_active)
        if is_admin is not None:
            stmt = stmt.where(User.is_admin == is_admin)
            
        stmt = stmt.offset(skip).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def create(self, user: User) -> User:
        """Insert a new user into the database."""
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def update(self, db_user: User, update_data: dict) -> User:
        """Apply a dict of changes to an existing user."""
        for key, value in update_data.items():
            setattr(db_user, key, value)
        self.db.commit()
        self.db.refresh(db_user)
        return db_user

    def touch_last_active_if_stale(
        self,
        db_user: User,
        min_interval: timedelta = timedelta(minutes=5),
    ) -> User:
        """Update last_active_at only when it's older than the interval (or missing)."""
        now_utc = datetime.now(timezone.utc)
        last_active = db_user.last_active_at

        if last_active is not None and last_active.tzinfo is None:
            # Defensively treat naive timestamps as UTC.
            last_active = last_active.replace(tzinfo=timezone.utc)

        if last_active is None or (now_utc - last_active) > min_interval:
            db_user.last_active_at = now_utc
            self.db.commit()
            self.db.refresh(db_user)

        return db_user

    def delete(self, db_user: User) -> None:
        """Permanently remove a user from the database."""
        self.db.delete(db_user)
        self.db.commit()
