"""
User Repository — the *only* layer that talks to the database.

Why a separate repository?
  - Routes shouldn't write raw SQL / ORM queries
  - Services contain business logic but delegate DB work here
  - Makes it easy to swap databases or add caching later
"""

from sqlalchemy.orm import Session
from typing import Optional

from app.models.user import User


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    """Fetch a single user by primary key."""
    return db.query(User).filter(User.id == user_id).first()


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """Fetch a single user by email (useful for login / duplicate checks)."""
    return db.query(User).filter(User.email == email).first()


def get_all_users(db: Session, skip: int = 0, limit: int = 100) -> list[User]:
    """Return a paginated list of users."""
    return db.query(User).offset(skip).limit(limit).all()


def create_user(db: Session, user: User) -> User:
    """Insert a new user into the database."""
    db.add(user)
    db.commit()
    db.refresh(user)  # reload to get the auto-generated id, timestamps, etc.
    return user


def update_user(db: Session, db_user: User, update_data: dict) -> User:
    """
    Apply a dict of changes to an existing user.
    Only keys present in update_data are updated.
    """
    for key, value in update_data.items():
        setattr(db_user, key, value)
    db.commit()
    db.refresh(db_user)
    return db_user


def delete_user(db: Session, db_user: User) -> None:
    """Permanently remove a user from the database."""
    db.delete(db_user)
    db.commit()
