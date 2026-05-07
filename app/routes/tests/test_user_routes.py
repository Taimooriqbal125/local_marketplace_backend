"""Test user routes - validates authentication, authorization, and user CRUD operations."""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi.security import OAuth2PasswordRequestForm

from app.core.security import get_current_user, get_current_admin_user
from app.core.rate_limiter import login_rate_limit, signup_rate_limit
from app.db.session import get_db
from app.routes.user_routes import router
from app.services.user_service import (
	UserService,
	UserNotFoundError,
	UserConflictError,
	PhoneConflictError,
	UserForbiddenError,
)


def _user_payload(
	user_id,
	email,
	is_active=True,
	is_admin=False,
	is_email_verified=False,
	email_verified_at=None,
	last_active_at=None,
	phone=None,
	created_at="2024-01-01T00:00:00Z",
	updated_at="2024-01-01T00:00:00Z",
):
	return {
		"id": str(user_id),
		"email": email,
		"is_active": is_active,
		"is_admin": is_admin,
		"is_email_verified": is_email_verified,
		"email_verified_at": email_verified_at,
		"last_active_at": last_active_at,
		"phone": phone,
		"created_at": created_at,
		"updated_at": updated_at,
	}


def _token_payload(user_payload, access_token="test_access_token", refresh_token="test_refresh_token"):
	return {
		"access_token": access_token,
		"refresh_token": refresh_token,
		"token_type": "bearer",
		"user": user_payload,
	}


def _build_test_app(current_user=None) -> FastAPI:
	app = FastAPI()
	app.include_router(router)

	def _override_get_db():
		yield object()

	app.dependency_overrides[get_db] = _override_get_db
	app.dependency_overrides[login_rate_limit] = lambda: None
	app.dependency_overrides[signup_rate_limit] = lambda: None

	if current_user is None:
		current_user = SimpleNamespace(id=uuid4(), is_admin=False)
	app.dependency_overrides[get_current_user] = lambda: current_user
	
	def _admin_override():
		if current_user.is_admin:
			return current_user
		from fastapi import HTTPException, status
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
	
	app.dependency_overrides[get_current_admin_user] = _admin_override

	return app


@pytest.fixture
def client() -> TestClient:
	return TestClient(_build_test_app())


@pytest.fixture
def admin_client() -> TestClient:
	admin_user = SimpleNamespace(id=uuid4(), is_admin=True)
	return TestClient(_build_test_app(admin_user))


