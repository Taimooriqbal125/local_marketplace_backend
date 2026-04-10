import uuid
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.services.category_service import CategoryService
from app.schemas.category import (
    CategoryCreate,
    CategoryUpdate,
    CategoryOut,
    CategoryParentOut,
    CategoryTreeOut,
)
from app.db.session import get_db
from app.core.security import get_current_admin_user
from app.models.user import User
from typing import List

router = APIRouter(prefix="/categories", tags=["categories"])

@router.get("/", response_model=List[CategoryOut])
def list_categories(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return CategoryService(db).list_categories(skip=skip, limit=limit)

@router.get("/parentcategories", response_model=List[CategoryParentOut])
def list_parent_categories(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return CategoryService(db).list_parent_categories(skip=skip, limit=limit)

@router.get("/parent/{parent_id}/children", response_model=List[CategoryOut])
def list_categories_by_parent(
    parent_id: uuid.UUID,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    return CategoryService(db).list_categories_by_parent(
        parent_id=parent_id,
        skip=skip,
        limit=limit,
    )

@router.get("/tree/", response_model=List[CategoryTreeOut])
def get_category_tree(parent_id: uuid.UUID | None = None, db: Session = Depends(get_db)):
    return CategoryService(db).get_category_tree(parent_id)

@router.get("/slug/{slug}", response_model=CategoryOut)
def get_category_by_slug(slug: str, db: Session = Depends(get_db)):
    return CategoryService(db).get_category_by_slug(slug)

@router.get("/{category_id}", response_model=CategoryOut)
def get_category(category_id: uuid.UUID, db: Session = Depends(get_db)):
    return CategoryService(db).get_category(category_id)

@router.post("/", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
def create_category(
    obj_in: CategoryCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin_user),
):
    return CategoryService(db).create_category(obj_in)

@router.patch("/{category_id}", response_model=CategoryOut)
def update_category(
    category_id: uuid.UUID,
    obj_in: CategoryUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin_user),
):
    return CategoryService(db).update_category(category_id, obj_in)

@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(
    category_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin_user),
):
    CategoryService(db).delete_category(category_id)
    return None

@router.get("/admin/{category_id}", response_model=CategoryTreeOut)
def get_category_admin(
    category_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin_user),
):
    """
    Admin-only: Retrieve detailed category info including subcategories.
    """
    return CategoryService(db).get_category_admin(category_id)
