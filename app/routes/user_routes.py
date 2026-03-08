"""
User Routes — the API endpoints that the client calls.

This is the *thinnest* layer. A route should:
  1. Accept the request
  2. Call the service
  3. Return the response

All business logic is in the service, all DB work is in the repository.
"""

from fastapi import APIRouter, Depends, status, HTTPException, Query
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta
from uuid import UUID
from typing import Optional

from app.db.session import get_db
from app.schemas.user import UserCreate, UserUpdate, UserResponse, Token
from app.services import UserService
from app.core import security, config
from app.models.user import User

# Create a router — this groups all user-related endpoints together
router = APIRouter(
    prefix="/users",   # all routes here start with /users
    tags=["Users"],     # shows up as a group in the Swagger docs
)


# ============================================================
#  POST /users/login  →  Auth & Get Token
# ============================================================
@router.post("/login", response_model=Token)
def login(db: Session = Depends(get_db), form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Login to get a JWT token.
    FastAPI's OAuth2PasswordRequestForm expects 'username' (we use email) and 'password'.
    """
    # 1. Fetch user
    service = UserService(db)
    try:
        user = service.get_user_by_email(email=form_data.username)
    except HTTPException:
        user = None
    
    if not user or not security.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 2. Create token
    access_token_expires = timedelta(minutes=config.settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        data={"sub": str(user.id)}, expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}


# ============================================================
#  POST /users  →  Create a new user
# ============================================================
@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(user_data: UserCreate, db: Session = Depends(get_db)):
    """
    Register a new user.

    - **email**: must be unique
    - **password**: will be hashed before saving
    """
    service = UserService(db)
    return service.create_user(user_data)


# ============================================================
#  GET /users  →  List all users (with optional pagination)
# ============================================================
@router.get("/", response_model=list[UserResponse])
def get_all_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    is_admin: Optional[bool] = Query(None, description="Filter by admin status"),
    db: Session = Depends(get_db),
    current_admin: User = Depends(security.get_current_admin_user),
):
    """
    Retrieve a list of users.

    - **skip**: number of records to skip (for pagination)
    - **limit**: max number of records to return
    - **is_active**: filter by active status (true/false)
    - **is_admin**: filter by admin status (true/false)
    """
    service = UserService(db)
    return service.get_all_users(
        skip=skip, limit=limit, is_active=is_active, is_admin=is_admin
    )


# ============================================================
#  GET /users/{user_id}  →  Get one user by ID
# ============================================================
@router.get("/{user_id}", response_model=UserResponse)
def get_user(user_id: UUID, db: Session = Depends(get_db)):
    """Retrieve a single user by their ID."""
    service = UserService(db)
    return service.get_user(user_id)


# ============================================================
#  PATCH /users/{user_id}  →  Update a user (owner or admin)
# ============================================================
@router.patch("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: UUID,
    user_data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(security.get_current_user),
):
    """
    Update user information. Owner can update own profile.
    Only admins can change is_admin / is_active.
    """
    # Only the owner or an admin can update
    if current_user.id != user_id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own account",
        )
    # Only admins can flip is_admin / is_active
    if (user_data.is_admin is not None or user_data.is_active is not None) and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can change is_admin or is_active",
        )
    service = UserService(db)
    return service.update_user(user_id, user_data)


#  DELETE /users/{user_id}  →  Delete a user (admin only)
# ============================================================
@router.delete("/{user_id}", status_code=status.HTTP_200_OK)
def delete_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(security.get_current_admin_user),
):
    """Permanently delete a user. Admin only."""
    service = UserService(db)
    service.delete_user(user_id)
    return {"message": "User deleted successfully."}
