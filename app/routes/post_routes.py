"""
Post Routes — API endpoints for Posts.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas import PostCreate, PostUpdate, PostResponse
from app.services import post_service
from app.core.security import get_current_user
from app.models import User

router = APIRouter(
    prefix="/posts",
    tags=["Posts"],
)

@router.post("/", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
def create_post(
    post_data: PostCreate, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new post for the logged-in user."""
    return post_service.create_post(db, post_data, owner_id=current_user.id)

@router.get("/", response_model=list[PostResponse])
def get_posts(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Retrieve a list of posts."""
    return post_service.get_posts(db, skip=skip, limit=limit)

@router.get("/{post_id}", response_model=PostResponse)
def get_post(post_id: int, db: Session = Depends(get_db)):
    """Get a specific post by ID."""
    return post_service.get_post(db, post_id)

@router.put("/{post_id}", response_model=PostResponse)
def update_post(
    post_id: int, 
    post_data: PostUpdate, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a post (only if you are the owner)."""
    return post_service.update_post(db, post_id, post_data, user_id=current_user.id)

@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_post(
    post_id: int, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a post (only if you are the owner)."""
    post_service.delete_post(db, post_id, user_id=current_user.id)
