import re
from typing import Optional
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from .base import BaseSchema


SLUG_REGEX = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$")


class CategoryBase(BaseSchema):
    """
    Base attributes for a Category.
    """
    name: str = Field(
        ..., 
        min_length=2, 
        max_length=100,
        description="Display name of the category"
    )
    slug: str = Field(
        ..., 
        min_length=2, 
        max_length=150,
        description="URL-friendly identifier"
    )
    sort_order: int = Field(
        default=0, 
        ge=0,
        description="Order in which categories are displayed"
    )
    is_active: bool = Field(
        default=True,
        description="Whether the category is available for use"
    )
    parent_id: Optional[UUID] = Field(
        default=None,
        description="ID of the parent category, if any"
    )

    @model_validator(mode="before")
    @classmethod
    def generate_slug(cls, data: any) -> any:
        """
        Automatically generates a slug from the name if not provided.
        """
        if not isinstance(data, dict):
            return data

        name = data.get("name")
        slug = data.get("slug")

        if not slug and name:
            generated = name.strip().lower()
            generated = re.sub(r"[^a-z0-9]", "-", generated)
            generated = re.sub(r"-+", "-", generated)
            data["slug"] = generated.strip("-")
            
        return data

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
        """
        Validates and standardizes the slug format.
        """
        v = v.strip().lower()
        # Replace spaces and invalid characters with hyphens
        v = re.sub(r"[^a-z0-9._-]", "-", v)
        # Collapse multiple separators (e.g. "---" -> "-")
        v = re.sub(r"([._-])\1+", r"\1", v)
        # Remove leading/trailing separators
        v = v.strip(" ._-")

        if not SLUG_REGEX.match(v):
            raise ValueError(
                "Final slug is invalid. Slug must be lowercase and URL-friendly. "
                "Only letters, numbers, hyphens, underscores, and dots are allowed."
            )
        return v


class CategoryCreate(CategoryBase):
    """
    Schema for creating a new Category.
    """
    pass


class CategoryUpdate(BaseSchema):
    """
    Schema for updating an existing Category. 
    All fields are optional.
    """
    name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    slug: Optional[str] = Field(default=None, min_length=2, max_length=150)
    sort_order: Optional[int] = Field(default=None, ge=0)
    is_active: Optional[bool] = Field(default=None)
    parent_id: Optional[UUID] = Field(default=None)

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
            raise ValueError("Invalid slug format.")
        return v


from datetime import datetime


class CategoryOut(CategoryBase):
    """
    Full Category response including ID and timestamps.
    """
    id: UUID
    created_at: datetime
    updated_at: datetime


class CategoryParentOut(BaseSchema):
    """
    Response model for parent categories, excluding internal IDs and parent links.
    """
    id: UUID
    name: str
    slug: str
    sort_order: int
    is_active: bool


class CategoryTreeOut(CategoryOut):
    """
    Recursive Category response including children.
    """
    children: list["CategoryTreeOut"] = Field(default_factory=list)