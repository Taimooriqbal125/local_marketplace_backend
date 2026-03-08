"""
User Repository — the *only* layer that talks to the database.
"""

import uuid
from sqlalchemy.orm import Session
from typing import Optional, List

from app.models.user import User


class UserRepository:
    """Class-based repository for User database operations."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, user_id: uuid.UUID) -> Optional[User]:
        """Fetch a single user by primary key."""
        return self.db.query(User).filter(User.id == user_id).first()

    def get_by_email(self, email: str) -> Optional[User]:
        """Fetch a single user by email."""
        return self.db.query(User).filter(User.email == email).first()

    def get_by_phone(self, phone: str) -> Optional[User]:
        """Fetch a single user by phone number."""
        return self.db.query(User).filter(User.phone == phone).first()

    def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        is_active: Optional[bool] = None,
        is_admin: Optional[bool] = None,
    ) -> List[User]:
        """Return a paginated and optionally filtered list of users."""
        query = self.db.query(User)
        if is_active is not None:
            query = query.filter(User.is_active == is_active)
        if is_admin is not None:
            query = query.filter(User.is_admin == is_admin)
        return query.offset(skip).limit(limit).all()

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

    def delete(self, db_user: User) -> None:
        """Permanently remove a user from the database."""
        self.db.delete(db_user)
        self.db.commit()
