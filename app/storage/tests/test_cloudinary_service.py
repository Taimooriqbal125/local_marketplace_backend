"""
Unit tests for Cloudinary Service.
Focuses on upload/delete orchestration, thread-pool execution, and file validation rules.
"""

import io
from unittest.mock import MagicMock, patch

import pytest
from fastapi import UploadFile, HTTPException

from app.storage.cloudinary_service import CloudinaryService


@pytest.fixture
def cloudinary_service():
    """Provides a CloudinaryService instance with mocked settings."""
    with patch("app.core.config.settings") as mock_settings:
        mock_settings.CLOUDINARY_CLOUD_NAME = "test_cloud"
        mock_settings.CLOUDINARY_API_KEY = "test_key"
        mock_settings.CLOUDINARY_API_SECRET = "test_secret"
        mock_settings.CLOUDINARY_FOLDER = "test_folder"
        return CloudinaryService()


# ── UPLOAD Tests ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("anyio_backend", ["asyncio"])
async def test_upload_image_success(cloudinary_service, anyio_backend):
    """Test successful image upload to Cloudinary."""
    # Arrange
    content = b"fake-image-data"
    file = MagicMock(spec=UploadFile)
    file.content_type = "image/jpeg"
    file.read = MagicMock(return_value=content) # read is async in FastAPI but we mock the result
    
    # We need to wrap the return_value in an awaitable for the service's await file.read()
    async def mock_read(): return content
    file.read = mock_read

    mock_upload_result = {
        "secure_url": "https://cloudinary.com/image.jpg",
        "public_id": "folder/image_id"
    }

    with patch("cloudinary.uploader.upload", return_value=mock_upload_result) as mock_upload:
        # Act
        result = await cloudinary_service.upload_image(file, folder="custom_folder")

        # Assert
        assert result["url"] == mock_upload_result["secure_url"]
        assert result["public_id"] == mock_upload_result["public_id"]
        mock_upload.assert_called_once()
        args, kwargs = mock_upload.call_args
        assert args[0] == content
        assert kwargs["folder"] == "custom_folder"


@pytest.mark.parametrize("anyio_backend", ["asyncio"])
async def test_upload_image_unsupported_type(cloudinary_service, anyio_backend):
    """Test that unsupported MIME types are rejected with 400."""
    # Arrange
    file = MagicMock(spec=UploadFile)
    file.content_type = "application/pdf"

    # Act & Assert
    with pytest.raises(HTTPException) as exc:
        await cloudinary_service.upload_image(file)
    assert exc.value.status_code == 400
    assert "Unsupported file type" in exc.value.detail


@pytest.mark.parametrize("anyio_backend", ["asyncio"])
async def test_upload_image_too_large(cloudinary_service, anyio_backend):
    """Test that files exceeding MAX_FILE_SIZE_BYTES are rejected."""
    # Arrange
    file = MagicMock(spec=UploadFile)
    file.content_type = "image/png"
    # 6MB data
    large_content = b"0" * (6 * 1024 * 1024)
    async def mock_read(): return large_content
    file.read = mock_read

    # Act & Assert
    with pytest.raises(HTTPException) as exc:
        await cloudinary_service.upload_image(file)
    assert exc.value.status_code == 400
    assert "File too large" in exc.value.detail


@pytest.mark.parametrize("anyio_backend", ["asyncio"])
async def test_upload_image_cloudinary_failure(cloudinary_service, anyio_backend):
    """Test that Cloudinary SDK errors are wrapped in 500 HTTPExceptions."""
    # Arrange
    file = MagicMock(spec=UploadFile)
    file.content_type = "image/jpeg"
    async def mock_read(): return b"data"
    file.read = mock_read

    with patch("cloudinary.uploader.upload", side_effect=Exception("API Error")):
        # Act & Assert
        with pytest.raises(HTTPException) as exc:
            await cloudinary_service.upload_image(file)
        assert exc.value.status_code == 500
        assert "Cloudinary upload failed" in exc.value.detail


# ── DELETE Tests ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("anyio_backend", ["asyncio"])
async def test_delete_image_success(cloudinary_service, anyio_backend):
    """Test successful image deletion."""
    # Arrange
    public_id = "test_id"
    with patch("cloudinary.uploader.destroy", return_value={"result": "ok"}) as mock_destroy:
        # Act
        result = await cloudinary_service.delete_image(public_id)

        # Assert
        assert result is True
        mock_destroy.assert_called_once_with(public_id, resource_type="image")


@pytest.mark.parametrize("anyio_backend", ["asyncio"])
async def test_delete_image_not_found_or_error(cloudinary_service, anyio_backend):
    """Test that deletion failures are swallowed and return False."""
    # Arrange
    with patch("cloudinary.uploader.destroy", return_value={"result": "not found"}):
        # Act
        result = await cloudinary_service.delete_image("bad_id")
        # Assert
        assert result is False

    with patch("cloudinary.uploader.destroy", side_effect=Exception("Network error")):
        # Act
        result = await cloudinary_service.delete_image("any_id")
        # Assert
        assert result is False


@pytest.mark.parametrize("anyio_backend", ["asyncio"])
async def test_delete_image_empty_id(cloudinary_service, anyio_backend):
    """Test that providing an empty public_id returns False immediately."""
    # Act
    result = await cloudinary_service.delete_image("")
    # Assert
    assert result is False
