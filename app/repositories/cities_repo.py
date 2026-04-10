"""
City Repository — handles database operations for the City model.
Modernized to SQLAlchemy 2.0 select syntax and safely bridges snake_case schemas with camelCase DB columns.
"""

import uuid
from typing import Optional, List

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.cities import City
from app.schemas.cities import CityCreate, CityUpdate


CITY_MODEL_MAP = {
    "center_point": "centerPoint",
    "is_active": "isActive"
}


class CityRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, city_id: uuid.UUID) -> Optional[City]:
        stmt = select(City).where(City.id == city_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_slug(self, slug: str) -> Optional[City]:
        stmt = select(City).where(City.slug == slug)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_name_and_country(self, name: str, country: str) -> Optional[City]:
        stmt = select(City).where(City.name == name, City.country == country)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_all(self, skip: int = 0, limit: int = 100) -> List[City]:
        stmt = select(City).offset(skip).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def create(self, obj_in: CityCreate) -> City:
        data = obj_in.model_dump()
        db_data = {}
        
        for key, value in data.items():
            model_key = CITY_MODEL_MAP.get(key, key)
            db_data[model_key] = value

        db_obj = City(**db_data)
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def update(self, db_obj: City, obj_in: CityUpdate) -> City:
        update_data = obj_in.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            model_key = CITY_MODEL_MAP.get(key, key)
            setattr(db_obj, model_key, value)
            
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def delete(self, db_obj: City) -> None:
        self.db.delete(db_obj)
        self.db.commit()
