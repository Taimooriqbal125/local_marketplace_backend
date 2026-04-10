"""Pydantic schemas for City resource."""

from __future__ import annotations

import re
from uuid import UUID
from typing import Optional, Any

from pydantic import Field, field_validator, model_validator

from .base import BaseSchema


SLUG_REGEX = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class CityBase(BaseSchema):
    """
    Fields shared across all City schema variants.
    """
    name: str = Field(..., min_length=2, max_length=100)
    country: str = Field(..., min_length=2, max_length=100)
    center_point: Optional[str] = Field(
        default=None, 
        max_length=50, 
        description="Default geographic center (lat,lng) for searches in this city."
    )
    is_active: bool = Field(default=True)
    slug: Optional[str] = Field(default=None, min_length=2, max_length=120)

    @model_validator(mode="before")
    @classmethod
    def generate_slug(cls, data: Any) -> Any:
        # If input is already a model instance or not a dict, skip
        if not isinstance(data, dict):
            return data
            
        # If slug is not provided, generate from name
        name = data.get("name")
        slug = data.get("slug")
        
        if not slug and name:
            slug = name.strip().lower()
            slug = re.sub(r"[^a-z0-9]", "-", slug)
            slug = re.sub(r"-+", "-", slug)
            slug = slug.strip("-")
            data["slug"] = slug
        
        elif slug:
            slug = slug.strip().lower()
            slug = re.sub(r"[^a-z0-9]", "-", slug)
            slug = re.sub(r"-+", "-", slug)
            slug = slug.strip("-")
            data["slug"] = slug
            
        return data

    @field_validator("slug")
    @classmethod
    def slug_validate(cls, v: str) -> str:
        if not v or not SLUG_REGEX.match(v):
            raise ValueError("slug must be lowercase and URL-friendly (e.g. 'karachi')")
        return v


class CityCreate(CityBase):
    """
    Payload for POST /cities.
    Slug is automatically generated from name if not provided.
    """
    pass


class CityUpdate(BaseSchema):
    """
    Payload for PATCH /cities/{id}.
    """
    name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    country: Optional[str] = Field(default=None, min_length=2, max_length=100)
    center_point: Optional[str] = Field(default=None, max_length=50)
    is_active: Optional[bool] = None
    slug: Optional[str] = None

    @field_validator("slug")
    @classmethod
    def slug_validate(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip().lower()
        v = re.sub(r"[^a-z0-9]", "-", v)
        v = re.sub(r"-+", "-", v)
        v = v.strip("-")
        if not SLUG_REGEX.match(v):
            raise ValueError("slug must be lowercase and URL-friendly")
        return v


class CityOut(BaseSchema):
    """
    Output model for City details.
    """
    id: UUID
    name: str
    country: str
    slug: str
    is_active: bool
    center_point: Optional[str] = None
