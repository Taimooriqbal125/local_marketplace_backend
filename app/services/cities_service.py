import uuid
from typing import Sequence
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status

from app.repositories.cities_repo import CityRepository
from app.schemas.cities import CityCreate, CityUpdate, CityOut


class CityNotFoundError(HTTPException):
    def __init__(self, detail: str = "City not found"):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


class CityConflictError(HTTPException):
    def __init__(self, detail: str = "A city with this slug or name already exists."):
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=detail)


class CityService:
    """Service layer for City operations, encapsulating business logic."""

    def __init__(self, db: Session) -> None:
        self.repo = CityRepository(db)

    def get_city(self, city_id: uuid.UUID) -> CityOut:
        city = self.repo.get(city_id)
        if not city:
            raise CityNotFoundError()
        return CityOut.model_validate(city)

    def get_city_by_slug(self, slug: str) -> CityOut:
        city = self.repo.get_by_slug(slug)
        if not city:
            raise CityNotFoundError()
        return CityOut.model_validate(city)

    def list_cities(self, skip: int = 0, limit: int = 100) -> Sequence[CityOut]:
        cities = self.repo.get_all(skip=skip, limit=limit)
        return [CityOut.model_validate(city) for city in cities]

    def create_city(self, obj_in: CityCreate) -> CityOut:
        # Pre-check: slug must be unique
        if self.repo.get_by_slug(obj_in.slug):
            raise CityConflictError(f"A city with slug '{obj_in.slug}' already exists.")
        
        # Pre-check: name + country combination should be unique
        if self.repo.get_by_name_and_country(obj_in.name, obj_in.country):
            raise CityConflictError(f"City '{obj_in.name}' already exists in '{obj_in.country}'.")

        try:
            city = self.repo.create(obj_in)
            return CityOut.model_validate(city)
        except IntegrityError:
            raise CityConflictError()

    def update_city(self, city_id: uuid.UUID, obj_in: CityUpdate) -> CityOut:
        city = self.repo.get(city_id)
        if not city:
            raise CityNotFoundError()
            
        try:
            updated = self.repo.update(city, obj_in)
            return CityOut.model_validate(updated)
        except IntegrityError:
            raise CityConflictError("Update failed: A city with this slug already exists.")

    def delete_city(self, city_id: uuid.UUID) -> None:
        city = self.repo.get(city_id)
        if not city:
            raise CityNotFoundError()
            
        self.repo.delete(city)
