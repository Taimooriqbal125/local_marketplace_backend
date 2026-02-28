class DuplicateCityError(Exception):
	pass
import uuid
from sqlalchemy.orm import Session
from app.repositories.cities_repo import CityRepository
from app.schemas.cities import CityCreate, CityUpdate, CityOut
from app.models.cities import City
from typing import Sequence

class CityService:
	def __init__(self, db: Session):
		self.repo = CityRepository(db)

	def get_city(self, city_id: uuid.UUID) -> CityOut | None:
		city = self.repo.get(city_id)
		if city:
			return CityOut.model_validate(city)
		return None

	def get_city_by_slug(self, slug: str) -> CityOut | None:
		city = self.repo.get_by_slug(slug)
		if city:
			return CityOut.model_validate(city)
		return None

	def list_cities(self, skip: int = 0, limit: int = 100) -> Sequence[CityOut]:
		cities = self.repo.get_all(skip=skip, limit=limit)
		return [CityOut.model_validate(city) for city in cities]

	def create_city(self, obj_in: CityCreate) -> CityOut:
		# Check for duplicate name or slug before creating
		existing_by_name = self.repo.get_by_slug(obj_in.slug)
		if existing_by_name:
			raise DuplicateCityError("City with this slug already exists.")
		# You can add more checks for name if needed
		city = self.repo.create(obj_in)
		return CityOut.model_validate(city)

	def update_city(self, city_id: uuid.UUID, obj_in: CityUpdate) -> CityOut | None:
		city = self.repo.get(city_id)
		if not city:
			return None
		updated = self.repo.update(city, obj_in)
		return CityOut.model_validate(updated)

	def delete_city(self, city_id: uuid.UUID) -> bool:
		city = self.repo.get(city_id)
		if not city:
			return False
		self.repo.delete(city)
		return True
