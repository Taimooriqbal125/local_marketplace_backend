"""
User Service — business logic lives here.
"""

import uuid
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from typing import Optional, List

from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate
from app.repositories import UserRepository
from app.core.security import hash_password


class UserService:
    """Service layer for User business logic."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = UserRepository(db)

    def create_user(self, user_data: UserCreate) -> User:
        """Register a new user."""
        # 1. Business rule: no duplicate emails
        existing = self.repo.get_by_email(user_data.email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A user with this email already exists"
            )

        # 2. Business rule: no duplicate phone numbers
        if user_data.phone:
            existing_phone = self.repo.get_by_phone(user_data.phone)
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
            phone=user_data.phone,
        )

        return self.repo.create(new_user)

    def get_user_by_email(self, email: str) -> User:
        """Get a user by email. Raises 404 if not found."""
        user = self.repo.get_by_email(email)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        return user

    def get_user(self, user_id: uuid.UUID) -> User:
        """Get a user by ID. Raises 404 if not found."""
        user = self.repo.get(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        return user

    def get_all_users(
        self,
        skip: int = 0,
        limit: int = 100,
        is_active: Optional[bool] = None,
        is_admin: Optional[bool] = None,
    ) -> List[User]:
        """Get a paginated and filtered list of all users."""
        return self.repo.get_all(
            skip=skip, limit=limit, is_active=is_active, is_admin=is_admin
        )

    def update_user(self, user_id: uuid.UUID, user_data: UserUpdate) -> User:
        """Update a user's info."""
        db_user = self.get_user(user_id)
        update_data = user_data.model_dump(exclude_unset=True)

        if "phone_number" in update_data:
            new_phone = update_data["phone_number"]
            existing_phone = self.repo.get_by_phone(new_phone)
            if existing_phone and existing_phone.id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="A user with this phone number already exists"
                )
            update_data["phone"] = update_data.pop("phone_number")

        if "password" in update_data:
            update_data["hashed_password"] = hash_password(update_data.pop("password"))

        return self.repo.update(db_user, update_data)

    def delete_user(self, user_id: uuid.UUID) -> None:
        """Delete a user by ID."""
        db_user = self.get_user(user_id)
        self.repo.delete(db_user)
