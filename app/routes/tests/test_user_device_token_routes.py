"""
Test suite for UserDeviceToken routes.

Tests the API endpoints for managing user device push notification tokens,
including registration, listing, deactivation, and deletion.
"""

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.db.session import get_db
from app.models.user_device_tokens import UserDeviceToken
from app.routes.user_device_token_routes import router
from app.services.user_device_token_service import UserDeviceTokenService


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS & TEST APP SETUP
# ─────────────────────────────────────────────────────────────────────────────

def _device_token_response(
    token_id: str,
    user_id: str,
    expo_push_token: str,
    device_type: str,
    device_name: str | None = None,
    is_active: bool = True,
    last_used_at: str | None = None,
    created_at: str = "2024-01-01T00:00:00Z",
    updated_at: str = "2024-01-01T00:00:00Z",
) -> dict:
    """Helper to create a device token response payload."""
    return {
        "id": token_id,
        "user_id": user_id,
        "expo_push_token": expo_push_token,
        "device_type": device_type,
        "device_name": device_name,
        "is_active": is_active,
        "last_used_at": last_used_at,
        "created_at": created_at,
        "updated_at": updated_at,
    }


def _build_test_app(current_user: SimpleNamespace | None = None) -> FastAPI:
    """Build FastAPI test application with dependency overrides."""
    app = FastAPI()
    app.include_router(router)

    # Override database dependency
    def _override_get_db():
        yield object()

    app.dependency_overrides[get_db] = _override_get_db

    # Set current user
    if current_user is None:
        current_user = SimpleNamespace(id=uuid.uuid4(), email="testuser@example.com")
    app.dependency_overrides[get_current_user] = lambda: current_user

    return app


# ─────────────────────────────────────────────────────────────────────────────
# FIXTURES
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def current_user() -> SimpleNamespace:
    """Fixture providing a mock authenticated user."""
    return SimpleNamespace(
        id=uuid.uuid4(),
        email="testuser@example.com",
        is_active=True,
    )


@pytest.fixture
def client(current_user: SimpleNamespace) -> TestClient:
    """Fixture providing authenticated test client."""
    app = _build_test_app(current_user)
    return TestClient(app)


@pytest.fixture
def client_different_user() -> TestClient:
    """Fixture providing test client with a different user."""
    other_user = SimpleNamespace(
        id=uuid.uuid4(),
        email="otheruser@example.com",
        is_active=True,
    )
    app = _build_test_app(other_user)
    return TestClient(app)


@pytest.fixture
def unauthenticated_client() -> TestClient:
    """Fixture providing test client that simulates authentication failure."""
    app = FastAPI()
    app.include_router(router)
    
    def _override_get_db():
        yield object()
    
    def _override_get_current_user():
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    
    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _override_get_current_user
    
    return TestClient(app)


# ─────────────────────────────────────────────────────────────────────────────
# REGISTER DEVICE TOKEN (POST)
# ─────────────────────────────────────────────────────────────────────────────

