"""
Category Service — service layer for Category operations.
"""

import uuid
from typing import Sequence, List
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status

from app.repositories.category_repo import CategoryRepository
from app.schemas.category import (
    CategoryCreate,
    CategoryUpdate,
    CategoryOut,
    CategoryParentOut,
    CategoryTreeOut,
)

class CategoryNotFoundError(HTTPException):
    def __init__(self, detail: str = "Category not found"):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)

class CategoryConflictError(HTTPException):
    def __init__(self, detail: str = "A category with this slug or name already exists."):
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=detail)

class CategoryService:
    """Service layer for Category operations, encapsulating business logic."""

    def __init__(self, db: Session) -> None:
        self.repo = CategoryRepository(db)

    def get_category(self, category_id: uuid.UUID) -> CategoryOut:
        """Fetch a single category or raise 404."""
        category = self.repo.get(category_id)
        if not category:
            raise CategoryNotFoundError()
        return CategoryOut.model_validate(category)

    def get_category_by_slug(self, slug: str) -> CategoryOut:
        """Fetch a single category by slug or raise 404."""
        category = self.repo.get_by_slug(slug)
        if not category:
            raise CategoryNotFoundError()
        return CategoryOut.model_validate(category)

    def list_categories(self, skip: int = 0, limit: int = 100) -> Sequence[CategoryOut]:
        categories = self.repo.get_all(skip=skip, limit=limit)
        return [CategoryOut.model_validate(cat) for cat in categories]

    def list_parent_categories(self, skip: int = 0, limit: int = 100) -> Sequence[CategoryParentOut]:
        categories = self.repo.get_parent_categories(skip=skip, limit=limit)
        return [CategoryParentOut.model_validate(cat) for cat in categories]

    def list_categories_by_parent(
        self, parent_id: uuid.UUID, skip: int = 0, limit: int = 100
    ) -> Sequence[CategoryOut]:
        parent = self.repo.get(parent_id)
        if not parent:
            raise CategoryNotFoundError("Parent category not found")

        categories = self.repo.get_children(parent_id=parent_id, skip=skip, limit=limit)
        return [CategoryOut.model_validate(cat) for cat in categories]

    def create_category(self, obj_in: CategoryCreate) -> CategoryOut:
        # Pre-check: slug must be unique
        if self.repo.get_by_slug(obj_in.slug):
            raise CategoryConflictError(f"A category with slug '{obj_in.slug}' already exists.")
            
        try:
            category = self.repo.create(obj_in)
            return CategoryOut.model_validate(category)
        except IntegrityError:
            raise CategoryConflictError()

    def update_category(self, category_id: uuid.UUID, obj_in: CategoryUpdate) -> CategoryOut:
        category = self.repo.get(category_id)
        if not category:
            raise CategoryNotFoundError()
            
        try:
            updated = self.repo.update(category, obj_in)
            return CategoryOut.model_validate(updated)
        except IntegrityError:
            raise CategoryConflictError("Update failed: A category with this slug or name already exists.")

    def delete_category(self, category_id: uuid.UUID) -> None:
        category = self.repo.get(category_id)
        if not category:
            raise CategoryNotFoundError()
            
        self.repo.delete(category)

    def get_category_admin(self, category_id: uuid.UUID) -> CategoryTreeOut:
        """Admin-only: Fetch category details with immediate children."""
        category = self.repo.get(category_id)
        if not category:
            raise CategoryNotFoundError()
        return CategoryTreeOut.model_validate(category)

    def get_category_tree(self, parent_id: uuid.UUID | None = None) -> List[CategoryTreeOut]:
        """
        Builds a full category tree recursively in-memory to prevent N+1 queries.
        Fetches all categories once and constructs the tree hierarchy.
        """
        all_categories = self.repo.get_all(skip=0, limit=1000)
        
        # Build a mapping of parent_id -> list of children
        children_map = {}
        for cat in all_categories:
            pid = cat.parent_id
            if pid not in children_map:
                children_map[pid] = []
            children_map[pid].append(cat)
            
        def build_tree(current_id: uuid.UUID | None) -> List[CategoryTreeOut]:
            result = []
            children = children_map.get(current_id, [])
            for child in children:
                # Recursively get children of this node
                node_children = build_tree(child.id)
                # Ensure dictionary has required values for Pydantic mapping
                child_data = child.__dict__.copy()
                child_data.pop("_sa_instance_state", None)
                child_data["children"] = node_children
                
                result.append(CategoryTreeOut.model_validate(child_data))
            return result
            
        return build_tree(parent_id)
