from __future__ import annotations
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator

SLUG_REGEX = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"

class CityBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    country: str = Field(..., min_length=2, max_length=100)
    centerPoint: str | None = Field(default=None, max_length=50, description="lat,lng as string")
    isActive: bool = Field(default=True)
    slug: str = Field(..., min_length=2, max_length=120)

    @field_validator("slug")
    @classmethod
    def slug_validate(cls, v: str) -> str:
        v = v.strip().lower()
        import re
        if not re.match(SLUG_REGEX, v):
            raise ValueError("slug must be lowercase and URL-friendly (e.g. 'karachi', no spaces/underscores)")
        return v

class CityCreate(CityBase):
    pass

class CityUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    country: str | None = Field(default=None, min_length=2, max_length=100)
    centerPoint: str | None = Field(default=None, max_length=50, description="lat,lng as string")
    isActive: bool | None = Field(default=None)
    slug: str | None = Field(default=None, min_length=2, max_length=120)

    @field_validator("slug")
    @classmethod
    def slug_validate(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip().lower()
        import re
        if not re.match(SLUG_REGEX, v):
            raise ValueError("slug must be lowercase and URL-friendly (e.g. 'karachi', no spaces/underscores)")
        return v

class CityOut(BaseModel):
    id: uuid.UUID
    name: str
    country: str
    slug: str
    isActive: bool
    centerPoint: str | None = None

    model_config = dict(from_attributes=True)
