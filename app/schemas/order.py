"""Pydantic schemas for Order resource."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Allowed literals
# ---------------------------------------------------------------------------
OrderStatus = Literal["requested", "accepted", "completed", "cancelled", "disputed"]


# ---------------------------------------------------------------------------
# Base — shared fields for Create / Update / Response
# ---------------------------------------------------------------------------
class OrderBase(BaseModel):
    """Fields shared across all Order schema variants."""

    proposedPrice: int = Field(..., gt=0, description="Initial price offered by the buyer")
    notes: Optional[str] = Field(default=None, description="Extra info provided by the buyer")


# ---------------------------------------------------------------------------
# Create — what a client POSTs to create a new order request
# ---------------------------------------------------------------------------
class OrderCreate(OrderBase):
    """Payload for POST /orders."""

    listingId: UUID = Field(..., description="The ID of the service listing being ordered")


# ---------------------------------------------------------------------------
# Update — PATCH payload (all fields optional)
# ---------------------------------------------------------------------------
class OrderUpdate(BaseModel):
    """
    Payload for PATCH /orders/{id}.
    Used by sellers to accept/complete and buyers to cancel/confirm.
    """

    status: Optional[OrderStatus] = None
    agreedPrice: Optional[int] = Field(default=None, gt=0)
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Response — what the API returns
# ---------------------------------------------------------------------------
class OrderResponse(BaseModel):
    """Full order object returned by the API."""

    id: UUID
    listingId: UUID
    buyerId: UUID
    sellerId: UUID
    status: OrderStatus
    
    # Payload fields
    proposedPrice: int
    agreedPrice: Optional[int] = None
    notes: Optional[str] = None
    
    # Timestamps
    acceptedAt: Optional[datetime] = None
    sellerCompletedAt: Optional[datetime] = None
    buyerCompletedAt: Optional[datetime] = None
    createdAt: datetime
    updatedAt: datetime

    model_config = dict(from_attributes=True)
