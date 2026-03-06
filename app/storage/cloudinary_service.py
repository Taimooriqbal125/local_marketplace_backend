# app/storage/cloudinary_service.py
"""
Cloudinary Service — centralised wrapper for all Cloudinary operations.

Usage (anywhere in the app):
    from app.storage.cloudinary_service import cloudinary_service

    upload_result = await cloudinary_service.upload_image(file, folder="listings")
    await cloudinary_service.delete_image(upload_result["public_id"])
"""

import asyncio
from typing import Optional

import cloudinary
import cloudinary.uploader
from fastapi import HTTPException, UploadFile, status

from app.core.config import settings

# ── Allowed MIME types ────────────────────────────────────────────────────────
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB


class CloudinaryService:
    """
    Async-friendly wrapper around the synchronous Cloudinary SDK.
    All blocking SDK calls are executed in a thread-pool via asyncio.to_thread
    so they never block the event loop.
    """

    def __init__(self) -> None:
        cloudinary.config(
            cloud_name=settings.CLOUDINARY_CLOUD_NAME,
            api_key=settings.CLOUDINARY_API_KEY,
            api_secret=settings.CLOUDINARY_API_SECRET,
            secure=True,
        )

    # ── Upload ────────────────────────────────────────────────────────────────

    async def upload_image(
        self,
        file: UploadFile,
        folder: Optional[str] = None,
        public_id: Optional[str] = None,
        transformation: Optional[dict] = None,
    ) -> dict:
        """
        Upload an image file to Cloudinary.

        Parameters
        ----------
        file           : FastAPI UploadFile received from the request.
        folder         : Cloudinary folder to store the image in.
                         Falls back to CLOUDINARY_FOLDER from settings.
        public_id      : Optional custom public_id (filename without extension).
                         Cloudinary auto-generates one when omitted.
        transformation : Optional Cloudinary transformation dict, e.g.
                         {"width": 800, "crop": "limit", "quality": "auto"}.

        Returns
        -------
        dict with keys:
            "url"       - HTTPS URL of the uploaded image
            "public_id" - Cloudinary public_id (needed for future deletion)
        """
        self._validate_image(file)

        content = await file.read()
        self._validate_size(content)

        upload_options: dict = {
            "folder": folder or settings.CLOUDINARY_FOLDER,
            "overwrite": True,
            "resource_type": "image",
        }
        if public_id:
            upload_options["public_id"] = public_id
        if transformation:
            upload_options["transformation"] = transformation

        try:
            result = await asyncio.to_thread(
                cloudinary.uploader.upload,
                content,
                **upload_options,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Cloudinary upload failed: {exc}",
            ) from exc

        return {
            "url": result["secure_url"],
            "public_id": result["public_id"],
        }

    # ── Delete ────────────────────────────────────────────────────────────────

    async def delete_image(self, public_id: str) -> bool:
        """
        Delete an image from Cloudinary by its public_id.

        Returns True if deleted successfully, False otherwise.
        Failures are silently swallowed so a missing asset never breaks
        a delete operation.
        """
        if not public_id:
            return False
        try:
            result = await asyncio.to_thread(
                cloudinary.uploader.destroy,
                public_id,
                resource_type="image",
            )
            return result.get("result") == "ok"
        except Exception:
            return False

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _validate_image(file: UploadFile) -> None:
        if file.content_type not in ALLOWED_IMAGE_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Unsupported file type '{file.content_type}'. "
                    f"Allowed types: {', '.join(ALLOWED_IMAGE_TYPES)}"
                ),
            )

    @staticmethod
    def _validate_size(content: bytes) -> None:
        if len(content) > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File too large. Maximum allowed size is 5 MB.",
            )


# ── Singleton ─────────────────────────────────────────────────────────────────
# Import this instance throughout the app — avoids re-initialising on every request.
cloudinary_service = CloudinaryService()
