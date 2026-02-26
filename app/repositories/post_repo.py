"""
Post Repository — database interactions for Posts.
"""

from sqlalchemy.orm import Session
from typing import Optional

from app.models import Post

def get_post_by_id(db: Session, post_id: int) -> Optional[Post]:
    return db.query(Post).filter(Post.id == post_id).first()

def get_posts(db: Session, skip: int = 0, limit: int = 100) -> list[Post]:
    return db.query(Post).offset(skip).limit(limit).all()

def get_user_posts(db: Session, user_id: int) -> list[Post]:
    return db.query(Post).filter(Post.owner_id == user_id).all()

def create_post(db: Session, post: Post) -> Post:
    db.add(post)
    db.commit()
    db.refresh(post)
    return post

def update_post(db: Session, db_post: Post, update_data: dict) -> Post:
    for key, value in update_data.items():
        setattr(db_post, key, value)
    db.commit()
    db.refresh(db_post)
    return db_post

def delete_post(db: Session, db_post: Post) -> None:
    db.delete(db_post)
    db.commit()
