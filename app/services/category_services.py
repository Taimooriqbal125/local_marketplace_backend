from sqlalchemy.orm import Session
from app.repositories.category_repo import CategoryRepository
from app.schemas.category import CategoryCreate, CategoryUpdate, CategoryOut, CategoryTreeOut
from app.models.category import Category
from typing import Sequence

class CategoryService:
    def __init__(self, db: Session):
        self.repo = CategoryRepository(db)

    def get_category(self, category_id: int) -> CategoryOut | None:
        category = self.repo.get(category_id)
        if category:
            return CategoryOut.model_validate(category)
        return None

    def get_category_by_slug(self, slug: str) -> CategoryOut | None:
        category = self.repo.get_by_slug(slug)
        if category:
            return CategoryOut.model_validate(category)
        return None

    def list_categories(self, skip: int = 0, limit: int = 100) -> Sequence[CategoryOut]:
        categories = self.repo.get_all(skip=skip, limit=limit)
        return [CategoryOut.model_validate(cat) for cat in categories]

    def create_category(self, obj_in: CategoryCreate) -> CategoryOut:
        category = self.repo.create(obj_in)
        return CategoryOut.model_validate(category)

    def update_category(self, category_id: int, obj_in: CategoryUpdate) -> CategoryOut | None:
        category = self.repo.get(category_id)
        if not category:
            return None
        updated = self.repo.update(category, obj_in)
        return CategoryOut.model_validate(updated)

    def delete_category(self, category_id: int) -> bool:
        category = self.repo.get(category_id)
        if not category:
            return False
        self.repo.delete(category)
        return True

    def get_category_tree(self, parent_id: int | None = None) -> list[CategoryTreeOut]:
        def build_tree(parent_id):
            nodes = self.repo.get_children(parent_id)
            result = []
            for node in nodes:
                children = build_tree(node.id)
                result.append(CategoryTreeOut.model_validate({
                    **node.__dict__,
                    "children": children
                }))
            return result
        return build_tree(parent_id)
