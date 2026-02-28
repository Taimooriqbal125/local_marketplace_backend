from __future__ import annotations

import re
from typing import Optional

from pydantic import BaseModel, Field, field_validator

# NOTE:
# - This schema validates input/output for Category endpoints.
# - Uniqueness (slug unique, parent_id+name unique) DB level pe enforce hoti hai.
# - parent_id optional hai (root category ke liye None).


SLUG_REGEX = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class CategoryBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    slug: str = Field(..., min_length=2, max_length=150)
    sort_order: int = Field(default=0, ge=0)
    is_active: bool = Field(default=True)
    parent_id: int | None = Field(default=None)

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
        v = v.strip().lower()
        if not SLUG_REGEX.match(v):
            raise ValueError(
                "slug must be lowercase and URL-friendly (e.g. 'home-services', no spaces/underscores)"
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
    parent_id: int | None = Field(default=None)

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
        if not SLUG_REGEX.match(v):
            raise ValueError(
                "slug must be lowercase and URL-friendly (e.g. 'home-services', no spaces/underscores)"
            )
        return v


class CategoryOut(CategoryBase):
    """
    Response model
    """
    id: int

    model_config = dict(from_attributes=True)  # Pydantic v2: SQLAlchemy -> Pydantic


# Optional: tree response (agar tum categories ko nested show karna chaho)
class CategoryTreeOut(CategoryOut):
    children: list["CategoryTreeOut"] = Field(default_factory=list)

    model_config = dict(from_attributes=True)