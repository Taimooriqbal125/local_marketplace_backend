from types import SimpleNamespace
from uuid import uuid4
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.db.session import get_db
from app.routes.profile_routes import router
from app.services.profile_service import (
    ProfileService,
    ProfileNotFoundError,
)


def _build_test_app(current_user=None) -> FastAPI:
    app = FastAPI()
    app.include_router(router)

    def _override_get_db():
        yield object()

    app.dependency_overrides[get_db] = _override_get_db
    if current_user is None:
        current_user = SimpleNamespace(id=uuid4(), is_admin=False, profile=None)
    app.dependency_overrides[get_current_user] = lambda: current_user
    return app


@pytest.fixture
def client() -> TestClient:
    return TestClient(_build_test_app())


# ============================================================================
# Profile Creation Tests
# ============================================================================

def test_create_profile_returns_400_for_invalid_json_format(
    client: TestClient,
) -> None:
    """Test that invalid JSON format in profile_data is properly rejected."""
    payload = {"profile_data": "{invalid json"}
    response = client.post("/profiles/", data=payload)

    assert response.status_code == 400
    assert "Invalid profile_data JSON format" in response.json()["detail"]


def test_create_profile_with_incomplete_json(
    client: TestClient,
) -> None:
    """Test that incomplete JSON in profile_data is rejected."""
    payload = {"profile_data": '{"name": "John"'}
    response = client.post("/profiles/", data=payload)

    assert response.status_code == 400
    assert "Invalid profile_data JSON format" in response.json()["detail"]


# ============================================================================
# Get My Profile Tests
# ============================================================================

def test_get_my_profile_returns_404_when_not_exists(
    client: TestClient,
) -> None:
    """Test that /profiles/me returns 404 when user has no profile."""
    user_id = uuid4()
    current_user = SimpleNamespace(id=user_id, is_admin=False, profile=None)
    app = _build_test_app(current_user)
    test_client = TestClient(app)

    response = test_client.get("/profiles/me")

    assert response.status_code == 404
    assert "Profile not found" in response.json()["detail"]


# ============================================================================
# Update Location Tests
# ============================================================================

def test_update_my_location_validates_latitude_bounds(
    client: TestClient,
) -> None:
    """Test that latitude > 90 is rejected."""
    payload = {"latitude": 91.0, "longitude": -74.0060}
    response = client.patch("/profiles/me/location", json=payload)

    assert response.status_code == 422


def test_update_my_location_validates_longitude_bounds(
    client: TestClient,
) -> None:
    """Test that longitude > 180 is rejected."""
    payload = {"latitude": 40.7128, "longitude": 181.0}
    response = client.patch("/profiles/me/location", json=payload)

    assert response.status_code == 422


def test_update_my_location_requires_both_coordinates(
    client: TestClient,
) -> None:
    """Test that both latitude and longitude are required."""
    payload = {"latitude": 40.7128}  # Missing longitude
    response = client.patch("/profiles/me/location", json=payload)

    assert response.status_code == 422


# ============================================================================
# Get All Profiles Tests (Admin Only)
# ============================================================================

def test_get_all_profiles_returns_403_for_non_admin(
    client: TestClient,
) -> None:
    """Test that non-admin users cannot access /profiles/."""
    response = client.get("/profiles/")

    assert response.status_code == 403
    assert "Only administrators" in response.json()["detail"]


# ============================================================================
# Get Single Profile Tests
# ============================================================================

def test_get_profile_uuid_validation(
    client: TestClient,
) -> None:
    """Test that invalid UUID format is rejected."""
    response = client.get("/profiles/not-a-uuid")

    assert response.status_code == 422


def test_get_profile_returns_404_when_not_found(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that get profile returns 404 when profile missing."""
    user_id = uuid4()

    def _fake_get_profile(self, user_id):
        raise ProfileNotFoundError()

    monkeypatch.setattr(ProfileService, "get_profile", _fake_get_profile)

    response = client.get(f"/profiles/{user_id}")

    assert response.status_code == 404
    assert "Profile not found" in response.json()["detail"]


# ============================================================================
# Update Profile Tests
# ============================================================================

def test_update_profile_returns_403_for_non_owner_non_admin(
    client: TestClient,
) -> None:
    """Test that non-owner cannot update another user's profile."""
    other_user_id = uuid4()
    payload = {"profile_data": '{"name": "Updated"}'}
    response = client.patch(f"/profiles/{other_user_id}", data=payload)

    assert response.status_code == 403
    assert "Cannot update another user's profile" in response.json()["detail"]


def test_update_profile_returns_400_for_invalid_json(
    client: TestClient,
) -> None:
    """Test that invalid JSON in update payload is rejected."""
    user_id = uuid4()
    app = _build_test_app(SimpleNamespace(id=user_id, is_admin=False))
    test_client = TestClient(app)

    payload = {"profile_data": "{invalid json"}
    response = test_client.patch(f"/profiles/{user_id}", data=payload)

    assert response.status_code == 400
    assert "Invalid profile_data JSON format" in response.json()["detail"]


# ============================================================================
# Delete Profile Tests
# ============================================================================

def test_delete_profile_returns_403_for_non_owner_non_admin(
    client: TestClient,
) -> None:
    """Test that non-owner cannot delete another user's profile."""
    other_user_id = uuid4()
    response = client.delete(f"/profiles/{other_user_id}")

    assert response.status_code == 403
    assert "Cannot delete another user's profile" in response.json()["detail"]


def test_delete_profile_returns_404_when_not_found(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that delete profile returns 404 when profile missing."""
    user_id = uuid4()
    app = _build_test_app(SimpleNamespace(id=user_id, is_admin=False))
    test_client = TestClient(app)

    async def _fake_delete_profile(self, user_id, background_tasks=None):
        raise ProfileNotFoundError()

    monkeypatch.setattr(ProfileService, "delete_profile", _fake_delete_profile)

    response = test_client.delete(f"/profiles/{user_id}")

    assert response.status_code == 404
    assert "Profile not found" in response.json()["detail"]
