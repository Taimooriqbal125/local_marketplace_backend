from sqlalchemy.orm import Session
from app.models.category import Category
from app.schemas.category import CategoryCreate, CategoryUpdate

class CategoryRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, category_id: int) -> Category | None:
        return self.db.query(Category).filter(Category.id == category_id).first()

    def get_by_slug(self, slug: str) -> Category | None:
        return self.db.query(Category).filter(Category.slug == slug).first()

    def get_all(self, skip: int = 0, limit: int = 100) -> list[Category]:
        return self.db.query(Category).offset(skip).limit(limit).all()

    def create(self, obj_in: CategoryCreate) -> Category:
        db_obj = Category(**obj_in.model_dump())
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def update(self, db_obj: Category, obj_in: CategoryUpdate) -> Category:
        update_data = obj_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_obj, field, value)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def delete(self, db_obj: Category) -> None:
        self.db.delete(db_obj)
        self.db.commit()

    def get_children(self, parent_id: int) -> list[Category]:
        return self.db.query(Category).filter(Category.parent_id == parent_id).all()

    def get_tree(self, parent_id: int | None = None) -> list[Category]:
        return self.db.query(Category).filter(Category.parent_id == parent_id).all()
