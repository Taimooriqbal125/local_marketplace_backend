"""Test service listing routes - validates routing, auth, and parameter passing."""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.core.rate_limiter import (
	services_create_rate_limit,
	services_nearby_me_rate_limit,
)
from app.db.session import get_db
from app.routes.service_listing_routes import router
from app.services.service_listing_service import (
	ListingNotFoundError,
	ListingForbiddenError,
	ProfileLocationMissingError,
	ServiceListingService,
)


def _build_test_app(current_user=None) -> FastAPI:
	app = FastAPI()
	app.include_router(router)

	def _override_get_db():
		yield object()

	app.dependency_overrides[get_db] = _override_get_db
	app.dependency_overrides[services_create_rate_limit] = lambda: None
	app.dependency_overrides[services_nearby_me_rate_limit] = lambda: None

	if current_user is None:
		current_user = SimpleNamespace(id=uuid4(), is_admin=False)
	app.dependency_overrides[get_current_user] = lambda: current_user

	return app


@pytest.fixture
def client() -> TestClient:
	return TestClient(_build_test_app())


def test_list_my_listings_passes_seller_id(
	client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
	"""Test that /services/me passes seller_id parameter to service."""
	seller_id = uuid4()
	app = _build_test_app(SimpleNamespace(id=seller_id, is_admin=False))
	test_client = TestClient(app)

	captured_seller_id = None

	def _fake_list_my_listings(self, seller_id, **kwargs):
		nonlocal captured_seller_id
		captured_seller_id = seller_id
		return {"total": 0, "page": 1, "page_size": 20, "results": []}

	monkeypatch.setattr(ServiceListingService, "list_my_listings", _fake_list_my_listings)

	response = test_client.get("/services/me")

	assert response.status_code == 200
	assert captured_seller_id == seller_id


def test_get_listing_returns_404_not_found(
	client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
	"""Test that GET /services/{id} returns 404 when not found."""
	listing_id = uuid4()

	def _fake_get_listing(self, incoming_listing_id):
		raise ListingNotFoundError(incoming_listing_id)

	monkeypatch.setattr(ServiceListingService, "get_listing", _fake_get_listing)

	response = client.get(f"/services/{listing_id}")

	assert response.status_code == 404


def test_create_listing_empty_payload(client: TestClient) -> None:
	"""Test that POST /services/ with empty JSON returns 422."""
	response = client.post("/services/", json={})

	assert response.status_code == 422


def test_delete_listing_forbidden_non_owner(
	client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
	"""Test that DELETE returns 403 when user is not the owner."""
	listing_id = uuid4()

	def _fake_delete_listing(self, listing_id, current_user_id, is_admin=False):
		raise ListingForbiddenError()

	monkeypatch.setattr(ServiceListingService, "delete_listing", _fake_delete_listing)

	response = client.delete(f"/services/{listing_id}")

	assert response.status_code == 403


def test_delete_listing_succeeds_for_owner(
	client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
	"""Test that DELETE returns 200 when user is the owner."""
	seller_id = uuid4()
	listing_id = uuid4()
	app = _build_test_app(SimpleNamespace(id=seller_id, is_admin=False))
	test_client = TestClient(app)

	captured_listing_id = None
	captured_user_id = None

	def _fake_delete_listing(self, listing_id, current_user_id, is_admin=False):
		nonlocal captured_listing_id, captured_user_id
		captured_listing_id = listing_id
		captured_user_id = current_user_id
		return None

	monkeypatch.setattr(ServiceListingService, "delete_listing", _fake_delete_listing)

	response = test_client.delete(f"/services/{listing_id}")

	assert response.status_code == 200
	assert captured_listing_id == listing_id
	assert captured_user_id == seller_id


def test_get_nearby_validates_longitude_required(client: TestClient) -> None:
	"""Test that GET /services/nearby requires longitude parameter."""
	response = client.get("/services/nearby?latitude=24.8&radius_km=10")

	assert response.status_code == 422


def test_get_nearby_me_returns_400_user_no_location(
	client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
	"""Test that GET /services/nearby/me returns 400 when user has no saved location."""
	seller_id = uuid4()
	app = _build_test_app(SimpleNamespace(id=seller_id, is_admin=False))
	test_client = TestClient(app)

	def _fake_search_nearby_from_profile(self, user_id, db, **kwargs):
		raise ProfileLocationMissingError()

	monkeypatch.setattr(ServiceListingService, "search_nearby_from_profile", _fake_search_nearby_from_profile)

	response = test_client.get("/services/nearby/me")

	assert response.status_code == 400
