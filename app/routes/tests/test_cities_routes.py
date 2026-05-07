from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.core.security import get_current_admin_user
from app.db.session import get_db
from app.routes.cities_routes import router
from app.services.cities_service import CityNotFoundError, CityService


def _build_test_app(admin_override=None) -> FastAPI:
	app = FastAPI()
	app.include_router(router)

	def _override_get_db():
		yield object()

	app.dependency_overrides[get_db] = _override_get_db
	app.dependency_overrides[get_current_admin_user] = admin_override or (lambda: object())
	return app


@pytest.fixture
def client() -> TestClient:
	return TestClient(_build_test_app())


def test_list_cities_returns_200_and_payload(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
	city_id = uuid4()

	def _fake_list_cities(self, skip: int = 0, limit: int = 100):
		assert skip == 0
		assert limit == 100
		return [
			{
				"id": city_id,
				"name": "Karachi",
				"country": "Pakistan",
				"slug": "karachi",
				"is_active": True,
				"center_point": "24.8607,67.0011",
			}
		]

	monkeypatch.setattr(CityService, "list_cities", _fake_list_cities)

	response = client.get("/cities/")

	assert response.status_code == 200
	body = response.json()
	assert len(body) == 1
	assert body[0]["id"] == str(city_id)
	assert body[0]["slug"] == "karachi"


def test_get_city_by_slug_returns_404_when_missing(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
	def _fake_get_city_by_slug(self, slug: str):
		raise CityNotFoundError()

	monkeypatch.setattr(CityService, "get_city_by_slug", _fake_get_city_by_slug)

	response = client.get("/cities/slug/missing-city")

	assert response.status_code == 404
	assert response.json()["detail"] == "City not found"


def test_create_city_returns_201_for_admin(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
	city_id = uuid4()

	def _fake_create_city(self, obj_in):
		return {
			"id": city_id,
			"name": obj_in.name,
			"country": obj_in.country,
			"slug": obj_in.slug,
			"is_active": obj_in.is_active,
			"center_point": obj_in.center_point,
		}

	monkeypatch.setattr(CityService, "create_city", _fake_create_city)

	payload = {
		"name": "Lahore",
		"country": "Pakistan",
		"slug": "lahore",
		"is_active": True,
		"center_point": "31.5204,74.3587",
	}
	response = client.post("/cities/", json=payload)

	assert response.status_code == 201
	body = response.json()
	assert body["id"] == str(city_id)
	assert body["name"] == "Lahore"


def test_delete_city_requires_admin() -> None:
	def _deny_admin():
		raise HTTPException(status_code=403, detail="The user does not have enough privileges")

	app = _build_test_app(admin_override=_deny_admin)
	client = TestClient(app)

	response = client.delete(f"/cities/{uuid4()}")

	assert response.status_code == 403
	assert response.json()["detail"] == "The user does not have enough privileges"
