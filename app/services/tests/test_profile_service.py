"""
Unit tests for Profile Service.
Focuses on profile lifecycle, photo management, and location metadata.
"""

import uuid
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock, patch

import pytest
from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.services.profile_service import (
    ProfileService,
    ProfileNotFoundError,
    UserNotFoundError,
    ProfileConflictError
)
from app.schemas.profile import ProfileCreate, ProfileUpdate


class MockProfile:
    """Mock Profile database model."""
    def __init__(self, **kwargs):
        self.id = kwargs.get("id", uuid.uuid4())
        self.userId = kwargs.get("userId", uuid.uuid4())
        self.name = kwargs.get("name", "Test User")
        self.photo_url = kwargs.get("photo_url", None)
        self.cloudinary_public_id = kwargs.get("cloudinary_public_id", None)
        # Add any other fields dynamically
        for key, value in kwargs.items():
            setattr(self, key, value)


@pytest.fixture
def db_session():
    return MagicMock(spec=Session)


@pytest.fixture
def profile_service(db_session):
    """Provides a ProfileService instance with mocked repositories."""
    service = ProfileService(db_session)
    service.repo = MagicMock()
    service.user_repo = MagicMock()
    return service


# ── CREATE Tests ──────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_create_profile_success(profile_service):
    """Test successful profile creation without an image."""
    # Arrange
    user_id = uuid.uuid4()
    profile_data = ProfileCreate(user_id=user_id, name="New User")
    
    profile_service.user_repo.get.return_value = MagicMock(id=user_id)
    profile_service.repo.get_by_user_id.return_value = None
    profile_service.repo.create.return_value = MockProfile(userId=user_id, name="New User")

    # Act
    result = await profile_service.create_profile(profile_data)

    # Assert
    assert result.userId == user_id
    assert result.name == "New User"
    profile_service.repo.create.assert_called_once()


@pytest.mark.anyio
async def test_create_profile_with_image(profile_service):
    """Test profile creation with an accompanying image upload."""
    # Arrange
    user_id = uuid.uuid4()
    profile_data = ProfileCreate(user_id=user_id, name="Photo User")
    file_mock = MagicMock(spec=UploadFile)
    
    profile_service.user_repo.get.return_value = MagicMock(id=user_id)
    profile_service.repo.get_by_user_id.return_value = None
    
    upload_result = {"url": "http://img.com/p.jpg", "public_id": "p_123"}
    
    with patch("app.services.profile_service.cloudinary_service", new_callable=AsyncMock) as mock_cloud:
        mock_cloud.upload_image.return_value = upload_result
        
        # Act
        await profile_service.create_profile(profile_data, file=file_mock)

        # Assert
        assert profile_data.photo_url == upload_result["url"]
        assert profile_data.cloudinary_public_id == upload_result["public_id"]
        mock_cloud.upload_image.assert_called_once()


@pytest.mark.anyio
async def test_create_profile_user_not_found(profile_service):
    """Test that creating a profile for a non-existent user raises UserNotFoundError."""
    # Arrange
    profile_service.user_repo.get.return_value = None
    
    # Act & Assert
    with pytest.raises(UserNotFoundError):
        await profile_service.create_profile(ProfileCreate(user_id=uuid.uuid4(), name="No User"))


# ── FETCH Tests ───────────────────────────────────────────────────────────

def test_get_profile_success(profile_service):
    """Test fetching a profile by user ID successfully."""
    # Arrange
    user_id = uuid.uuid4()
    mock_profile = MockProfile(userId=user_id)
    profile_service.repo.get_by_user_id.return_value = mock_profile

    # Act
    result = profile_service.get_profile(user_id)

    # Assert
    assert result.userId == user_id
    profile_service.repo.get_by_user_id.assert_called_once_with(user_id)


def test_get_profile_not_found(profile_service):
    """Test fetching a non-existent profile raises ProfileNotFoundError."""
    # Arrange
    profile_service.repo.get_by_user_id.return_value = None

    # Act & Assert
    with pytest.raises(ProfileNotFoundError):
        profile_service.get_profile(uuid.uuid4())


# ── UPDATE Tests ──────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_update_profile_success(profile_service):
    """Test updating profile metadata successfully."""
    # Arrange
    user_id = uuid.uuid4()
    mock_profile = MockProfile(userId=user_id)
    profile_service.repo.get_by_user_id.return_value = mock_profile
    
    update_data = ProfileUpdate(name="Updated Name")
    
    # Act
    await profile_service.update_profile(user_id, update_data)

    # Assert
    profile_service.repo.update.assert_called_once()


@pytest.mark.anyio
async def test_update_profile_with_image_replacement(profile_service):
    """Test that updating an image deletes the old one from Cloudinary."""
    # Arrange
    user_id = uuid.uuid4()
    old_public_id = "old_123"
    mock_profile = MockProfile(userId=user_id, cloudinary_public_id=old_public_id)
    profile_service.repo.get_by_user_id.return_value = mock_profile
    
    file_mock = MagicMock(spec=UploadFile)
    update_data = ProfileUpdate()
    
    with patch("app.services.profile_service.cloudinary_service", new_callable=AsyncMock) as mock_cloud:
        mock_cloud.upload_image.return_value = {"url": "new.jpg", "public_id": "new_123"}
        
        # Act
        await profile_service.update_profile(user_id, update_data, file=file_mock)

        # Assert
        mock_cloud.delete_image.assert_called_once_with(old_public_id)
        mock_cloud.upload_image.assert_called_once()


# ── DELETE Tests ──────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_delete_profile_success(profile_service):
    """Test deleting a profile and its cloud assets."""
    # Arrange
    user_id = uuid.uuid4()
    public_id = "p_123"
    mock_profile = MockProfile(userId=user_id, cloudinary_public_id=public_id)
    profile_service.repo.get_by_user_id.return_value = mock_profile

    with patch("app.services.profile_service.cloudinary_service", new_callable=AsyncMock) as mock_cloud:
        # Act
        await profile_service.delete_profile(user_id)

        # Assert
        mock_cloud.delete_image.assert_called_once_with(public_id)
        profile_service.repo.delete.assert_called_once_with(mock_profile)
