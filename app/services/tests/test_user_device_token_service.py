import uuid
from types import SimpleNamespace
from datetime import datetime, timezone, timedelta

import pytest

from app.services.user_device_token_service import (
	UserDeviceTokenService,
	UserDeviceTokenNotFoundError,
)


class FakeRepo:
	def __init__(self):
		self.created = None
		self.updated = None
		self.deleted = None
		self.last_used_updated = None
		self.deactivated = None
		self.deleted_inactive_before = None

	def get_by_token(self, token):
		return getattr(self, "_get_by_token_return", None)

	def create(self, user_id, obj_in):
		self.created = (user_id, obj_in)
		return SimpleNamespace(id=uuid.uuid4(), userId=user_id, expo_push_token=obj_in.expo_push_token)

	def update(self, db_obj, update_data):
		self.updated = (db_obj, update_data)
		return db_obj

	def get_all_by_user(self, user_id, active_only=True):
		return getattr(self, "_get_all_return", [])

	def deactivate_token(self, expo_push_token: str) -> bool:
		self.deactivated = expo_push_token
		return getattr(self, "_deactivate_return", True)

	def get(self, token_id):
		return getattr(self, "_get_return", None)

	def delete(self, db_obj):
		self.deleted = db_obj

	def update_last_used(self, expo_push_token: str):
		self.last_used_updated = expo_push_token
		return getattr(self, "_update_last_used_return", True)

	def delete_inactive_tokens(self, before):
		self.deleted_inactive_before = before
		return getattr(self, "_delete_inactive_return", 0)


@pytest.fixture(autouse=True)
def patch_repo(monkeypatch):
	"""Patch the repository class used inside the service to a fake in-memory repo."""
	fake = FakeRepo()

	def fake_repo_ctor(db):
		return fake

	monkeypatch.setattr("app.services.user_device_token_service.UserDeviceTokenRepository", fake_repo_ctor)
	return fake


@pytest.fixture
def service(monkeypatch):
	# db argument is unused because we patched the repo constructor
	return UserDeviceTokenService(db=None)


def test_register_token_creates_when_not_exists(service, patch_repo):
	class CreateIn:
		expo_push_token = "token-123"
		device_type = "ios"
		device_name = "iPhone"

	patch_repo._get_by_token_return = None
	result = service.register_token(user_id=uuid.uuid4(), obj_in=CreateIn())
	assert result is not None
	assert patch_repo.created is not None


def test_register_token_updates_when_exists(service, patch_repo):
	existing = SimpleNamespace(id=uuid.uuid4(), userId=uuid.uuid4(), deviceType="android", deviceName=None, expo_push_token="tkn")
	patch_repo._get_by_token_return = existing

	class In:
		expo_push_token = "tkn"
		device_type = "ios"
		device_name = "My Phone"

	new_user = uuid.uuid4()
	ret = service.register_token(user_id=new_user, obj_in=In())
	# repo.update returns the same object; service should have reassigned ownership
	assert ret is existing
	assert existing.userId == new_user
	assert existing.deviceType == "ios"
	assert existing.deviceName == "My Phone"


def test_get_user_tokens_delegates(service, patch_repo):
	user = uuid.uuid4()
	patch_repo._get_all_return = [1, 2, 3]
	res = service.get_user_tokens(user, active_only=False)
	assert res == [1, 2, 3]


def test_deactivate_token(service, patch_repo):
	patch_repo._deactivate_return = False
	assert service.deactivate_token("tok") is False
	patch_repo._deactivate_return = True
	assert service.deactivate_token("tok") is True


def test_delete_token_success(service, patch_repo):
	user = uuid.uuid4()
	token = SimpleNamespace(id=uuid.uuid4(), userId=user)
	patch_repo._get_return = token
	resp = service.delete_token(token.id, user)
	assert resp == {"message": "Device token deleted successfully"}
	assert patch_repo.deleted is token


def test_delete_token_not_found_or_not_owner(service, patch_repo):
	# Not found
	patch_repo._get_return = None
	with pytest.raises(UserDeviceTokenNotFoundError):
		service.delete_token(uuid.uuid4(), uuid.uuid4())

	# Found but wrong owner
	patch_repo._get_return = SimpleNamespace(id=uuid.uuid4(), userId=uuid.uuid4())
	with pytest.raises(UserDeviceTokenNotFoundError):
		service.delete_token(patch_repo._get_return.id, uuid.uuid4())


def test_update_activity(service, patch_repo):
	patch_repo._update_last_used_return = True
	assert service.update_activity("tok") is True
	patch_repo._update_last_used_return = False
	assert service.update_activity("tok") is False


def test_cleanup_inactive_tokens_uses_retention(monkeypatch, service, patch_repo):
	# Ensure settings value is used when retention_days is None
	import app.core.config as config

	monkeypatch.setattr(config, "settings", SimpleNamespace(DELETE_INACTIVE_DEVICE_TOKENS_IN_DAYS=7))
	patch_repo._delete_inactive_return = 5
	res = service.cleanup_inactive_tokens()
	assert res == {"deleted_count": 5}
	assert isinstance(patch_repo.deleted_inactive_before, datetime)


def test_cleanup_inactive_tokens_with_param(monkeypatch, service, patch_repo):
	patch_repo._delete_inactive_return = 2
	res = service.cleanup_inactive_tokens(retention_days=3)
	assert res == {"deleted_count": 2}
	assert isinstance(patch_repo.deleted_inactive_before, datetime)

