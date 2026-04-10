"""
User Service — business logic lives here.
"""

import uuid
from datetime import timedelta
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from typing import Optional, List

from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate
from app.repositories import UserRepository
from app.core.security import hash_password
from app.services.otp_token_service import OTPTokenService
from app.models.otp_token import OTPPurpose


class UserNotFoundError(HTTPException):
    def __init__(self, detail: str = "User not found"):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


class UserConflictError(HTTPException):
    def __init__(self, detail: str = "A user with this email already exists"):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


class PhoneConflictError(HTTPException):
    def __init__(self, detail: str = "A user with this phone number already exists"):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


class UserForbiddenError(HTTPException):
    def __init__(self, detail: str = "You do not have permission to perform this action"):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


class UserService:
    """Service layer for User business logic."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = UserRepository(db)
        self.otp_service = OTPTokenService(db)

    def login(self, email: str, password: str) -> dict:
        """Authenticate a user and return the token payload."""
        try:
            user = self.get_user_by_email(email)
        except UserNotFoundError:
            user = None
            
        from app.core import security, config
        if not user or not security.verify_password(password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        user = self.touch_last_active(user)
        access_token_expires = timedelta(minutes=config.settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = security.create_access_token(
            data={"sub": str(user.id)}, expires_delta=access_token_expires
        )
        
        from app.services.refresh_token_service import RefreshTokenService
        refresh_token_service = RefreshTokenService(self.db)
        raw_refresh_token, _ = refresh_token_service.issue_token(user.id)
        
        return {
            "access_token": access_token,
            "refresh_token": raw_refresh_token,
            "token_type": "bearer",
            "user": user,
        }

    def create_user(self, user_data: UserCreate) -> User:
        """Register a new user."""
        # 1. Business rule: no duplicate emails
        existing = self.repo.get_by_email(user_data.email)
        if existing:
            raise UserConflictError()

        # 2. Business rule: no duplicate phone numbers
        if user_data.phone:
            existing_phone = self.repo.get_by_phone(user_data.phone)
            if existing_phone:
                raise PhoneConflictError()

        # 3. Hash the password before saving
        new_user = User(
            email=user_data.email,
            hashed_password=hash_password(user_data.password),
            is_admin=user_data.is_admin,
            phone=user_data.phone,
            is_email_verified=False, # Explicitly set to false on signup
        )

        user = self.repo.create(new_user)

        # 4. Trigger OTP Service: Generate and print (or send) OTP safely
        try:
            plain_otp = self.otp_service.create_otp(
                email=user.email,
                purpose=OTPPurpose.SIGNUP_VERIFY,
                user_id=user.id
            )
            print(
                f"[OTP-TEST] Signup OTP for {user.email}: {plain_otp} "
                f"(purpose={OTPPurpose.SIGNUP_VERIFY.value})"
            )
        except Exception as e:
            print(f"[ERROR] Failed to send signup OTP: {e}")

        return user

    def get_user_by_email(self, email: str) -> User:
        """Get a user by email. Raises 404 if not found."""
        user = self.repo.get_by_email(email)
        if not user:
            raise UserNotFoundError()
        return user

    def get_user(self, user_id: uuid.UUID) -> User:
        """Get a user by ID. Raises 404 if not found."""
        user = self.repo.get(user_id)
        if not user:
            raise UserNotFoundError()
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

    def update_user(self, user_id: uuid.UUID, user_data: UserUpdate, current_user: User) -> User:
        """Update a user's info enforcing uniqueness checks and authorization safely."""
        # Only the owner or an admin can update
        if current_user.id != user_id and not current_user.is_admin:
            raise UserForbiddenError("You can only update your own account")
            
        # Only admins can flip is_admin / is_active
        if (user_data.is_admin is not None or user_data.is_active is not None) and not current_user.is_admin:
            raise UserForbiddenError("Only admins can change is_admin or is_active")

        db_user = self.get_user(user_id)
        update_data = user_data.model_dump(exclude_unset=True)

        if "phone" in update_data:
            new_phone = update_data["phone"]
            existing_phone = self.repo.get_by_phone(new_phone)
            if existing_phone and existing_phone.id != user_id:
                raise PhoneConflictError()

        if "password" in update_data:
            update_data["hashed_password"] = hash_password(update_data.pop("password"))

        return self.repo.update(db_user, update_data)

    def delete_user(self, user_id: uuid.UUID) -> None:
        """Delete a user by ID."""
        db_user = self.get_user(user_id)
        self.repo.delete(db_user)

    def touch_last_active(self, user: User, min_interval: timedelta = timedelta(minutes=5)) -> User:
        """Refresh the user's activity timestamp when stale."""
        return self.repo.touch_last_active_if_stale(db_user=user, min_interval=min_interval)
