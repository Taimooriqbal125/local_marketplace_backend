from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.db.session import get_db
from app.routes.review_route import router
from app.services.review_service import (
	OrderNotFoundError,
	ReviewForbiddenError,
	ReviewNotFoundError,
	ReviewService,
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


def test_create_review_returns_201_and_payload(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
	order_id = uuid4()
	review_id = uuid4()
	current_user_id = uuid4()

	async def _fake_create_review(self, obj_in, current_user_id):
		assert obj_in.order_id == order_id
		assert obj_in.rating == 5
		assert obj_in.comment == "Great work"
		assert current_user_id == current_user_id
		return {
			"id": review_id,
			"created_at": datetime(2026, 4, 28, tzinfo=timezone.utc),
			"rating": 5,
			"seller_name": "Seller Name",
		}

	monkeypatch.setattr(ReviewService, "create_review", _fake_create_review)
	app = _build_test_app(SimpleNamespace(id=current_user_id, is_admin=False))
	test_client = TestClient(app)

	response = test_client.post(
		"/reviews/",
		json={"order_id": str(order_id), "rating": 5, "comment": "Great work"},
	)

	assert response.status_code == 201
	body = response.json()
	assert body["id"] == str(review_id)
	assert body["rating"] == 5
	assert body["sellerName"] == "Seller Name"
	assert body["createdAt"] == "2026-04-28T00:00:00Z"


def test_create_review_validates_rating_range(client: TestClient) -> None:
	order_id = uuid4()

	response = client.post(
		"/reviews/",
		json={"order_id": str(order_id), "rating": 6, "comment": "Too high"},
	)

	assert response.status_code == 422


def test_create_review_returns_404_when_order_missing(
	client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
	order_id = uuid4()
	current_user_id = uuid4()

	async def _fake_create_review(self, obj_in, current_user_id):
		raise OrderNotFoundError()

	monkeypatch.setattr(ReviewService, "create_review", _fake_create_review)
	app = _build_test_app(SimpleNamespace(id=current_user_id, is_admin=False))
	test_client = TestClient(app)

	response = test_client.post("/reviews/", json={"order_id": str(order_id), "rating": 5})

	assert response.status_code == 404
	assert response.json()["detail"] == "Order not found"


def test_get_all_reviews_returns_200_for_admin_and_passes_filters(
	client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
	review_id = uuid4()
	admin_user = SimpleNamespace(id=uuid4(), is_admin=True)
	app = _build_test_app(admin_user)
	test_client = TestClient(app)

	def _fake_list_all_reviews(self, current_user, days=None, skip=0, limit=100):
		assert current_user.is_admin is True
		assert days == 7
		assert skip == 10
		assert limit == 25
		return [
			{
				"id": review_id,
				"rating": 4,
				"comment": "Helpful",
				"created_at": datetime(2026, 4, 28, tzinfo=timezone.utc),
				"reviewer_name": "Buyer",
				"seller_name": "Seller",
				"service_name": "Service",
				"service_images": ["https://cdn.example.com/image.jpg"],
			}
		]

	monkeypatch.setattr(ReviewService, "list_all_reviews", _fake_list_all_reviews)

	response = test_client.get("/reviews/?days=7&skip=10&limit=25")

	assert response.status_code == 200
	body = response.json()
	assert len(body) == 1
	assert body[0]["id"] == str(review_id)
	assert body[0]["sellerName"] == "Seller"
	assert body[0]["serviceImages"] == ["https://cdn.example.com/image.jpg"]


def test_get_all_reviews_returns_403_for_non_admin(
	client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
	def _fake_list_all_reviews(self, current_user, days=None, skip=0, limit=100):
		raise ReviewForbiddenError("Only administrators can access the full review listing.")

	monkeypatch.setattr(ReviewService, "list_all_reviews", _fake_list_all_reviews)

	response = client.get("/reviews/")

	assert response.status_code == 403
	assert response.json()["detail"] == "Only administrators can access the full review listing."


def test_get_my_received_reviews_returns_200_and_uses_query_params(
	client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
	review_id = uuid4()
	current_user_id = uuid4()
	app = _build_test_app(SimpleNamespace(id=current_user_id, is_admin=False))
	test_client = TestClient(app)

	def _fake_list_received_reviews(self, user_id, rating=None, skip=0, limit=20):
		assert user_id == current_user_id
		assert rating == 5
		assert skip == 2
		assert limit == 10
		return [
			{
				"id": review_id,
				"rating": 5,
				"comment": "Excellent",
				"created_at": datetime(2026, 4, 28, tzinfo=timezone.utc),
				"reviewer_name": "Buyer",
				"reviewer_photo_url": "https://cdn.example.com/buyer.jpg",
				"service_title": "Service Title",
				"category_name": "Category",
				"service_image_url": "https://cdn.example.com/service.jpg",
			}
		]

	monkeypatch.setattr(ReviewService, "list_received_reviews", _fake_list_received_reviews)

	response = test_client.get("/reviews/me/received?rating=5&skip=2&limit=10")

	assert response.status_code == 200
	body = response.json()
	assert len(body) == 1
	assert body[0]["id"] == str(review_id)
	assert body[0]["reviewerPhotoUrl"] == "https://cdn.example.com/buyer.jpg"
	assert body[0]["serviceTitle"] == "Service Title"


def test_get_my_given_reviews_returns_200_and_uses_query_params(
	client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
	review_id = uuid4()
	current_user_id = uuid4()
	app = _build_test_app(SimpleNamespace(id=current_user_id, is_admin=False))
	test_client = TestClient(app)

	def _fake_list_given_reviews(self, user_id, skip=0, limit=20):
		assert user_id == current_user_id
		assert skip == 3
		assert limit == 15
		return [
			{
				"id": review_id,
				"order_id": uuid4(),
				"rating": 4,
				"comment": "Solid",
				"created_at": datetime(2026, 4, 28, tzinfo=timezone.utc),
				"service_name": "Service Name",
				"category_name": "Category",
				"image_url": "https://cdn.example.com/service.jpg",
			}
		]

	monkeypatch.setattr(ReviewService, "list_given_reviews", _fake_list_given_reviews)

	response = test_client.get("/reviews/me/given?skip=3&limit=15")

	assert response.status_code == 200
	body = response.json()
	assert len(body) == 1
	assert body[0]["id"] == str(review_id)
	assert body[0]["serviceName"] == "Service Name"
	assert body[0]["imageUrl"] == "https://cdn.example.com/service.jpg"


def test_get_reviews_by_user_id_returns_200_and_payload(
	client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
	review_id = uuid4()
	user_id = uuid4()

	def _fake_list_received_reviews(self, user_id, rating=None, skip=0, limit=20):
		assert skip == 1
		assert limit == 5
		assert rating == 4
		return [
			{
				"id": review_id,
				"rating": 4,
				"note": "Good",
				"created_at": datetime(2026, 4, 28, tzinfo=timezone.utc),
				"reviewer": {
					"id": uuid4(),
					"name": "Reviewer",
					"photo_url": "https://cdn.example.com/reviewer.jpg",
				},
			}
		]

	monkeypatch.setattr(ReviewService, "list_received_reviews", _fake_list_received_reviews)

	response = client.get(f"/reviews/byuserid/{user_id}?rating=4&skip=1&limit=5")

	assert response.status_code == 200
	body = response.json()
	assert len(body) == 1
	assert body[0]["id"] == str(review_id)
	assert body[0]["note"] == "Good"
	assert body[0]["reviewer"]["photoUrl"] == "https://cdn.example.com/reviewer.jpg"


def test_get_review_returns_200_for_single_review(
	client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
	review_id = uuid4()

	def _fake_get_review(self, incoming_review_id):
		assert incoming_review_id == review_id
		return {
			"id": review_id,
			"order_id": uuid4(),
			"reviewer_id": uuid4(),
			"reviewed_user_id": uuid4(),
			"rating": 5,
			"comment": "Excellent",
			"created_at": datetime(2026, 4, 28, tzinfo=timezone.utc),
		}

	monkeypatch.setattr(ReviewService, "get_review", _fake_get_review)

	response = client.get(f"/reviews/{review_id}")

	assert response.status_code == 200
	body = response.json()
	assert body["id"] == str(review_id)
	assert body["orderId"] is not None
	assert body["reviewedUserId"] is not None


def test_get_review_returns_404_when_missing(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
	review_id = uuid4()

	def _fake_get_review(self, incoming_review_id):
		raise ReviewNotFoundError()

	monkeypatch.setattr(ReviewService, "get_review", _fake_get_review)

	response = client.get(f"/reviews/{review_id}")

	assert response.status_code == 404
	assert response.json()["detail"] == "Review not found"


def test_delete_review_returns_204_for_author(
	client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
	review_id = uuid4()
	current_user_id = uuid4()
	app = _build_test_app(SimpleNamespace(id=current_user_id, is_admin=False))
	test_client = TestClient(app)

	def _fake_delete_review(self, incoming_review_id, current_user_id):
		assert incoming_review_id == review_id
		assert current_user_id == current_user_id
		return None

	monkeypatch.setattr(ReviewService, "delete_review", _fake_delete_review)

	response = test_client.delete(f"/reviews/{review_id}")

	assert response.status_code == 204
	assert response.text == ""


def test_delete_review_returns_403_for_non_author(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
	review_id = uuid4()

	def _fake_delete_review(self, incoming_review_id, current_user_id):
		raise ReviewForbiddenError("Only the author can delete this review")

	monkeypatch.setattr(ReviewService, "delete_review", _fake_delete_review)

	response = client.delete(f"/reviews/{review_id}")

	assert response.status_code == 403
	assert response.json()["detail"] == "Only the author can delete this review"


def test_delete_review_returns_404_when_missing(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
	review_id = uuid4()

	def _fake_delete_review(self, incoming_review_id, current_user_id):
		raise ReviewNotFoundError()

	monkeypatch.setattr(ReviewService, "delete_review", _fake_delete_review)

	response = client.delete(f"/reviews/{review_id}")

	assert response.status_code == 404
	assert response.json()["detail"] == "Review not found"
