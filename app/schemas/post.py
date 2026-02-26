"""
Pydantic schemas for the Post resource.
"""

from pydantic import BaseModel
from datetime import datetime
from typing import Optional

# ---------- Request Schemas ----------

class PostCreate(BaseModel):
    title: str
    content: str

class PostUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None

# ---------- Response Schemas ----------

class PostResponse(BaseModel):
    id: int
    title: str
    content: str
    owner_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
