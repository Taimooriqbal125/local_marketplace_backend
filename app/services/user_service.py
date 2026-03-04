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

import uuid
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate
from app.repositories import user_repo
from app.core.security import hash_password
from typing import Optional


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

    # 2. Business rule: no duplicate phone numbers
    if user_data.phone_number:
        existing_phone = user_repo.get_user_by_phone(db, user_data.phone_number)
        if existing_phone:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A user with this phone number already exists"
            )

    # 3. Hash the password before saving
    new_user = User(
        email=user_data.email,
        hashed_password=hash_password(user_data.password),
        is_admin=user_data.is_admin,
        phone=user_data.phone_number,
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


def get_user(db: Session, user_id: uuid.UUID) -> User:
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


def get_all_users(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    is_active: Optional[bool] = None,
    is_admin: Optional[bool] = None,
) -> list[User]:
    """Get a paginated and filtered list of all users."""
    return user_repo.get_all_users(
        db, skip=skip, limit=limit, is_active=is_active, is_admin=is_admin
    )


def update_user(db: Session, user_id: uuid.UUID, user_data: UserUpdate) -> User:
    """
    Update a user's info.
    Only fields that are sent get updated (partial update).
    """
    db_user = get_user(db, user_id)  # reuse the 404 check from above

    # Build a dict of only the fields the client actually sent
    update_data = user_data.model_dump(exclude_unset=True)

    # If they're updating the phone number, map it to the model's 'phone' field
    if "phone_number" in update_data:
        new_phone = update_data["phone_number"]
        # Business rule: check for duplicates but skip the current user
        existing_phone = user_repo.get_user_by_phone(db, new_phone)
        if existing_phone and existing_phone.id != user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A user with this phone number already exists"
            )
        update_data["phone"] = update_data.pop("phone_number")

    # If they're updating the password, hash the new one
    if "password" in update_data:
        update_data["hashed_password"] = hash_password(update_data.pop("password"))

    return user_repo.update_user(db, db_user, update_data)


def delete_user(db: Session, user_id: uuid.UUID) -> None:
    """
    Delete a user by ID.
    Raises 404 if the user doesn't exist.
    """
    db_user = get_user(db, user_id)  # 404 check
    user_repo.delete_user(db, db_user)
