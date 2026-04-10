from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.services.cities_service import CityService
from app.schemas.cities import CityCreate, CityUpdate, CityOut
from app.db.session import get_db
from app.core.security import get_current_admin_user
from app.models.user import User
from typing import List
import uuid

router = APIRouter(prefix="/cities", tags=["cities"])

@router.get("/", response_model=List[CityOut])
def list_cities(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
	return CityService(db).list_cities(skip=skip, limit=limit)

@router.get("/{city_id}", response_model=CityOut)
def get_city(city_id: uuid.UUID, db: Session = Depends(get_db)):
	return CityService(db).get_city(city_id)

@router.get("/slug/{slug}", response_model=CityOut)
def get_city_by_slug(slug: str, db: Session = Depends(get_db)):
	return CityService(db).get_city_by_slug(slug)

@router.post("/", response_model=CityOut, status_code=status.HTTP_201_CREATED)
def create_city(
	obj_in: CityCreate,
	db: Session = Depends(get_db),
	_: User = Depends(get_current_admin_user),
):
	return CityService(db).create_city(obj_in)

@router.patch("/{city_id}", response_model=CityOut)
def update_city(
	city_id: uuid.UUID,
	obj_in: CityUpdate,
	db: Session = Depends(get_db),
	_: User = Depends(get_current_admin_user),
):
	return CityService(db).update_city(city_id, obj_in)

@router.delete("/{city_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_city(
	city_id: uuid.UUID,
	db: Session = Depends(get_db),
	_: User = Depends(get_current_admin_user),
):
	return CityService(db).delete_city(city_id)
