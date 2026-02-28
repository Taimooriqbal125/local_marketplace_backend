"""
Security utilities — password hashing and JWT tokens.
"""

import uuid
import bcrypt
from datetime import datetime, timedelta
from typing import Optional

from jose import jwt, JWTError
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.user import User
from app.repositories import user_repo

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


# ---------- Password Hashing ----------

def hash_password(plain_password: str) -> str:
    password_bytes = plain_password.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


# ---------- JWT Tokens ----------

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()

    # Ensure sub is always a string (UUID safe)
    if "sub" in to_encode and to_encode["sub"] is not None:
        to_encode["sub"] = str(to_encode["sub"])

    expire = datetime.utcnow() + (
        expires_delta if expires_delta else timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})

    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


# ---------- Dependencies ----------

def get_current_user(
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str | None = payload.get("sub")
        if not user_id:
            raise credentials_exception

        # Validate UUID format
        user_uuid = uuid.UUID(user_id)

    except (JWTError, ValueError):
        raise credentials_exception

    user = user_repo.get_user_by_id(db, user_id=user_uuid)
    if user is None:
        raise credentials_exception

    return user


def get_current_admin_user(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user does not have enough privileges",
        )
    return current_user