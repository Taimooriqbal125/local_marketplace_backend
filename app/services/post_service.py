"""
Post Service — business logic for Posts.
"""

from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models import Post
from app.schemas import PostCreate, PostUpdate
from app.repositories import post_repo

def create_post(db: Session, post_data: PostCreate, owner_id: int) -> Post:
    new_post = Post(
        title=post_data.title,
        content=post_data.content,
        owner_id=owner_id
    )
    return post_repo.create_post(db, new_post)

def get_posts(db: Session, skip: int = 0, limit: int = 100) -> list[Post]:
    return post_repo.get_posts(db, skip=skip, limit=limit)

def get_post(db: Session, post_id: int) -> Post:
    post = post_repo.get_post_by_id(db, post_id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found"
        )
    return post

def update_post(db: Session, post_id: int, post_data: PostUpdate, user_id: int) -> Post:
    db_post = get_post(db, post_id)
    
    # Check if user owns the post
    if db_post.owner_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this post"
        )
        
    update_data = post_data.model_dump(exclude_unset=True)
    return post_repo.update_post(db, db_post, update_data)

def delete_post(db: Session, post_id: int, user_id: int) -> None:
    db_post = get_post(db, post_id)
    
    # Check if user owns the post
    if db_post.owner_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this post"
        )
        
    post_repo.delete_post(db, db_post)