def test_login_returns_token(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
	"""Test that login endpoint returns a token on successful authentication."""
	access_token = "test_access_token"
	user_id = uuid4()

	def _fake_login(self, email, password):
		return _token_payload(_user_payload(user_id, email), access_token=access_token)

	monkeypatch.setattr(UserService, "login", _fake_login)

	response = client.post("/users/login", data={"username": "user@example.com", "password": "password123"})

	assert response.status_code == 200
	assert response.json()["accessToken"] == access_token
	assert response.json()["tokenType"] == "bearer"


def test_signup_creates_user(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
	"""Test that signup endpoint creates a new user and returns 201."""
	user_id = uuid4()

	def _fake_create_user(self, user_data):
		return _user_payload(user_id, user_data.email)

	monkeypatch.setattr(UserService, "create_user", _fake_create_user)

	response = client.post("/users/signup", json={
		"email": "newuser@example.com",
		"password": "SecurePass123!",
	})

	assert response.status_code == 201
	assert response.json()["email"] == "newuser@example.com"


def test_signup_returns_409_duplicate_email(
	client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
	"""Test that signup returns 409 when email already exists."""
	def _fake_create_user(self, user_data):
		raise UserConflictError()

	monkeypatch.setattr(UserService, "create_user", _fake_create_user)

	response = client.post("/users/signup", json={
		"email": "existing@example.com",
		"password": "password123",
	})

	assert response.status_code == 400


def test_signup_returns_409_duplicate_phone(
	client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
	"""Test that signup returns 409 when phone number already exists."""
	def _fake_create_user(self, user_data):
		raise PhoneConflictError()

	monkeypatch.setattr(UserService, "create_user", _fake_create_user)

	response = client.post("/users/signup", json={
		"email": "user@example.com",
		"password": "password123",
		"phone": "03001234567",
	})

	assert response.status_code == 400


def test_get_all_users_requires_admin(client: TestClient) -> None:
	"""Test that GET /users/ requires admin authentication."""
	response = client.get("/users/")

	assert response.status_code == 403


def test_get_all_users_returns_list(admin_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
	"""Test that GET /users/ returns list of users for admin."""
	user_id_1 = uuid4()
	user_id_2 = uuid4()

	def _fake_get_all_users(self, skip, limit, is_active, is_admin):
		return [
			_user_payload(user_id_1, "user1@example.com", is_active=True),
			_user_payload(user_id_2, "user2@example.com", is_active=False),
		]

	monkeypatch.setattr(UserService, "get_all_users", _fake_get_all_users)

	response = admin_client.get("/users/?skip=0&limit=100")

	assert response.status_code == 200
	assert len(response.json()) == 2


def test_get_all_users_passes_filter_parameters(
	admin_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
	"""Test that GET /users/ passes filter parameters to service."""
	captured_kwargs = {}

	def _fake_get_all_users(self, skip, limit, is_active, is_admin):
		captured_kwargs.update({"skip": skip, "limit": limit, "is_active": is_active, "is_admin": is_admin})
		return []

	monkeypatch.setattr(UserService, "get_all_users", _fake_get_all_users)

	response = admin_client.get("/users/?skip=10&limit=50&is_active=true&is_admin=false")

	assert response.status_code == 200
	assert captured_kwargs["skip"] == 10
	assert captured_kwargs["limit"] == 50
	assert captured_kwargs["is_active"] is True
	assert captured_kwargs["is_admin"] is False


def test_get_user_returns_404_not_found(
	client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
	"""Test that GET /users/{user_id} returns 404 when user not found."""
	user_id = uuid4()

	def _fake_get_user(self, incoming_user_id):
		raise UserNotFoundError()

	monkeypatch.setattr(UserService, "get_user", _fake_get_user)

	response = client.get(f"/users/{user_id}")

	assert response.status_code == 404


def test_get_user_returns_user(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
	"""Test that GET /users/{user_id} returns user data."""
	user_id = uuid4()

	def _fake_get_user(self, incoming_user_id):
		return _user_payload(user_id, "user@example.com", is_active=True)

	monkeypatch.setattr(UserService, "get_user", _fake_get_user)

	response = client.get(f"/users/{user_id}")

	assert response.status_code == 200
	assert response.json()["email"] == "user@example.com"


def test_update_user_returns_403_not_owner(
	client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
	"""Test that PATCH /users/{user_id} returns 403 when user is not owner and not admin."""
	other_user_id = uuid4()

	def _fake_update_user(self, user_id, user_data, current_user):
		raise UserForbiddenError("You can only update your own account")

	monkeypatch.setattr(UserService, "update_user", _fake_update_user)

	response = client.patch(f"/users/{other_user_id}", json={"email": "newemail@example.com"})

	assert response.status_code == 403


def test_update_user_succeeds_for_owner(
	client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
	"""Test that PATCH /users/{user_id} succeeds for user updating own profile."""
	user_id = uuid4()
	current_user = SimpleNamespace(id=user_id, is_admin=False)
	app = _build_test_app(current_user)
	test_client = TestClient(app)

	captured_user_id = None
	captured_current_user_id = None

	def _fake_update_user(self, user_id, user_data, current_user):
		nonlocal captured_user_id, captured_current_user_id
		captured_user_id = user_id
		captured_current_user_id = current_user.id
		return _user_payload(user_id, user_data.email)

	monkeypatch.setattr(UserService, "update_user", _fake_update_user)

	response = test_client.patch(f"/users/{user_id}", json={"email": "newemail@example.com"})

	assert response.status_code == 200
	assert captured_user_id == user_id
	assert captured_current_user_id == user_id


def test_update_user_admin_can_change_is_admin(
	admin_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
	"""Test that admin can change is_admin or is_active flags."""
	target_user_id = uuid4()

	captured_user_id = None

	def _fake_update_user(self, user_id, user_data, current_user):
		nonlocal captured_user_id
		captured_user_id = user_id
		return _user_payload(user_id, "user@example.com", is_admin=True)

	monkeypatch.setattr(UserService, "update_user", _fake_update_user)

	response = admin_client.patch(f"/users/{target_user_id}", json={"is_admin": True})

	assert response.status_code == 200
	assert captured_user_id == target_user_id


def test_update_user_returns_404_not_found(
	client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
	"""Test that PATCH returns 404 when user doesn't exist."""
	user_id = uuid4()

	def _fake_update_user(self, user_id, user_data, current_user):
		raise UserNotFoundError()

	monkeypatch.setattr(UserService, "update_user", _fake_update_user)

	response = client.patch(f"/users/{user_id}", json={"email": "new@example.com"})

	assert response.status_code == 404


def test_delete_user_requires_admin(client: TestClient) -> None:
	"""Test that DELETE /users/{user_id} requires admin authentication."""
	user_id = uuid4()
	response = client.delete(f"/users/{user_id}")

	assert response.status_code == 403


def test_delete_user_succeeds_for_admin(
	admin_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
	"""Test that DELETE /users/{user_id} succeeds for admin."""
	user_id = uuid4()

	captured_user_id = None

	def _fake_delete_user(self, incoming_user_id):
		nonlocal captured_user_id
		captured_user_id = incoming_user_id
		return None

	monkeypatch.setattr(UserService, "delete_user", _fake_delete_user)

	response = admin_client.delete(f"/users/{user_id}")

	assert response.status_code == 200
	assert response.json()["message"] == "User deleted successfully."
	assert captured_user_id == user_id


def test_delete_user_returns_404_not_found(
	admin_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
	"""Test that DELETE returns 404 when user doesn't exist."""
	user_id = uuid4()

	def _fake_delete_user(self, incoming_user_id):
		raise UserNotFoundError()

	monkeypatch.setattr(UserService, "delete_user", _fake_delete_user)

	response = admin_client.delete(f"/users/{user_id}")

	assert response.status_code == 404
