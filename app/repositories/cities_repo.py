from sqlalchemy.orm import Session
from app.models.cities import City
from app.schemas.cities import CityCreate, CityUpdate
import uuid

class CityRepository:
	def __init__(self, db: Session):
		self.db = db

	def get(self, city_id: uuid.UUID) -> City | None:
		return self.db.query(City).filter(City.id == city_id).first()

	def get_by_slug(self, slug: str) -> City | None:
		return self.db.query(City).filter(City.slug == slug).first()

	def get_all(self, skip: int = 0, limit: int = 100) -> list[City]:
		return self.db.query(City).offset(skip).limit(limit).all()

	def create(self, obj_in: CityCreate) -> City:
		db_obj = City(
			name=obj_in.name,
			country=obj_in.country,
			centerPoint=obj_in.centerPoint,
			isActive=obj_in.isActive,
			slug=obj_in.slug
		)
		self.db.add(db_obj)
		self.db.commit()
		self.db.refresh(db_obj)
		return db_obj

	def update(self, db_obj: City, obj_in: CityUpdate) -> City:
		update_data = obj_in.model_dump(exclude_unset=True)
		for field in ["name", "country", "centerPoint", "isActive", "slug"]:
			if field in update_data:
				setattr(db_obj, field, update_data[field])
		self.db.commit()
		self.db.refresh(db_obj)
		return db_obj

	def delete(self, db_obj: City) -> None:
		self.db.delete(db_obj)
		self.db.commit()
