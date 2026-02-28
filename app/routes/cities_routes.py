from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.services.cities_services import CityService, DuplicateCityError
from app.schemas.cities import CityCreate, CityUpdate, CityOut
from app.db.session import get_db
from typing import List
import uuid

router = APIRouter(prefix="/cities", tags=["cities"])

@router.get("/", response_model=List[CityOut])
def list_cities(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
	service = CityService(db)
	return service.list_cities(skip=skip, limit=limit)

@router.get("/{city_id}", response_model=CityOut)
def get_city(city_id: uuid.UUID, db: Session = Depends(get_db)):
	service = CityService(db)
	city = service.get_city(city_id)
	if not city:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="City not found")
	return city

@router.get("/slug/{slug}", response_model=CityOut)
def get_city_by_slug(slug: str, db: Session = Depends(get_db)):
	service = CityService(db)
	city = service.get_city_by_slug(slug)
	if not city:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="City not found")
	return city

@router.post("/", response_model=CityOut, status_code=status.HTTP_201_CREATED)
def create_city(obj_in: CityCreate, db: Session = Depends(get_db)):
	service = CityService(db)
	try:
		return service.create_city(obj_in)
	except DuplicateCityError as e:
		raise HTTPException(
			status_code=status.HTTP_409_CONFLICT,
			detail=str(e)
		)

@router.patch("/{city_id}", response_model=CityOut)
def update_city(city_id: uuid.UUID, obj_in: CityUpdate, db: Session = Depends(get_db)):
	service = CityService(db)
	city = service.update_city(city_id, obj_in)
	if not city:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="City not found")
	return city

@router.delete("/{city_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_city(city_id: uuid.UUID, db: Session = Depends(get_db)):
	service = CityService(db)
	success = service.delete_city(city_id)
	if not success:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="City not found")
	return None
