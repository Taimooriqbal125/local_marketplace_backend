from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.db.session import get_db
from app.routes.notification_routes import router
from app.services.notification_service import (
    NotificationForbiddenError,
    NotificationNotFoundError,
    NotificationService,
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


def test_list_notifications_returns_200_and_payload(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    notif_id = uuid4()
    user_id = uuid4()

    def _fake_list_notifications(self, user_id, only_unread=False, skip=0, limit=20):
        assert user_id == user_id
        assert only_unread is False
        assert skip == 0
        assert limit == 20
        return [
            {
                "id": notif_id,
                "type": "order_requested",
                "title": "New Order",
                "body": "You have a new order request.",
                "is_read": False,
                "created_at": "2026-04-28T00:00:00Z",
                "order_id": None,
                "listing_id": None,
            }
        ]

    monkeypatch.setattr(NotificationService, "list_notifications", _fake_list_notifications)

    response = client.get("/notifications/")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["id"] == str(notif_id)
    assert body[0]["type"] == "order_requested"
    assert body[0]["isRead"] is False


def test_list_notifications_with_only_unread_filter(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    notif_id = uuid4()

    def _fake_list_notifications(self, user_id, only_unread=False, skip=0, limit=20):
        assert only_unread is True
        return [
            {
                "id": notif_id,
                "type": "order_accepted",
                "title": "Order Accepted",
                "body": "Your order was accepted.",
                "is_read": False,
                "created_at": "2026-04-28T00:00:00Z",
                "order_id": None,
                "listing_id": None,
            }
        ]

    monkeypatch.setattr(NotificationService, "list_notifications", _fake_list_notifications)

    response = client.get("/notifications/?only_unread=true")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["isRead"] is False


def test_get_notification_returns_200_for_owner(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    notif_id = uuid4()

    def _fake_get_notification_by_id(self, notification_id, current_user_id):
        assert notification_id == notif_id
        return {
            "id": notif_id,
            "type": "review_received",
            "title": "New Review",
            "body": "You received a new review.",
            "user_id": current_user_id,
            "sender_id": None,
            "order_id": None,
            "listing_id": None,
            "is_read": False,
            "read_at": None,
            "created_at": "2026-04-28T00:00:00Z",
        }

    monkeypatch.setattr(NotificationService, "get_notification_by_id", _fake_get_notification_by_id)

    response = client.get(f"/notifications/{notif_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(notif_id)
    assert body["isRead"] is False


def test_get_notification_returns_404_when_missing(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    missing_id = uuid4()

    def _fake_get_notification_by_id(self, notification_id, current_user_id):
        raise NotificationNotFoundError()

    monkeypatch.setattr(NotificationService, "get_notification_by_id", _fake_get_notification_by_id)

    response = client.get(f"/notifications/{missing_id}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Notification not found"


def test_get_notification_returns_403_when_not_owner(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    notif_id = uuid4()

    def _fake_get_notification_by_id(self, notification_id, current_user_id):
        raise NotificationForbiddenError()

    monkeypatch.setattr(NotificationService, "get_notification_by_id", _fake_get_notification_by_id)

    response = client.get(f"/notifications/{notif_id}")

    assert response.status_code == 403
    assert response.json()["detail"] == "You are not authorized to access this notification"


def test_mark_as_read_returns_200_and_marks_notification(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    notif_id = uuid4()

    def _fake_mark_as_read(self, notification_id, current_user_id):
        return {
            "id": notif_id,
            "is_read": True,
            "read_at": "2026-04-28T12:00:00Z",
        }

    monkeypatch.setattr(NotificationService, "mark_as_read", _fake_mark_as_read)

    response = client.patch(f"/notifications/{notif_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(notif_id)
    assert body["isRead"] is True


def test_mark_all_as_read_returns_200_and_list(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_mark_all_as_read(self, current_user_id):
        return {"updated_count": 2}

    monkeypatch.setattr(NotificationService, "mark_all_as_read", _fake_mark_all_as_read)

    response = client.patch("/notifications/mark-all-as-read")

    assert response.status_code == 200
    body = response.json()
    assert body["updated_count"] == 2


def test_delete_notification_returns_200_for_owner(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    notif_id = uuid4()

    def _fake_delete_notification(self, notification_id, current_user_id):
        return {"message": "Notification deleted successfully"}

    monkeypatch.setattr(NotificationService, "delete_notification", _fake_delete_notification)

    response = client.delete(f"/notifications/{notif_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "Notification deleted successfully"


def test_delete_notification_returns_404_when_missing(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    missing_id = uuid4()

    def _fake_delete_notification(self, notification_id, current_user_id):
        raise NotificationNotFoundError()

    monkeypatch.setattr(NotificationService, "delete_notification", _fake_delete_notification)

    response = client.delete(f"/notifications/{missing_id}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Notification not found"


def test_delete_notification_returns_403_when_not_owner(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    notif_id = uuid4()

    def _fake_delete_notification(self, notification_id, current_user_id):
        raise NotificationForbiddenError()

    monkeypatch.setattr(NotificationService, "delete_notification", _fake_delete_notification)

    response = client.delete(f"/notifications/{notif_id}")

    assert response.status_code == 403
    assert response.json()["detail"] == "You are not authorized to access this notification"
