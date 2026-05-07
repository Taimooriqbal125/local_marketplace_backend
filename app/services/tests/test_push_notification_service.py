"""
Unit tests for Push Notification Service.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from app.services.push_notification_service import PushNotificationService


class FakeResponse:
    def __init__(self, body: dict) -> None:
        self._body = body

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._body

    @property
    def text(self) -> str:
        return json.dumps(self._body)


class FakeAsyncClient:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.request_kwargs = None

    async def __aenter__(self) -> "FakeAsyncClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def post(self, *args, **kwargs) -> FakeResponse:
        self.request_kwargs = kwargs
        return self.response


@pytest.fixture
def db_session() -> MagicMock:
    return MagicMock(spec=Session)


@pytest.fixture
def push_service(db_session: MagicMock) -> PushNotificationService:
    return PushNotificationService(db_session)


@pytest.mark.anyio
async def test_send_to_token_accepts_single_ticket_object(push_service: PushNotificationService, monkeypatch: pytest.MonkeyPatch) -> None:
    response = FakeResponse({"data": {"status": "ok", "id": "ticket-1"}})
    fake_client = FakeAsyncClient(response)

    monkeypatch.setattr("app.services.push_notification_service.httpx.AsyncClient", lambda: fake_client)

    success, ticket_id = await push_service.send_to_token(
        expo_push_token="ExponentPushToken[xxxxxxxxxxxxxxxxxxxxxx]",
        title="New order",
        body="You have a new request",
    )

    assert success is True
    assert ticket_id == "ticket-1"
    assert fake_client.request_kwargs["json"]["to"] == "ExponentPushToken[xxxxxxxxxxxxxxxxxxxxxx]"


@pytest.mark.anyio
async def test_send_to_token_accepts_ticket_list(push_service: PushNotificationService, monkeypatch: pytest.MonkeyPatch) -> None:
    response = FakeResponse({"data": [{"status": "ok", "id": "ticket-2"}]})
    fake_client = FakeAsyncClient(response)

    monkeypatch.setattr("app.services.push_notification_service.httpx.AsyncClient", lambda: fake_client)

    success, ticket_id = await push_service.send_to_token(
        expo_push_token="ExponentPushToken[yyyyyyyyyyyyyyyyyyyyyy]",
        title="New order",
        body="You have a new request",
    )

    assert success is True
    assert ticket_id == "ticket-2"


@pytest.mark.anyio
async def test_send_to_token_rejects_malformed_token(push_service: PushNotificationService, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_client = FakeAsyncClient(FakeResponse({"data": {"status": "ok", "id": "ticket-1"}}))

    monkeypatch.setattr("app.services.push_notification_service.httpx.AsyncClient", lambda: fake_client)

    success, ticket_id = await push_service.send_to_token(
        expo_push_token="not-a-real-token",
        title="New order",
        body="You have a new request",
    )

    assert success is False
    assert ticket_id is None
    assert fake_client.request_kwargs is None


@pytest.mark.anyio
async def test_get_push_receipt_success(push_service: PushNotificationService, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test fetching a push receipt that indicates successful delivery."""
    response = FakeResponse({
        "data": {
            "ticket-123": {
                "status": "ok",
                "id": "receipt-123"
            }
        }
    })
    fake_client = FakeAsyncClient(response)

    monkeypatch.setattr("app.services.push_notification_service.httpx.AsyncClient", lambda: fake_client)

    receipt = await push_service.get_push_receipt("ticket-123")

    assert receipt is not None
    assert receipt["status"] == "ok"
    assert receipt["id"] == "receipt-123"
    assert fake_client.request_kwargs["json"]["ids"] == ["ticket-123"]


@pytest.mark.anyio
async def test_get_push_receipt_device_not_registered(push_service: PushNotificationService, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test fetching a receipt showing device is no longer registered."""
    response = FakeResponse({
        "data": {
            "ticket-456": {
                "status": "error",
                "message": "The device is not a valid FCM registration ID",
                "details": {
                    "error": "DeviceNotRegistered"
                }
            }
        }
    })
    fake_client = FakeAsyncClient(response)

    monkeypatch.setattr("app.services.push_notification_service.httpx.AsyncClient", lambda: fake_client)

    receipt = await push_service.get_push_receipt("ticket-456")

    assert receipt is not None
    assert receipt["status"] == "error"
    assert receipt["details"]["error"] == "DeviceNotRegistered"


@pytest.mark.anyio
async def test_get_push_receipts_batch(push_service: PushNotificationService, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test fetching multiple push receipts in one request."""
    response = FakeResponse({
        "data": {
            "ticket-1": {
                "status": "ok",
                "id": "receipt-1"
            },
            "ticket-2": {
                "status": "error",
                "message": "Invalid token",
                "details": {"error": "DeviceNotRegistered"}
            }
        }
    })
    fake_client = FakeAsyncClient(response)

    monkeypatch.setattr("app.services.push_notification_service.httpx.AsyncClient", lambda: fake_client)

    results = await push_service.get_push_receipts_batch(["ticket-1", "ticket-2"])

    assert len(results) == 2
    assert results["ticket-1"]["status"] == "ok"
    assert results["ticket-2"]["status"] == "error"
    assert fake_client.request_kwargs["json"]["ids"] == ["ticket-1", "ticket-2"]
