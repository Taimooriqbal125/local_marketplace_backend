"""
Unit tests for ListingMedia Service.
Focuses on business logic, permissions, and Cloudinary integration while mocking IO.
"""

import uuid
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock, patch

import pytest
from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.services.listing_media_service import (
    ListingMediaService,
    MediaNotFoundError,
    ListingNotFoundError,
    ListingForbiddenError
)
from app.schemas.listing_media import ListingMediaCreate, ListingMediaUpdate


class MockListing:
    """Mock ServiceListing database model."""
    def __init__(self, **kwargs):
        self.id = kwargs.get("id", uuid.uuid4())
        self.sellerId = kwargs.get("sellerId", uuid.uuid4())
        for k, v in kwargs.items():
            setattr(self, k, v)


class MockMedia:
    """
    Mock ListingMedia database model.
    Includes snake_case attributes for Pydantic mapping if needed, 
    but relies on BaseSchema's alias_generator for camelCase mapping.
    """
    def __init__(self, **kwargs):
        self.id = kwargs.get("id", uuid.uuid4())
        self.listingId = kwargs.get("listingId", uuid.uuid4())
        self.imageUrl = kwargs.get("imageUrl", "https://cloudinary.com/test.jpg")
        self.cloudinaryPublicId = kwargs.get("cloudinaryPublicId", "public_id_123")
        self.sortOrder = kwargs.get("sortOrder", 0)
        self.created_at = kwargs.get("created_at", datetime.now())
        # Manual attribute setting for any extra fields
        for k, v in kwargs.items():
            setattr(self, k, v)


@pytest.fixture
def db_session():
    return MagicMock(spec=Session)


@pytest.fixture
def media_service(db_session):
    """Provides a ListingMediaService instance with mocked repositories."""
    service = ListingMediaService(db_session)
    service.repo = MagicMock()
    service.listing_repo = MagicMock()
    return service


# ── GET Tests ─────────────────────────────────────────────────────────────

def test_get_media_success(media_service):
    """Test fetching a media record successfully."""
    # Arrange
    media_id = uuid.uuid4()
    mock_media = MockMedia(id=media_id)
    media_service.repo.get.return_value = mock_media

    # Act
    result = media_service.get_media(media_id)

    # Assert
    assert result.id == media_id
    media_service.repo.get.assert_called_once_with(media_id)


def test_get_media_not_found(media_service):
    """Test fetching a non-existent media record raises MediaNotFoundError."""
    # Arrange
    media_id = uuid.uuid4()
    media_service.repo.get.return_value = None

    # Act & Assert
    with pytest.raises(MediaNotFoundError):
        media_service.get_media(media_id)


# ── PERMISSION Tests ──────────────────────────────────────────────────────

def test_ensure_permissions_success(media_service):
    """Test that owner of a listing has permission."""
    # Arrange
    listing_id = uuid.uuid4()
    seller_id = uuid.uuid4()
    media_service.listing_repo.get.return_value = MockListing(id=listing_id, sellerId=seller_id)

    # Act & Assert (Should not raise)
    media_service._ensure_listing_permissions(listing_id, seller_id)


def test_ensure_permissions_listing_not_found(media_service):
    """Test that missing listing raises ListingNotFoundError."""
    # Arrange
    listing_id = uuid.uuid4()
    media_service.listing_repo.get.return_value = None

    # Act & Assert
    with pytest.raises(ListingNotFoundError):
        media_service._ensure_listing_permissions(listing_id, uuid.uuid4())


def test_ensure_permissions_forbidden(media_service):
    """Test that non-owner user is forbidden from modifying media."""
    # Arrange
    listing_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    other_user_id = uuid.uuid4()
    media_service.listing_repo.get.return_value = MockListing(id=listing_id, sellerId=owner_id)

    # Act & Assert
    with pytest.raises(ListingForbiddenError):
        media_service._ensure_listing_permissions(listing_id, other_user_id)


def test_ensure_permissions_admin_override(media_service):
    """Test that admin can bypass ownership checks."""
    # Arrange
    listing_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    admin_id = uuid.uuid4()
    media_service.listing_repo.get.return_value = MockListing(id=listing_id, sellerId=owner_id)

    # Act & Assert (Should not raise)
    media_service._ensure_listing_permissions(listing_id, admin_id, is_admin=True)


# ── UPLOAD Tests ──────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_upload_and_add_media_success(media_service):
    """Test successful image upload and database record creation."""
    # Arrange
    listing_id = uuid.uuid4()
    seller_id = uuid.uuid4()
    file_mock = MagicMock(spec=UploadFile)
    
    media_service.listing_repo.get.return_value = MockListing(id=listing_id, sellerId=seller_id)
    
    upload_result = {"url": "https://cdn.com/img.jpg", "public_id": "p_123"}
    
    with patch("app.services.listing_media_service.cloudinary_service", new_callable=AsyncMock) as mock_cloudinary:
        mock_cloudinary.upload_image.return_value = upload_result
        
        media_service.repo.create.return_value = MockMedia(
            listingId=listing_id, 
            imageUrl=upload_result["url"],
            cloudinaryPublicId=upload_result["public_id"]
        )

        # Act
        result = await media_service.upload_and_add_media(
            listing_id=listing_id,
            file=file_mock,
            sort_order=1,
            current_seller_id=seller_id
        )

        # Assert
        assert result.image_url == upload_result["url"]
        assert result.cloudinary_public_id == upload_result["public_id"]
        mock_cloudinary.upload_image.assert_called_once()
        media_service.repo.create.assert_called_once()


# ── UPDATE Tests ──────────────────────────────────────────────────────────

def test_update_media_success(media_service):
    """Test updating media metadata (like sort order) successfully."""
    # Arrange
    media_id = uuid.uuid4()
    listing_id = uuid.uuid4()
    seller_id = uuid.uuid4()
    
    obj_in = ListingMediaUpdate(sort_order=5)
    mock_media = MockMedia(id=media_id, listingId=listing_id)
    
    media_service.repo.get.return_value = mock_media
    media_service.listing_repo.get.return_value = MockListing(id=listing_id, sellerId=seller_id)
    media_service.repo.update.return_value = MockMedia(id=media_id, listingId=listing_id, sortOrder=5)

    # Act
    result = media_service.update_media(media_id, obj_in, seller_id)

    # Assert
    assert result.sort_order == 5
    media_service.repo.update.assert_called_once()


# ── DELETE Tests ──────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_delete_media_success(media_service):
    """Test successful deletion of a media record and its Cloudinary asset."""
    # Arrange
    media_id = uuid.uuid4()
    listing_id = uuid.uuid4()
    seller_id = uuid.uuid4()
    
    mock_media = MockMedia(id=media_id, listingId=listing_id, cloudinaryPublicId="pub_id")
    media_service.repo.get.return_value = mock_media
    media_service.listing_repo.get.return_value = MockListing(id=listing_id, sellerId=seller_id)

    with patch("app.services.listing_media_service.cloudinary_service", new_callable=AsyncMock) as mock_cloudinary:
        # Act
        await media_service.delete_media(media_id, seller_id)

        # Assert
        mock_cloudinary.delete_image.assert_called_once_with("pub_id")
        media_service.repo.delete.assert_called_once_with(mock_media)