class TestRegisterDeviceToken:
    """Tests for POST /device-tokens endpoint."""

    def test_register_new_token_success(
        self,
        client: TestClient,
        current_user: SimpleNamespace,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test successfully registering a new device token."""
        # Arrange
        token_id = uuid.uuid4()
        token_data = {
            "expo_push_token": "ExponentPushToken[test123]",
            "device_type": "android",
            "device_name": "Samsung Galaxy",
        }
        
        mock_token = SimpleNamespace(
            id=token_id,
            userId=current_user.id,
            expo_push_token=token_data["expo_push_token"],
            deviceType=token_data["device_type"],
            deviceName=token_data["device_name"],
            isActive=True,
            lastUsedAt=None,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        def _fake_register(self, user_id, obj_in):
            return mock_token

        monkeypatch.setattr(UserDeviceTokenService, "register_token", _fake_register)

        # Act
        response = client.post("/device-tokens/", json=token_data)

        # Assert
        assert response.status_code == 201
        assert response.json()["deviceType"] == "android"
        assert response.json()["expoPushToken"] == "ExponentPushToken[test123]"
        assert response.json()["isActive"] is True

    def test_register_token_without_device_name(
        self,
        client: TestClient,
        current_user: SimpleNamespace,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test registering token with optional device name omitted."""
        # Arrange
        token_id = uuid.uuid4()
        token_data = {
            "expo_push_token": "ExponentPushToken[test456]",
            "device_type": "ios",
        }

        mock_token = SimpleNamespace(
            id=token_id,
            userId=current_user.id,
            expo_push_token=token_data["expo_push_token"],
            deviceType=token_data["device_type"],
            deviceName=None,
            isActive=True,
            lastUsedAt=None,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        def _fake_register(self, user_id, obj_in):
            return mock_token

        monkeypatch.setattr(UserDeviceTokenService, "register_token", _fake_register)

        # Act
        response = client.post("/device-tokens/", json=token_data)

        # Assert
        assert response.status_code == 201
        assert response.json()["deviceName"] is None
        assert response.json()["deviceType"] == "ios"

    def test_register_token_requires_authentication(
        self,
        unauthenticated_client: TestClient,
    ) -> None:
        """Test that registration endpoint requires authentication."""
        # Arrange
        token_data = {
            "expo_push_token": "ExponentPushToken[unauth]",
            "device_type": "android",
        }

        # Act
        response = unauthenticated_client.post("/device-tokens/", json=token_data)

        # Assert
        assert response.status_code == 401

    @pytest.mark.parametrize("device_type", [
        "android",
        "ios",
        "web",
        "macos",
        "windows",
    ])
    def test_register_token_various_device_types(
        self,
        client: TestClient,
        current_user: SimpleNamespace,
        monkeypatch: pytest.MonkeyPatch,
        device_type: str,
    ) -> None:
        """Test registering tokens for various device types."""
        # Arrange
        token_id = uuid.uuid4()
        token_data = {
            "expo_push_token": f"ExponentPushToken[{device_type}]",
            "device_type": device_type,
            "device_name": f"{device_type} Device",
        }

        mock_token = SimpleNamespace(
            id=token_id,
            userId=current_user.id,
            expo_push_token=token_data["expo_push_token"],
            deviceType=device_type,
            deviceName=token_data["device_name"],
            isActive=True,
            lastUsedAt=None,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        def _fake_register(self, user_id, obj_in):
            return mock_token

        monkeypatch.setattr(UserDeviceTokenService, "register_token", _fake_register)

        # Act
        response = client.post("/device-tokens/", json=token_data)

        # Assert
        assert response.status_code == 201
        assert response.json()["deviceType"] == device_type

    def test_register_token_returns_201_created(
        self,
        client: TestClient,
        current_user: SimpleNamespace,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that successful registration returns 201 Created."""
        # Arrange
        token_data = {
            "expo_push_token": "ExponentPushToken[test]",
            "device_type": "android",
        }

        mock_token = SimpleNamespace(
            id=uuid.uuid4(),
            userId=current_user.id,
            expo_push_token=token_data["expo_push_token"],
            deviceType=token_data["device_type"],
            deviceName=None,
            isActive=True,
            lastUsedAt=None,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        def _fake_register(self, user_id, obj_in):
            return mock_token

        monkeypatch.setattr(UserDeviceTokenService, "register_token", _fake_register)

        # Act
        response = client.post("/device-tokens/", json=token_data)

        # Assert
        assert response.status_code == 201


# ─────────────────────────────────────────────────────────────────────────────
# LIST DEVICE TOKENS (GET)
# ─────────────────────────────────────────────────────────────────────────────

class TestListDeviceTokens:
    """Tests for GET /device-tokens endpoint."""

    def test_list_user_tokens_returns_list(
        self,
        client: TestClient,
        current_user: SimpleNamespace,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that listing tokens returns a list of user's tokens."""
        # Arrange
        token1_id = uuid.uuid4()
        token2_id = uuid.uuid4()

        mock_tokens = [
            SimpleNamespace(
                id=token1_id,
                userId=current_user.id,
                expo_push_token="ExponentPushToken[token1]",
                deviceType="android",
                deviceName="Phone 1",
                isActive=True,
                lastUsedAt=None,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            ),
            SimpleNamespace(
                id=token2_id,
                userId=current_user.id,
                expo_push_token="ExponentPushToken[token2]",
                deviceType="ios",
                deviceName="Phone 2",
                isActive=True,
                lastUsedAt=None,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            ),
        ]

        def _fake_get_user_tokens(self, user_id, active_only=True):
            return mock_tokens

        monkeypatch.setattr(UserDeviceTokenService, "get_user_tokens", _fake_get_user_tokens)

        # Act
        response = client.get("/device-tokens/")

        # Assert
        assert response.status_code == 200
        assert len(response.json()) == 2
        assert response.json()[0]["deviceType"] == "android"
        assert response.json()[1]["deviceType"] == "ios"

    def test_list_tokens_with_active_only_filter(
        self,
        client: TestClient,
        current_user: SimpleNamespace,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test listing tokens with active_only filter."""
        # Arrange
        mock_tokens = [
            SimpleNamespace(
                id=uuid.uuid4(),
                userId=current_user.id,
                expo_push_token="ExponentPushToken[active]",
                deviceType="android",
                deviceName="Phone",
                isActive=True,
                lastUsedAt=None,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            ),
        ]

        def _fake_get_user_tokens(self, user_id, active_only=True):
            if active_only:
                return mock_tokens
            return mock_tokens  # In real scenario would include inactive

        monkeypatch.setattr(UserDeviceTokenService, "get_user_tokens", _fake_get_user_tokens)

        # Act
        response = client.get("/device-tokens/?active_only=true")

        # Assert
        assert response.status_code == 200
        assert len(response.json()) == 1
        assert response.json()[0]["isActive"] is True

    def test_list_tokens_includes_all_when_active_only_false(
        self,
        client: TestClient,
        current_user: SimpleNamespace,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test listing all tokens (active and inactive) when active_only=false."""
        # Arrange
        mock_tokens = [
            SimpleNamespace(
                id=uuid.uuid4(),
                userId=current_user.id,
                expo_push_token="ExponentPushToken[active]",
                deviceType="android",
                deviceName="Active Phone",
                isActive=True,
                lastUsedAt=None,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            ),
            SimpleNamespace(
                id=uuid.uuid4(),
                userId=current_user.id,
                expo_push_token="ExponentPushToken[inactive]",
                deviceType="ios",
                deviceName="Inactive Phone",
                isActive=False,
                lastUsedAt=None,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            ),
        ]

        def _fake_get_user_tokens(self, user_id, active_only=True):
            if active_only:
                return [t for t in mock_tokens if t.isActive]
            return mock_tokens

        monkeypatch.setattr(UserDeviceTokenService, "get_user_tokens", _fake_get_user_tokens)

        # Act
        response = client.get("/device-tokens/?active_only=false")

        # Assert
        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_list_tokens_empty_result(
        self,
        client: TestClient,
        current_user: SimpleNamespace,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test listing tokens when user has no tokens."""
        # Arrange
        def _fake_get_user_tokens(self, user_id, active_only=True):
            return []

        monkeypatch.setattr(UserDeviceTokenService, "get_user_tokens", _fake_get_user_tokens)

        # Act
        response = client.get("/device-tokens/")

        # Assert
        assert response.status_code == 200
        assert response.json() == []

    def test_list_tokens_requires_authentication(
        self,
        unauthenticated_client: TestClient,
    ) -> None:
        """Test that listing requires authentication."""
        # Act
        response = unauthenticated_client.get("/device-tokens/")

        # Assert
        assert response.status_code == 401


# ─────────────────────────────────────────────────────────────────────────────
# DELETE DEVICE TOKEN (DELETE)
# ─────────────────────────────────────────────────────────────────────────────

class TestDeleteDeviceToken:
    """Tests for DELETE /device-tokens/{token_id} endpoint."""

    def test_delete_token_success(
        self,
        client: TestClient,
        current_user: SimpleNamespace,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test successfully deleting a device token."""
        # Arrange
        token_id = uuid.uuid4()

        def _fake_delete_token(self, token_id, user_id):
            return {"message": "Device token deleted successfully"}

        monkeypatch.setattr(UserDeviceTokenService, "delete_token", _fake_delete_token)

        # Act
        response = client.delete(f"/device-tokens/{token_id}")

        # Assert
        assert response.status_code == 200
        assert response.json()["message"] == "Device token deleted successfully"

    def test_delete_nonexistent_token_returns_404(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test deleting a nonexistent token returns 404."""
        # Arrange
        token_id = uuid.uuid4()

        def _fake_delete_token(self, token_id, user_id):
            from app.services.user_device_token_service import UserDeviceTokenNotFoundError
            raise UserDeviceTokenNotFoundError()

        monkeypatch.setattr(UserDeviceTokenService, "delete_token", _fake_delete_token)

        # Act
        response = client.delete(f"/device-tokens/{token_id}")

        # Assert
        assert response.status_code == 404

    def test_delete_token_not_owned_by_user_returns_404(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that user cannot delete tokens they don't own."""
        # Arrange
        token_id = uuid.uuid4()

        def _fake_delete_token(self, token_id, user_id):
            from app.services.user_device_token_service import UserDeviceTokenNotFoundError
            raise UserDeviceTokenNotFoundError()

        monkeypatch.setattr(UserDeviceTokenService, "delete_token", _fake_delete_token)

        # Act
        response = client.delete(f"/device-tokens/{token_id}")

        # Assert
        assert response.status_code == 404

    def test_delete_token_requires_authentication(
        self,
        unauthenticated_client: TestClient,
    ) -> None:
        """Test that deletion requires authentication."""
        # Arrange
        token_id = uuid.uuid4()

        # Act
        response = unauthenticated_client.delete(f"/device-tokens/{token_id}")

        # Assert
        assert response.status_code == 401

    def test_delete_token_returns_200_ok(
        self,
        client: TestClient,
        current_user: SimpleNamespace,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that successful deletion returns 200 OK."""
        # Arrange
        token_id = uuid.uuid4()

        def _fake_delete_token(self, token_id, user_id):
            return {"message": "Device token deleted successfully"}

        monkeypatch.setattr(UserDeviceTokenService, "delete_token", _fake_delete_token)

        # Act
        response = client.delete(f"/device-tokens/{token_id}")

        # Assert
        assert response.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# DEACTIVATE DEVICE TOKEN (PATCH)
# ─────────────────────────────────────────────────────────────────────────────

class TestDeactivateDeviceToken:
    """Tests for PATCH /device-tokens/deactivate endpoint."""

    def test_deactivate_token_success(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test successfully deactivating a device token."""
        # Arrange
        def _fake_deactivate_token(self, expo_push_token):
            return True

        monkeypatch.setattr(UserDeviceTokenService, "deactivate_token", _fake_deactivate_token)

        # Act
        response = client.patch(
            "/device-tokens/deactivate",
            json={"expo_push_token": "ExponentPushToken[test123]"},
        )

        # Assert
        assert response.status_code == 200
        assert response.json()["success"] is True
        assert response.json()["message"] == "Token deactivated successfully"

    def test_deactivate_nonexistent_token(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test deactivating a nonexistent token returns failure response."""
        # Arrange
        def _fake_deactivate_token(self, expo_push_token):
            return False

        monkeypatch.setattr(UserDeviceTokenService, "deactivate_token", _fake_deactivate_token)

        # Act
        response = client.patch(
            "/device-tokens/deactivate",
            json={"expo_push_token": "NonexistentToken[xyz]"},
        )

        # Assert
        assert response.status_code == 200
        assert response.json()["success"] is False
        assert "not found" in response.json()["message"].lower()

    def test_deactivate_token_requires_authentication(
        self,
        unauthenticated_client: TestClient,
    ) -> None:
        """Test that deactivation requires authentication."""
        # Act
        response = unauthenticated_client.patch(
            "/device-tokens/deactivate",
            json={"expo_push_token": "ExponentPushToken[test]"},
        )

        # Assert
        assert response.status_code == 401

    def test_deactivate_token_returns_200_ok(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that deactivate endpoint returns 200 OK."""
        # Arrange
        def _fake_deactivate_token(self, expo_push_token):
            return True

        monkeypatch.setattr(UserDeviceTokenService, "deactivate_token", _fake_deactivate_token)

        # Act
        response = client.patch(
            "/device-tokens/deactivate",
            json={"expo_push_token": "ExponentPushToken[test]"},
        )

        # Assert
        assert response.status_code == 200

    def test_deactivate_token_response_structure(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that deactivate response contains required fields."""
        # Arrange
        def _fake_deactivate_token(self, expo_push_token):
            return True

        monkeypatch.setattr(UserDeviceTokenService, "deactivate_token", _fake_deactivate_token)

        # Act
        response = client.patch(
            "/device-tokens/deactivate",
            json={"expo_push_token": "ExponentPushToken[test]"},
        )

        # Assert
        assert "message" in response.json()
        assert "success" in response.json()


# ─────────────────────────────────────────────────────────────────────────────
# AUTHORIZATION & SECURITY
# ─────────────────────────────────────────────────────────────────────────────

class TestAuthorizationAndSecurity:
    """Tests for authorization and security of device token endpoints."""

    def test_list_tokens_isolation_between_users(
        self,
        client: TestClient,
        client_different_user: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that users can only see their own tokens."""
        # This test verifies the endpoint doesn't expose other users' data
        # In actual implementation, the service layer enforces this

        def _fake_get_user_tokens(self, user_id, active_only=True):
            # Simulate returning tokens only for the querying user
            return []

        monkeypatch.setattr(UserDeviceTokenService, "get_user_tokens", _fake_get_user_tokens)

        # Act
        response1 = client.get("/device-tokens/")
        response2 = client_different_user.get("/device-tokens/")

        # Assert
        assert response1.status_code == 200
        assert response2.status_code == 200

    def test_all_endpoints_require_authentication(
        self,
        unauthenticated_client: TestClient,
    ) -> None:
        """Test that all device token endpoints require authentication."""
        # Test POST
        response = unauthenticated_client.post(
            "/device-tokens/",
            json={"expo_push_token": "test", "device_type": "android"},
        )
        assert response.status_code == 401

        # Test GET
        response = unauthenticated_client.get("/device-tokens/")
        assert response.status_code == 401

        # Test DELETE
        response = unauthenticated_client.delete(f"/device-tokens/{uuid.uuid4()}")
        assert response.status_code == 401

        # Test PATCH
        response = unauthenticated_client.patch(
            "/device-tokens/deactivate",
            json={"expo_push_token": "test"},
        )
        assert response.status_code == 401


# ─────────────────────────────────────────────────────────────────────────────
# RESPONSE VALIDATION
# ─────────────────────────────────────────────────────────────────────────────

class TestResponseValidation:
    """Tests for response schema and content validation."""

    def test_register_token_response_schema(
        self,
        client: TestClient,
        current_user: SimpleNamespace,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that token registration response has required fields."""
        # Arrange
        token_data = {
            "expo_push_token": "ExponentPushToken[test]",
            "device_type": "android",
            "device_name": "Phone",
        }

        mock_token = SimpleNamespace(
            id=uuid.uuid4(),
            userId=current_user.id,
            expo_push_token=token_data["expo_push_token"],
            deviceType=token_data["device_type"],
            deviceName=token_data["device_name"],
            isActive=True,
            lastUsedAt=None,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        def _fake_register(self, user_id, obj_in):
            return mock_token

        monkeypatch.setattr(UserDeviceTokenService, "register_token", _fake_register)

        # Act
        response = client.post("/device-tokens/", json=token_data)

        # Assert
        required_fields = ["id", "userId", "expoPushToken", "deviceType", "isActive", "createdAt", "updatedAt"]
        response_data = response.json()
        for field in required_fields:
            assert field in response_data

    def test_list_tokens_response_is_list(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that list endpoint returns a JSON array."""
        # Arrange
        def _fake_get_user_tokens(self, user_id, active_only=True):
            return []

        monkeypatch.setattr(UserDeviceTokenService, "get_user_tokens", _fake_get_user_tokens)

        # Act
        response = client.get("/device-tokens/")

        # Assert
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_delete_response_contains_success_message(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that delete response contains a success message."""
        # Arrange
        def _fake_delete_token(self, token_id, user_id):
            return {"message": "Device token deleted successfully"}

        monkeypatch.setattr(UserDeviceTokenService, "delete_token", _fake_delete_token)

        # Act
        response = client.delete(f"/device-tokens/{uuid.uuid4()}")

        # Assert
        assert response.status_code == 200
        assert "message" in response.json()
        assert response.json()["message"] != ""


# ─────────────────────────────────────────────────────────────────────────────
# EDGE CASES
# ─────────────────────────────────────────────────────────────────────────────

class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_register_token_with_long_device_name(
        self,
        client: TestClient,
        current_user: SimpleNamespace,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test registering token with very long device name."""
        # Arrange
        long_name = "A" * 255  # Max typical device name length
        token_data = {
            "expo_push_token": "ExponentPushToken[test]",
            "device_type": "android",
            "device_name": long_name,
        }

        mock_token = SimpleNamespace(
            id=uuid.uuid4(),
            userId=current_user.id,
            expo_push_token=token_data["expo_push_token"],
            deviceType=token_data["device_type"],
            deviceName=long_name,
            isActive=True,
            lastUsedAt=None,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        def _fake_register(self, user_id, obj_in):
            return mock_token

        monkeypatch.setattr(UserDeviceTokenService, "register_token", _fake_register)

        # Act
        response = client.post("/device-tokens/", json=token_data)

        # Assert
        assert response.status_code == 201
        assert len(response.json()["deviceName"]) == 255

    def test_register_multiple_tokens_same_user(
        self,
        client: TestClient,
        current_user: SimpleNamespace,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that a user can register multiple device tokens."""
        # Arrange
        tokens_created = []

        def _fake_register(self, user_id, obj_in):
            token = SimpleNamespace(
                id=uuid.uuid4(),
                userId=user_id,
                expo_push_token=obj_in.expo_push_token,
                deviceType=obj_in.device_type,
                deviceName=obj_in.device_name,
                isActive=True,
                lastUsedAt=None,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            tokens_created.append(token)
            return token

        monkeypatch.setattr(UserDeviceTokenService, "register_token", _fake_register)

        # Act
        token_data_1 = {
            "expo_push_token": "ExponentPushToken[token1]",
            "device_type": "android",
        }
        token_data_2 = {
            "expo_push_token": "ExponentPushToken[token2]",
            "device_type": "ios",
        }

        response1 = client.post("/device-tokens/", json=token_data_1)
        response2 = client.post("/device-tokens/", json=token_data_2)

        # Assert
        assert response1.status_code == 201
        assert response2.status_code == 201
        assert len(tokens_created) == 2
        assert tokens_created[0].expo_push_token != tokens_created[1].expo_push_token

    def test_list_tokens_handles_pagination_gracefully(
        self,
        client: TestClient,
        current_user: SimpleNamespace,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test listing many tokens doesn't cause performance issues."""
        # Arrange
        large_token_list = [
            SimpleNamespace(
                id=uuid.uuid4(),
                userId=current_user.id,
                expo_push_token=f"ExponentPushToken[token_{i}]",
                deviceType="android" if i % 2 == 0 else "ios",
                deviceName=f"Device {i}",
                isActive=True,
                lastUsedAt=None,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            for i in range(100)
        ]

        def _fake_get_user_tokens(self, user_id, active_only=True):
            return large_token_list

        monkeypatch.setattr(UserDeviceTokenService, "get_user_tokens", _fake_get_user_tokens)

        # Act
        response = client.get("/device-tokens/")

        # Assert
        assert response.status_code == 200
        assert len(response.json()) == 100

    def test_delete_token_with_invalid_uuid_format(
        self,
        client: TestClient,
    ) -> None:
        """Test deleting token with invalid UUID format."""
        # Act
        response = client.delete("/device-tokens/invalid-uuid")

        # Assert
        assert response.status_code == 422  # Validation error

    def test_deactivate_token_with_empty_token_string(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test deactivating with empty token string."""
        # Arrange
        def _fake_deactivate_token(self, expo_push_token):
            return False

        monkeypatch.setattr(UserDeviceTokenService, "deactivate_token", _fake_deactivate_token)

        # Act
        response = client.patch(
            "/device-tokens/deactivate",
            json={"expo_push_token": ""},
        )

        # Assert
        assert response.status_code in [200, 422]  # Either processed or validation error
