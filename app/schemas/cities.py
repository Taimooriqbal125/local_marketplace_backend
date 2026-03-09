from __future__ import annotations
import uuid
from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field, field_validator, model_validator

import re

SLUG_REGEX = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

class CityBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    country: str = Field(..., min_length=2, max_length=100)
    centerPoint: str | None = Field(
        default=None, 
        max_length=50, 
        description="Default geographic center (lat,lng) for searches in this city."
    )
    isActive: bool = Field(default=True)
    slug: str | None = Field(default=None, min_length=2, max_length=120)

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
    POST /cities
    Admin creates cities by providing name and country. 
    Slug is auto-generated if omitted.
    """
    pass

class CityUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    country: str | None = Field(default=None, min_length=2, max_length=100)
    centerPoint: str | None = Field(default=None, max_length=50)
    isActive: bool | None = Field(default=None)
    slug: str | None = Field(default=None, min_length=2, max_length=120)

    @field_validator("slug")
    @classmethod
    def slug_validate(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip().lower()
        v = re.sub(r"[^a-z0-9]", "-", v)
        v = re.sub(r"-+", "-", v)
        v = v.strip("-")
        if not SLUG_REGEX.match(v):
            raise ValueError("slug must be lowercase and URL-friendly")
        return v

class CityOut(BaseModel):
    id: uuid.UUID
    name: str
    country: str
    slug: str
    isActive: bool
    centerPoint: str | None = None

    model_config = dict(from_attributes=True)
