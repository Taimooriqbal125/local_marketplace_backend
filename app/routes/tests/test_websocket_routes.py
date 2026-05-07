"""Test WebSocket routes — validates real-time connection, authentication, and message handling."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.db.session import get_db
from app.routes.websocket_routes import router
from app.websocket import manager


def _build_test_app() -> FastAPI:
    """Builds a minimal FastAPI app with the websocket router."""
    app = FastAPI()
    app.include_router(router)

    def _override_get_db():
        yield MagicMock()

    app.dependency_overrides[get_db] = _override_get_db
    return app


@pytest.fixture
def client() -> TestClient:
    """Fixture providing a TestClient for the websocket app."""
    return TestClient(_build_test_app())


def test_websocket_connection_unauthorized(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    """Test that connection is refused without a valid token."""
    from app.routes import websocket_routes
    
    # Mock get_token_user_id to return None (invalid token)
    monkeypatch.setattr(websocket_routes, "get_token_user_id", AsyncMock(return_value=None))

    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/ws/?token=invalid_token"):
            pass
    
    assert exc.value.code == status.WS_1008_POLICY_VIOLATION


def test_websocket_connection_success(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    """Test successful websocket connection and manager registration."""
    user_id = uuid.uuid4()
    from app.routes import websocket_routes
    
    # Mock authentication
    monkeypatch.setattr(websocket_routes, "get_token_user_id", AsyncMock(return_value=user_id))
    
    # Mock manager methods to track calls
    # Note: connect is async in manager, disconnect is sync
    async def mock_connect_side_effect(websocket, user_id):
        await websocket.accept()
        
    mock_connect = AsyncMock(side_effect=mock_connect_side_effect)
    mock_disconnect = MagicMock()
    monkeypatch.setattr(manager, "connect", mock_connect)
    monkeypatch.setattr(manager, "disconnect", mock_disconnect)

    with client.websocket_connect(f"/ws/?token=valid_token") as websocket:
        # Verify manager.connect was called with our user_id
        mock_connect.assert_called_once()
        args, _ = mock_connect.call_args
        assert args[1] == user_id

    # Connection closed after exiting 'with' block
    mock_disconnect.assert_called_once()


def test_websocket_message_handling(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    """Test that incoming messages are passed to the handler."""
    user_id = uuid.uuid4()
    from app.routes import websocket_routes
    
    # Mock authentication
    monkeypatch.setattr(websocket_routes, "get_token_user_id", AsyncMock(return_value=user_id))
    
    # Mock handler
    mock_handler = AsyncMock()
    monkeypatch.setattr(websocket_routes, "handle_websocket_message", mock_handler)
    
    test_data = {"event": "test_event", "data": {"key": "value"}}

    with client.websocket_connect(f"/ws/?token=valid_token") as websocket:
        websocket.send_json(test_data)
        
        # Verify handler was called with correct data
        # TestClient processes the message handling synchronously enough for this to work
        mock_handler.assert_called()
        
        # Check call arguments
        _, kwargs = mock_handler.call_args
        assert kwargs["user_id"] == user_id
        assert kwargs["data"] == test_data


def test_websocket_internal_error_cleanup(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    """Test that manager disconnects and socket closes on internal handler error."""
    user_id = uuid.uuid4()
    from app.routes import websocket_routes
    
    monkeypatch.setattr(websocket_routes, "get_token_user_id", AsyncMock(return_value=user_id))
    
    # Mock handler to raise an exception
    mock_handler = AsyncMock(side_effect=Exception("Unexpected crash"))
    monkeypatch.setattr(websocket_routes, "handle_websocket_message", mock_handler)
    
    mock_disconnect = MagicMock()
    monkeypatch.setattr(manager, "disconnect", mock_disconnect)

    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(f"/ws/?token=valid_token") as websocket:
            websocket.send_json({"event": "trigger_error"})
            # Try to receive to wait for the server to process and close
            websocket.receive_json()

    assert exc.value.code == status.WS_1011_INTERNAL_ERROR
    mock_disconnect.assert_called_once()
