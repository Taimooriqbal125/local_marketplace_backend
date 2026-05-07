from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.db.session import get_db
from app.routes.listing_media_routes import router
from app.services.listing_media_service import (
	ListingForbiddenError,
	ListingMediaService,
	ListingNotFoundError,
	MediaNotFoundError,
)


def _build_test_app(current_user=None) -> FastAPI:
	app = FastAPI()
	app.include_router(router)

	def _override_get_db():
		yield object()

	app.dependency_overrides[get_db] = _override_get_db
	if current_user is None:
		current_user = SimpleNamespace(id=uuid4(), is_admin=False)
	app.dependency_overrides[get_current_user] = lambda: current_user
	return app


@pytest.fixture
def client() -> TestClient:
	return TestClient(_build_test_app())


def test_get_listing_media_returns_200_and_payload(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
	media_id = uuid4()
	listing_id = uuid4()

	def _fake_get_listing_media(self, incoming_listing_id):
		assert incoming_listing_id == listing_id
		return [
			{
				"id": media_id,
				"listing_id": listing_id,
				"image_url": "https://cdn.example.com/image.jpg",
				"cloudinary_public_id": "marketplace/listings/1/image",
				"sort_order": 0,
				"created_at": "2026-04-27T00:00:00Z",
			}
		]

	monkeypatch.setattr(ListingMediaService, "get_listing_media", _fake_get_listing_media)

	response = client.get(f"/listingmedia/listing/{listing_id}")

	assert response.status_code == 200
	body = response.json()
	assert len(body) == 1
	assert body[0]["id"] == str(media_id)
	assert body[0]["listingId"] == str(listing_id)
	assert body[0]["sortOrder"] == 0


def test_get_media_returns_404_when_missing(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
	missing_media_id = uuid4()

	def _fake_get_media(self, media_id):
		raise MediaNotFoundError(media_id)

	monkeypatch.setattr(ListingMediaService, "get_media", _fake_get_media)

	response = client.get(f"/listingmedia/{missing_media_id}")

	assert response.status_code == 404
	assert response.json()["detail"] == f"Media record '{missing_media_id}' not found."


def test_add_media_returns_201_for_owner(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
	media_id = uuid4()
	listing_id = uuid4()

	def _fake_add_media(self, obj_in, current_seller_id):
		assert current_seller_id is not None
		assert obj_in.listing_id == listing_id
		from datetime import datetime, timezone

		return {
			"id": media_id,
			"listing_id": obj_in.listing_id,
			"image_url": obj_in.image_url,
			"cloudinary_public_id": obj_in.cloudinary_public_id,
			"sort_order": obj_in.sort_order,
			"created_at": datetime.now(timezone.utc),
		}

	monkeypatch.setattr(ListingMediaService, "add_media", _fake_add_media)

	payload = {
		"listing_id": str(listing_id),
		"image_url": "https://cdn.example.com/image.jpg",
		"cloudinary_public_id": "marketplace/listings/image",
		"sort_order": 1,
	}
	response = client.post("/listingmedia/", json=payload)

	assert response.status_code == 201
	body = response.json()
	assert body["id"] == str(media_id)
	assert body["listingId"] == str(listing_id)
	assert body["sortOrder"] == 1


def test_update_media_returns_404_when_missing(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
	missing_media_id = uuid4()

	def _fake_update_media(self, media_id, obj_in, current_seller_id):
		raise MediaNotFoundError(media_id)

	monkeypatch.setattr(ListingMediaService, "update_media", _fake_update_media)

	payload = {
		"image_url": "https://cdn.example.com/new-image.jpg",
		"sort_order": 2,
	}
	response = client.patch(f"/listingmedia/{missing_media_id}", json=payload)

	assert response.status_code == 404
	assert response.json()["detail"] == f"Media record '{missing_media_id}' not found."


def test_delete_media_returns_success_for_owner(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
	media_id = uuid4()

	async def _fake_delete_media(self, media_id, current_seller_id, is_admin=False):
		assert media_id == media_id
		assert is_admin is False

	monkeypatch.setattr(ListingMediaService, "delete_media", _fake_delete_media)

	response = client.delete(f"/listingmedia/{media_id}")

	assert response.status_code == 200
	assert response.json()["success"] is True


def test_upload_media_returns_404_when_listing_missing(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
	listing_id = uuid4()

	async def _fake_upload_and_add_media(self, listing_id, file, sort_order, current_seller_id, folder=None):
		raise ListingNotFoundError(listing_id)

	monkeypatch.setattr(ListingMediaService, "upload_and_add_media", _fake_upload_and_add_media)

	response = client.post(
		f"/listingmedia/{listing_id}/upload?sort_order=0",
		files={"file": ("image.jpg", b"fake image bytes", "image/jpeg")},
	)

	assert response.status_code == 404
	assert response.json()["detail"] == f"Service listing '{listing_id}' not found."


def test_add_media_uses_forbidden_error_when_service_blocks(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
	listing_id = uuid4()

	def _fake_add_media(self, obj_in, current_seller_id):
		raise ListingForbiddenError()

	monkeypatch.setattr(ListingMediaService, "add_media", _fake_add_media)

	payload = {
		"listing_id": str(listing_id),
		"image_url": "https://cdn.example.com/image.jpg",
		"sort_order": 0,
	}
	response = client.post("/listingmedia/", json=payload)

	assert response.status_code == 403
	assert response.json()["detail"] == "You do not have permission to modify this listing's media."
