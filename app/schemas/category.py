import re
import uuid
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


SLUG_REGEX = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$")


class CategoryBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    slug: str = Field(..., min_length=2, max_length=150)
    sort_order: int = Field(default=0, ge=0)
    is_active: bool = Field(default=True)
    parent_id: UUID | None = Field(default=None)

    @field_validator("name")
    @classmethod
    def name_strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name cannot be empty")
        return v

    @field_validator("slug")
    @classmethod
    def slug_validate(cls, v: str) -> str:
        # 1. Lowercase and replace spaces/underscores/dots with hyphens for uniformity
        # Senior devs often standardize on hyphens for SEO, but we'll preserve user's separators if valid.
        v = v.strip().lower()

        # 2. Replace spaces and invalid characters with hyphens
        v = re.sub(r"[^a-z0-9._-]", "-", v)

        # 3. Collapse multiple separators (e.g. "---" -> "-")
        v = re.sub(r"([._-])\1+", r"\1", v)

        # 4. Remove leading/trailing separators
        v = v.strip(" ._-")

        if not SLUG_REGEX.match(v):
            raise ValueError(
                "Final slug is invalid. Slug must be lowercase and URL-friendly. "
                "Only letters, numbers, hyphens, underscores, and dots are allowed."
            )
        return v


class CategoryCreate(CategoryBase):
    """
    POST /categories
    """
    pass


class CategoryUpdate(BaseModel):
    """
    PATCH /categories/{id}
    All fields optional.
    """
    name: str | None = Field(default=None, min_length=2, max_length=100)
    slug: str | None = Field(default=None, min_length=2, max_length=150)
    sort_order: int | None = Field(default=None, ge=0)
    is_active: bool | None = Field(default=None)
    parent_id: UUID | None = Field(default=None)

    @field_validator("name")
    @classmethod
    def name_strip(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("name cannot be empty")
        return v

    @field_validator("slug")
    @classmethod
    def slug_validate(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip().lower()
        v = re.sub(r"[^a-z0-9._-]", "-", v)
        v = re.sub(r"([._-])\1+", r"\1", v)
        v = v.strip(" ._-")

        if not SLUG_REGEX.match(v):
            raise ValueError(
                "Final slug is invalid. Slug must be lowercase and URL-friendly. "
                "Only letters, numbers, hyphens, underscores, and dots are allowed."
            )
        return v


class CategoryOut(CategoryBase):
    """
    Response model
    """
    id: UUID

    model_config = dict(from_attributes=True)  # Pydantic v2: SQLAlchemy -> Pydantic


# Optional: tree response (agar tum categories ko nested show karna chaho)
class CategoryTreeOut(CategoryOut):
    children: list["CategoryTreeOut"] = Field(default_factory=list)

    model_config = dict(from_attributes=True)