from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core import security
from app.core.rate_limiter import refresh_issue_rate_limit
from app.db.session import get_db
from app.models.user import User
from app.repositories import UserRepository
from app.routes.refresh_token_routes import router
from app.services.refresh_token_service import RefreshTokenService, TokenForbiddenError


def _build_test_app(current_user=None) -> FastAPI:
	app = FastAPI()
	app.include_router(router)

	def _override_get_db():
		yield object()

	app.dependency_overrides[get_db] = _override_get_db
	app.dependency_overrides[refresh_issue_rate_limit] = lambda: None
	if current_user is None:
		current_user = SimpleNamespace(id=uuid4())
	app.dependency_overrides[security.get_current_user] = lambda: current_user
	return app


@pytest.fixture
def client() -> TestClient:
	return TestClient(_build_test_app())


def test_issue_refresh_token_returns_201_and_sets_cookie(
	client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
	current_user_id = uuid4()
	app = _build_test_app(SimpleNamespace(id=current_user_id))
	test_client = TestClient(app)
	refresh_token = "r" * 64
	access_token = "access-token-value"

	def _fake_issue_token(self, user_id):
		assert user_id == current_user_id
		return refresh_token, SimpleNamespace(user_id=user_id)

	def _fake_create_access_token(data, expires_delta):
		assert data == {"sub": str(current_user_id)}
		assert expires_delta.total_seconds() > 0
		return access_token

	monkeypatch.setattr(RefreshTokenService, "issue_token", _fake_issue_token)
	monkeypatch.setattr(security, "create_access_token", _fake_create_access_token)

	response = test_client.post("/refreshtokens/issue")

	assert response.status_code == 201
	body = response.json()
	assert body["access_token"] == access_token
	assert body["refresh_token"] == refresh_token
	assert body["token_type"] == "bearer"
	assert "refresh_token=" in response.headers["set-cookie"]
	assert "HttpOnly" in response.headers["set-cookie"]


def test_rotate_refresh_token_returns_200_from_body_token(
	client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
	incoming_refresh_token = "i" * 64
	rotated_refresh_token = "n" * 64
	user_id = uuid4()
	access_token = "rotated-access-token"

	def _fake_rotate_token(self, raw_token):
		assert raw_token == incoming_refresh_token
		db_token = SimpleNamespace(user_id=user_id)
		return rotated_refresh_token, db_token

	def _fake_get(self, db_user_id):
		assert db_user_id == user_id
		return SimpleNamespace(id=user_id)

	def _fake_create_access_token(data, expires_delta):
		assert data == {"sub": str(user_id)}
		return access_token

	monkeypatch.setattr(RefreshTokenService, "rotate_token", _fake_rotate_token)
	monkeypatch.setattr(UserRepository, "get", _fake_get)
	monkeypatch.setattr(security, "create_access_token", _fake_create_access_token)

	response = client.post("/refreshtokens/rotate", json={"refresh_token": incoming_refresh_token})

	assert response.status_code == 200
	body = response.json()
	assert body["access_token"] == access_token
	assert body["refresh_token"] == rotated_refresh_token
	assert body["token_type"] == "bearer"
	assert "refresh_token=" in response.headers["set-cookie"]


def test_rotate_refresh_token_reads_token_from_cookie(
	client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
	incoming_refresh_token = "c" * 64
	rotated_refresh_token = "d" * 64
	user_id = uuid4()
	access_token = "cookie-rotated-access-token"

	def _fake_rotate_token(self, raw_token):
		assert raw_token == incoming_refresh_token
		return rotated_refresh_token, SimpleNamespace(user_id=user_id)

	def _fake_get(self, db_user_id):
		assert db_user_id == user_id
		return SimpleNamespace(id=user_id)

	def _fake_create_access_token(data, expires_delta):
		assert data == {"sub": str(user_id)}
		return access_token

	monkeypatch.setattr(RefreshTokenService, "rotate_token", _fake_rotate_token)
	monkeypatch.setattr(UserRepository, "get", _fake_get)
	monkeypatch.setattr(security, "create_access_token", _fake_create_access_token)

	client.cookies.set("refresh_token", incoming_refresh_token)
	response = client.post("/refreshtokens/rotate")

	assert response.status_code == 200
	body = response.json()
	assert body["access_token"] == access_token
	assert body["refresh_token"] == rotated_refresh_token


def test_rotate_refresh_token_returns_401_when_token_missing(client: TestClient) -> None:
	response = client.post("/refreshtokens/rotate")

	assert response.status_code == 401
	assert response.json()["detail"] == "Refresh token not provided"


def test_rotate_refresh_token_returns_401_when_user_missing(
	client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
	incoming_refresh_token = "m" * 64
	rotated_refresh_token = "n" * 64
	user_id = uuid4()

	def _fake_rotate_token(self, raw_token):
		assert raw_token == incoming_refresh_token
		return rotated_refresh_token, SimpleNamespace(user_id=user_id)

	def _fake_get(self, db_user_id):
		assert db_user_id == user_id
		return None

	monkeypatch.setattr(RefreshTokenService, "rotate_token", _fake_rotate_token)
	monkeypatch.setattr(UserRepository, "get", _fake_get)

	response = client.post("/refreshtokens/rotate", json={"refresh_token": incoming_refresh_token})

	assert response.status_code == 401
	assert response.json()["detail"] == "User not found for this refresh token"


def test_revoke_refresh_token_returns_200_and_deletes_cookie(
	client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
	incoming_refresh_token = "r" * 64

	def _fake_revoke_token(self, raw_token):
		assert raw_token == incoming_refresh_token
		return True

	monkeypatch.setattr(RefreshTokenService, "revoke_token", _fake_revoke_token)

	response = client.post("/refreshtokens/revoke", json={"refresh_token": incoming_refresh_token})

	assert response.status_code == 200
	assert response.json()["message"] == "Refresh token revoked successfully"
	assert 'refresh_token=""' in response.headers["set-cookie"]
	assert "Max-Age=0" in response.headers["set-cookie"]


def test_revoke_refresh_token_returns_404_when_missing(
	client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
	incoming_refresh_token = "x" * 64

	def _fake_revoke_token(self, raw_token):
		assert raw_token == incoming_refresh_token
		return False

	monkeypatch.setattr(RefreshTokenService, "revoke_token", _fake_revoke_token)

	response = client.post("/refreshtokens/revoke", json={"refresh_token": incoming_refresh_token})

	assert response.status_code == 404
	assert response.json()["detail"] == "Refresh token not found"


def test_logout_user_returns_200_and_deletes_cookie(
	client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
	current_user_id = uuid4()
	incoming_refresh_token = "l" * 64
	current_user = SimpleNamespace(id=current_user_id)
	app = _build_test_app(current_user)
	test_client = TestClient(app)

	def _fake_revoke_token_for_user(self, raw_token, user_id):
		assert raw_token == incoming_refresh_token
		assert user_id == current_user_id
		return True

	monkeypatch.setattr(RefreshTokenService, "revoke_token_for_user", _fake_revoke_token_for_user)

	test_client.cookies.set("refresh_token", incoming_refresh_token)
	response = test_client.post("/refreshtokens/logout")

	assert response.status_code == 200
	assert response.json()["message"] == "Logged out successfully"
	assert 'refresh_token=""' in response.headers["set-cookie"]
	assert "Max-Age=0" in response.headers["set-cookie"]


def test_logout_user_returns_403_when_token_belongs_to_other_user(
	client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
	incoming_refresh_token = "z" * 64
	current_user_id = uuid4()
	other_user_id = uuid4()
	app = _build_test_app(SimpleNamespace(id=current_user_id))
	test_client = TestClient(app)

	def _fake_revoke_token_for_user(self, raw_token, user_id):
		assert raw_token == incoming_refresh_token
		assert user_id == current_user_id
		raise TokenForbiddenError()

	monkeypatch.setattr(RefreshTokenService, "revoke_token_for_user", _fake_revoke_token_for_user)

	response = test_client.post("/refreshtokens/logout", json={"refresh_token": incoming_refresh_token})

	assert response.status_code == 403
	assert response.json()["detail"] == "You are not allowed to revoke this refresh token"


def test_logout_user_returns_404_when_missing(
	client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
	incoming_refresh_token = "y" * 64

	def _fake_revoke_token_for_user(self, raw_token, user_id):
		assert raw_token == incoming_refresh_token
		return False

	monkeypatch.setattr(RefreshTokenService, "revoke_token_for_user", _fake_revoke_token_for_user)

	response = client.post("/refreshtokens/logout", json={"refresh_token": incoming_refresh_token})

	assert response.status_code == 404
	assert response.json()["detail"] == "Refresh token not found"


def test_revoke_all_user_tokens_returns_200_and_deletes_cookie(
	client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
	current_user_id = uuid4()
	app = _build_test_app(SimpleNamespace(id=current_user_id))
	test_client = TestClient(app)

	def _fake_revoke_all_for_user(self, user_id):
		assert user_id == current_user_id
		return 3

	monkeypatch.setattr(RefreshTokenService, "revoke_all_for_user", _fake_revoke_all_for_user)

	response = test_client.post("/refreshtokens/revoke-all")

	assert response.status_code == 200
	assert response.json()["message"] == "Revoked 3 refresh token(s)"
	assert 'refresh_token=""' in response.headers["set-cookie"]
	assert "Max-Age=0" in response.headers["set-cookie"]
