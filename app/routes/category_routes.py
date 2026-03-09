import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.services.category_service import CategoryService
from app.schemas.category import CategoryCreate, CategoryUpdate, CategoryOut, CategoryTreeOut
from app.db.session import get_db
from app.core.security import get_current_admin_user
from app.models.user import User
from typing import List

router = APIRouter(prefix="/categories", tags=["categories"])

@router.get("/", response_model=List[CategoryOut])
def list_categories(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    service = CategoryService(db)
    return service.list_categories(skip=skip, limit=limit)

@router.get("/{category_id}", response_model=CategoryOut)
def get_category(category_id: uuid.UUID, db: Session = Depends(get_db)):
    service = CategoryService(db)
    category = service.get_category(category_id)
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    return category

@router.get("/slug/{slug}", response_model=CategoryOut)
def get_category_by_slug(slug: str, db: Session = Depends(get_db)):
    service = CategoryService(db)
    category = service.get_category_by_slug(slug)
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    return category

@router.post("/", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
def create_category(
    obj_in: CategoryCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin_user),
):
    service = CategoryService(db)
    return service.create_category(obj_in)

@router.patch("/{category_id}", response_model=CategoryOut)
def update_category(
    category_id: uuid.UUID,
    obj_in: CategoryUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin_user),
):
    service = CategoryService(db)
    category = service.update_category(category_id, obj_in)
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    return category

@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(
    category_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin_user),
):
    service = CategoryService(db)
    success = service.delete_category(category_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
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
    service = CategoryService(db)
    category = service.get_category_admin(category_id)
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    return category

@router.get("/tree/", response_model=List[CategoryTreeOut])
def get_category_tree(parent_id: uuid.UUID | None = None, db: Session = Depends(get_db)):
    service = CategoryService(db)
    return service.get_category_tree(parent_id)
