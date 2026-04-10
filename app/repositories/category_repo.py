"""
Category Repository — handles direct database operations for the Category model.
"""

import uuid
from typing import Optional, List

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.category import Category
from app.schemas.category import CategoryCreate, CategoryUpdate


class CategoryRepository:
    """Class-based repository for Category database operations."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, category_id: uuid.UUID) -> Optional[Category]:
        """Fetch a single category by its ID."""
        stmt = select(Category).where(Category.id == category_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_slug(self, slug: str) -> Optional[Category]:
        """Fetch a single category by its unique slug."""
        stmt = select(Category).where(Category.slug == slug)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_all(self, skip: int = 0, limit: int = 100) -> List[Category]:
        """Fetch a paginated list of all categories."""
        stmt = select(Category).offset(skip).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def get_parent_categories(self, skip: int = 0, limit: int = 100) -> List[Category]:
        """Fetch a paginated list of top-level categories (no parent)."""
        stmt = select(Category).where(Category.parent_id.is_(None)).offset(skip).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def get_children(self, parent_id: uuid.UUID, skip: int = 0, limit: int = 100) -> List[Category]:
        """Fetch child categories for a specific parent ID."""
        stmt = select(Category).where(Category.parent_id == parent_id).offset(skip).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def get_tree(self, parent_id: Optional[uuid.UUID] = None) -> List[Category]:
        """Fetch all categories for a specific parent unconditionally."""
        stmt = select(Category).where(Category.parent_id == parent_id)
        return list(self.db.execute(stmt).scalars().all())

    def create(self, obj_in: CategoryCreate) -> Category:
        """Insert a new category into the database."""
        db_obj = Category(**obj_in.model_dump())
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def update(self, db_obj: Category, obj_in: CategoryUpdate) -> Category:
        """Apply a dictionary of changes to an existing category."""
        update_data = obj_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_obj, field, value)
            
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def delete(self, db_obj: Category) -> None:
        """Permanently remove a category from the database."""
        self.db.delete(db_obj)
        self.db.commit()
