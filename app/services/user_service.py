"""
User Service — business logic lives here.

This layer sits between Routes and Repositories:
  Route  →  Service  →  Repository  →  Database

The service:
  ✅ Validates business rules (e.g. "email must be unique")
  ✅ Hashes passwords before saving
  ✅ Raises HTTPExceptions with proper status codes
  ❌ Does NOT write raw DB queries (that's the repo's job)
  ❌ Does NOT know about HTTP requests/responses (that's the route's job)
"""

from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate
from app.repositories import user_repo
from app.core.security import hash_password


def create_user(db: Session, user_data: UserCreate) -> User:
    """
    Register a new user.
    Raises 400 if the email is already taken.
    """
    # 1. Business rule: no duplicate emails
    existing = user_repo.get_user_by_email(db, user_data.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email already exists"
        )

    # 2. Hash the password before saving
    new_user = User(
        name=user_data.name,
        email=user_data.email,
        hashed_password=hash_password(user_data.password),
        is_admin=user_data.is_admin,
    )

    # 3. Delegate the actual DB insert to the repository
    return user_repo.create_user(db, new_user)


def get_user_by_email(db: Session, email: str) -> User:
    """
    Get a user by email.
    Raises 404 if not found.
    """
    user = user_repo.get_user_by_email(db, email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user


def get_user(db: Session, user_id: int) -> User:
    """
    Get a user by ID.
    Raises 404 if not found.
    """
    user = user_repo.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user


def get_all_users(db: Session, skip: int = 0, limit: int = 100) -> list[User]:
    """Get a paginated list of all users."""
    return user_repo.get_all_users(db, skip=skip, limit=limit)


def update_user(db: Session, user_id: int, user_data: UserUpdate) -> User:
    """
    Update a user's info.
    Only fields that are sent get updated (partial update).
    """
    db_user = get_user(db, user_id)  # reuse the 404 check from above

    # Build a dict of only the fields the client actually sent
    update_data = user_data.model_dump(exclude_unset=True)

    # If they're updating the password, hash the new one
    if "password" in update_data:
        update_data["hashed_password"] = hash_password(update_data.pop("password"))

    return user_repo.update_user(db, db_user, update_data)


def delete_user(db: Session, user_id: int) -> None:
    """
    Delete a user by ID.
    Raises 404 if the user doesn't exist.
    """
    db_user = get_user(db, user_id)  # 404 check
    user_repo.delete_user(db, db_user)
