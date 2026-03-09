import uuid
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status
from app.repositories.cities_repo import CityRepository
from app.schemas.cities import CityCreate, CityUpdate, CityOut
from app.models.cities import City
from typing import Sequence


class DuplicateCityError(Exception):
	pass


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
		# 1. Pre-check: slug must be unique
		if self.repo.get_by_slug(obj_in.slug):
			raise HTTPException(
				status_code=status.HTTP_409_CONFLICT,
				detail=f"A city with slug '{obj_in.slug}' already exists.",
			)
		
		# 2. Pre-check: name + country combination should be unique (logical check)
		if self.repo.get_by_name_and_country(obj_in.name, obj_in.country):
			raise HTTPException(
				status_code=status.HTTP_409_CONFLICT,
				detail=f"City '{obj_in.name}' already exists in '{obj_in.country}'.",
			)

		try:
			city = self.repo.create(obj_in)
		except IntegrityError as e:
			# Differentiate between NotNull (missing slug) and Unique (duplicate)
			err_msg = str(e.orig).lower()
			if "slug" in err_msg:
				detail = f"A city with slug '{obj_in.slug}' already exists."
			elif "name" in err_msg:
				detail = f"City '{obj_in.name}' already exists."
			else:
				detail = "Database integrity error: A city with this slug or name already exists."
				
			raise HTTPException(
				status_code=status.HTTP_409_CONFLICT,
				detail=detail,
			)
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
