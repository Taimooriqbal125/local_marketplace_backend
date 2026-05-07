from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.db.session import get_db
from app.routes.order_routes import router
from app.services.order_service import (
    OrderForbiddenError,
    OrderNotFoundError,
    OrderStateError,
    ListingNotFoundError,
    OrderService,
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


def test_create_order_returns_201_for_authenticated_buyer(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    order_id = uuid4()
    listing_id = uuid4()
    buyer_id = uuid4()
    seller_id = uuid4()

    async def _fake_create_order(self, obj_in, buyer_id):
        assert obj_in.listing_id == listing_id
        return {
            "id": order_id,
            "listing_id": listing_id,
            "buyer_id": buyer_id,
            "seller_id": seller_id,
            "status": "requested",
            "proposed_price": 5000,
            "agreed_price": None,
            "notes": "Please complete this quickly",
            "accepted_at": None,
            "seller_completed_at": None,
            "buyer_completed_at": None,
            "created_at": "2026-04-28T00:00:00Z",
            "updated_at": "2026-04-28T00:00:00Z",
            "service_name": "Website Design",
            "image_url": "https://cdn.example.com/image.jpg",
            "seller_name": "John Seller",
        }

    monkeypatch.setattr(OrderService, "create_order", _fake_create_order)

    payload = {
        "listing_id": str(listing_id),
        "proposed_price": 5000,
        "notes": "Please complete this quickly",
    }
    response = client.post("/orders/", json=payload)

    assert response.status_code == 201
    body = response.json()
    assert body["id"] == str(order_id)
    assert body["status"] == "requested"
    assert body["proposedPrice"] == 5000


def test_create_order_returns_404_when_listing_missing(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    listing_id = uuid4()

    async def _fake_create_order(self, obj_in, buyer_id):
        raise ListingNotFoundError()

    monkeypatch.setattr(OrderService, "create_order", _fake_create_order)

    payload = {
        "listing_id": str(listing_id),
        "proposed_price": 5000,
    }
    response = client.post("/orders/", json=payload)

    assert response.status_code == 404
    assert response.json()["detail"] == "Service listing not found"


def test_list_seller_orders_returns_200_with_orders(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    order_id = uuid4()

    async def _fake_list_seller_orders(self, user_id, status=None, skip=0, limit=20):
        return {
            "total_orders": 5,
            "orders": [
                {
                    "id": order_id,
                    "status": "completed",
                    "created_at": "2026-04-28T00:00:00Z",
                    "proposed_price": 5000,
                    "seller_completed_at": "2026-04-28T12:00:00Z",
                    "buyer_completed_at": "2026-04-28T11:00:00Z",
                    "buyer_name": "Jane Buyer",
                    "buyer_phone": "+1234567890",
                    "service_name": "Logo Design",
                    "image_url": "https://cdn.example.com/logo.jpg",
                    "service_price": 5000.0,
                }
            ],
        }

    monkeypatch.setattr(OrderService, "list_seller_orders", _fake_list_seller_orders)

    response = client.get("/orders/me/as-seller")

    assert response.status_code == 200
    body = response.json()
    assert body["totalOrders"] == 5
    assert len(body["orders"]) == 1
    assert body["orders"][0]["id"] == str(order_id)
    assert body["orders"][0]["status"] == "completed"


def test_list_seller_orders_with_status_filter(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _fake_list_seller_orders(self, user_id, status=None, skip=0, limit=20):
        assert status == "accepted"
        return {
            "total_orders": 2,
            "orders": [],
        }

    monkeypatch.setattr(OrderService, "list_seller_orders", _fake_list_seller_orders)

    response = client.get("/orders/me/as-seller?status=accepted")

    assert response.status_code == 200
    body = response.json()
    assert body["totalOrders"] == 2


def test_list_buyer_orders_returns_200_with_orders(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    order_id = uuid4()

    async def _fake_list_buyer_orders(self, user_id, status=None, skip=0, limit=20):
        return [
            {
                "id": order_id,
                "status": "accepted",
                "created_at": "2026-04-28T00:00:00Z",
                "agreed_price": 4500,
                "seller_completed_at": None,
                "buyer_completed_at": None,
                "service_name": "Content Writing",
                "image_url": "https://cdn.example.com/content.jpg",
                "service_price": 5000.0,
                "seller_name": "Bob Writer",
                "seller_phone": "+9876543210",
            }
        ]

    monkeypatch.setattr(OrderService, "list_buyer_orders", _fake_list_buyer_orders)

    response = client.get("/orders/me/as-buyer")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["id"] == str(order_id)
    assert body[0]["status"] == "accepted"
    assert body[0]["agreedPrice"] == 4500


def test_get_order_returns_200_for_involved_party(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    order_id = uuid4()

    async def _fake_get_order(self, order_id, current_user_id):
        return {
            "id": order_id,
            "status": "completed",
            "proposed_price": 5000,
            "agreed_price": 4800,
            "notes": "Great work!",
            "created_at": "2026-04-28T00:00:00Z",
            "accepted_at": "2026-04-28T02:00:00Z",
            "seller_completed_at": "2026-04-28T12:00:00Z",
            "buyer_completed_at": "2026-04-28T11:00:00Z",
            "updated_at": "2026-04-28T12:00:00Z",
            "service_name": "Mobile App Dev",
            "image_url": "https://cdn.example.com/app.jpg",
            "category_name": "Development",
            "price_type": "fixed",
            "listing_price": 5000.0,
            "seller_name": "Alice Developer",
            "seller_photo_url": "https://cdn.example.com/alice.jpg",
            "seller_phone": "+1111111111",
            "buyer_name": "Charlie Buyer",
            "buyer_photo_url": "https://cdn.example.com/charlie.jpg",
            "buyer_phone": "+2222222222",
        }

    monkeypatch.setattr(OrderService, "get_order", _fake_get_order)

    response = client.get(f"/orders/{order_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(order_id)
    assert body["status"] == "completed"
    assert body["sellerName"] == "Alice Developer"


def test_get_order_returns_404_when_missing(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    order_id = uuid4()

    async def _fake_get_order(self, order_id, current_user_id):
        raise OrderNotFoundError()

    monkeypatch.setattr(OrderService, "get_order", _fake_get_order)

    response = client.get(f"/orders/{order_id}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Order not found"


def test_get_order_returns_403_when_not_involved(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    order_id = uuid4()

    async def _fake_get_order(self, order_id, current_user_id):
        raise OrderForbiddenError()

    monkeypatch.setattr(OrderService, "get_order", _fake_get_order)

    response = client.get(f"/orders/{order_id}")

    assert response.status_code == 403
    assert response.json()["detail"] == "You are not authorized to view or modify this order"


def test_accept_order_returns_200_for_seller(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    order_id = uuid4()

    async def _fake_update_order_status(self, order_id, obj_in, current_user_id):
        assert obj_in.status == "accepted"
        return {
            "id": order_id,
            "status": "accepted",
            "proposed_price": 5000,
            "agreed_price": 4500,
            "notes": None,
            "created_at": "2026-04-28T00:00:00Z",
            "accepted_at": "2026-04-28T02:00:00Z",
            "seller_completed_at": None,
            "buyer_completed_at": None,
            "updated_at": "2026-04-28T02:00:00Z",
            "service_name": "SEO Optimization",
            "image_url": None,
            "category_name": "Marketing",
            "price_type": "hourly",
            "listing_price": 100.0,
            "seller_name": "David SEO",
            "seller_photo_url": None,
            "seller_phone": None,
            "buyer_name": "Eve Client",
            "buyer_photo_url": None,
            "buyer_phone": None,
        }

    monkeypatch.setattr(OrderService, "update_order_status", _fake_update_order_status)

    payload = {
        "status": "accepted",
        "agreed_price": 4500,
    }
    response = client.patch(f"/orders/{order_id}", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(order_id)
    assert body["status"] == "accepted"
    assert body["agreedPrice"] == 4500


def test_complete_order_returns_200_for_completion(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    order_id = uuid4()

    async def _fake_update_order_status(self, order_id, obj_in, current_user_id):
        assert obj_in.status == "completed"
        return {
            "id": order_id,
            "status": "completed",
            "proposed_price": 3000,
            "agreed_price": 3000,
            "notes": None,
            "created_at": "2026-04-28T00:00:00Z",
            "accepted_at": "2026-04-28T01:00:00Z",
            "seller_completed_at": "2026-04-28T10:00:00Z",
            "buyer_completed_at": "2026-04-28T09:00:00Z",
            "updated_at": "2026-04-28T10:00:00Z",
            "service_name": "Copywriting",
            "image_url": None,
            "category_name": "Writing",
            "price_type": "fixed",
            "listing_price": 3000.0,
            "seller_name": "Frank Writer",
            "seller_photo_url": None,
            "seller_phone": None,
            "buyer_name": "Grace Publisher",
            "buyer_photo_url": None,
            "buyer_phone": None,
        }

    monkeypatch.setattr(OrderService, "update_order_status", _fake_update_order_status)

    payload = {
        "status": "completed",
    }
    response = client.patch(f"/orders/{order_id}", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["sellerCompletedAt"] is not None


def test_cancel_order_request_returns_200_for_buyer(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    order_id = uuid4()

    async def _fake_cancel_order_request(self, order_id, current_user_id):
        return {
            "message": "Order request cancelled successfully",
            "order_id": order_id,
        }

    monkeypatch.setattr(OrderService, "cancel_order_request", _fake_cancel_order_request)

    response = client.delete(f"/orders/{order_id}/cancel-request")

    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "Order request cancelled successfully"
    assert body["orderId"] == str(order_id)


def test_cancel_order_request_returns_404_when_missing(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    order_id = uuid4()

    async def _fake_cancel_order_request(self, order_id, current_user_id):
        raise OrderNotFoundError()

    monkeypatch.setattr(OrderService, "cancel_order_request", _fake_cancel_order_request)

    response = client.delete(f"/orders/{order_id}/cancel-request")

    assert response.status_code == 404
    assert response.json()["detail"] == "Order not found"


def test_cancel_order_request_returns_403_for_non_buyer(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    order_id = uuid4()

    async def _fake_cancel_order_request(self, order_id, current_user_id):
        raise OrderForbiddenError("Only the buyer who requested this service can cancel it")

    monkeypatch.setattr(OrderService, "cancel_order_request", _fake_cancel_order_request)

    response = client.delete(f"/orders/{order_id}/cancel-request")

    assert response.status_code == 403
    assert "Only the buyer" in response.json()["detail"]


def test_cancel_order_request_returns_400_for_non_requested_status(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    order_id = uuid4()

    async def _fake_cancel_order_request(self, order_id, current_user_id):
        raise OrderStateError("Only orders in 'requested' status can be cancelled")

    monkeypatch.setattr(OrderService, "cancel_order_request", _fake_cancel_order_request)

    response = client.delete(f"/orders/{order_id}/cancel-request")

    assert response.status_code == 400
    assert "requested" in response.json()["detail"]
