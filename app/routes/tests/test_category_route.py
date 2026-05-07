from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.core.security import get_current_admin_user
from app.db.session import get_db
from app.routes.category_routes import router
from app.services.category_service import CategoryNotFoundError, CategoryService


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


def test_list_categories_returns_200_and_payload(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
	category_id = uuid4()
	now = datetime.now(timezone.utc)

	def _fake_list_categories(self, skip: int = 0, limit: int = 100):
		assert skip == 0
		assert limit == 100
		return [
			{
				"id": category_id,
				"name": "Electronics",
				"slug": "electronics",
				"sort_order": 1,
				"is_active": True,
				"parent_id": None,
				"created_at": now,
				"updated_at": now,
			}
		]

	monkeypatch.setattr(CategoryService, "list_categories", _fake_list_categories)

	response = client.get("/categories/")

	assert response.status_code == 200
	body = response.json()
	assert len(body) == 1
	assert body[0]["id"] == str(category_id)
	assert body[0]["slug"] == "electronics"


def test_get_category_by_slug_returns_404_when_missing(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
	def _fake_get_by_slug(self, slug: str):
		raise CategoryNotFoundError()

	monkeypatch.setattr(CategoryService, "get_category_by_slug", _fake_get_by_slug)

	response = client.get("/categories/slug/missing-slug")

	assert response.status_code == 404
	assert response.json()["detail"] == "Category not found"


def test_create_category_returns_201_for_admin(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
	category_id = uuid4()
	now = datetime.now(timezone.utc)

	def _fake_create_category(self, obj_in):
		return {
			"id": category_id,
			"name": obj_in.name,
			"slug": obj_in.slug,
			"sort_order": obj_in.sort_order,
			"is_active": obj_in.is_active,
			"parent_id": obj_in.parent_id,
			"created_at": now,
			"updated_at": now,
		}

	monkeypatch.setattr(CategoryService, "create_category", _fake_create_category)

	payload = {
		"name": "Home Cleaning",
		"slug": "home-cleaning",
		"sort_order": 0,
		"is_active": True,
		"parent_id": None,
	}
	response = client.post("/categories/", json=payload)

	assert response.status_code == 201
	body = response.json()
	assert body["id"] == str(category_id)
	assert body["name"] == "Home Cleaning"
	assert body["slug"] == "home-cleaning"


def test_create_category_requires_admin() -> None:
	def _deny_admin():
		raise HTTPException(status_code=403, detail="The user does not have enough privileges")

	app = _build_test_app(admin_override=_deny_admin)
	client = TestClient(app)

	payload = {
		"name": "Home Cleaning",
		"slug": "home-cleaning",
		"sort_order": 0,
		"is_active": True,
		"parent_id": None,
	}
	response = client.post("/categories/", json=payload)

	assert response.status_code == 403
	assert response.json()["detail"] == "The user does not have enough privileges"
