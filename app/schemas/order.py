"""Pydantic schemas for Order resource."""

from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional
from uuid import UUID

from pydantic import Field, model_validator

from .base import BaseSchema


# ---------------------------------------------------------------------------
# Allowed literals
# ---------------------------------------------------------------------------
OrderStatus = Literal["requested", "accepted", "completed", "cancelled", "disputed"]


# ---------------------------------------------------------------------------
# Base — shared fields for Create / Update / Response
# ---------------------------------------------------------------------------
class OrderBase(BaseSchema):
    """Fields shared across all Order schema variants."""

    proposed_price: int = Field(..., gt=0, description="Initial price offered by the buyer")
    notes: Optional[str] = Field(default=None, description="Extra info provided by the buyer")


# ---------------------------------------------------------------------------
# Create — what a client POSTs to create a new order request
# ---------------------------------------------------------------------------
class OrderCreate(OrderBase):
    """Payload for POST /orders."""

    listing_id: UUID = Field(..., description="The ID of the service listing being ordered")


# ---------------------------------------------------------------------------
# Update — PATCH payload
# ---------------------------------------------------------------------------
class OrderUpdate(BaseSchema):
    """
    Payload for PATCH /orders/{id}.
    Used by sellers to accept/complete and buyers to cancel/confirm.
    """

    status: Optional[OrderStatus] = None
    agreed_price: Optional[int] = Field(default=None, gt=0)
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Response — what the API returns
# ---------------------------------------------------------------------------
class OrderResponse(BaseSchema):
    """Full order object returned by the API."""

    id: UUID
    listing_id: UUID
    buyer_id: UUID
    seller_id: UUID
    status: OrderStatus
    
    # Pricing fields
    proposed_price: int
    agreed_price: Optional[int] = None
    notes: Optional[str] = None
    
    # Timestamps
    accepted_at: Optional[datetime] = None
    seller_completed_at: Optional[datetime] = None
    buyer_completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    # Context fields (Populated via validator)
    service_name: str
    image_url: Optional[str] = None
    seller_name: str

    @model_validator(mode="before")
    @classmethod
    def map_relationships(cls, data: any) -> any:
        """Attach listing and seller context while preserving the base order fields."""
        if isinstance(data, dict):
            return data

        service_name = "Unknown Service"
        service_image = None
        seller_name = "Unknown"

        if hasattr(data, "listing") and data.listing:
            service_name = data.listing.title or "Unknown Service"
            if data.listing.media:
                service_image = data.listing.media[0].image_url

        if hasattr(data, "seller") and data.seller and data.seller.profile:
            seller_name = data.seller.profile.name or "Unknown"

        # Map ORM attributes into dict for Pydantic
        result = {k: v for k, v in data.__dict__.items() if not k.startswith('_')}
        result.update({
            "service_name": service_name,
            "image_url": service_image,
            "seller_name": seller_name,
        })
        return result


# ---------------------------------------------------------------------------
# Dashboard Responses (Seller/Buyer)
# ---------------------------------------------------------------------------
class OrderAsSellerResponse(BaseSchema):
    """
    Order response optimized for the seller's dashboard view.
    """
    id: UUID
    status: OrderStatus
    created_at: datetime
    proposed_price: int
    seller_completed_at: Optional[datetime] = None
    buyer_completed_at: Optional[datetime] = None

    # Buyer info
    buyer_name: str
    buyer_phone: Optional[str] = None

    # Service context
    service_name: str
    image_url: Optional[str] = None
    service_price: float

    @model_validator(mode="before")
    @classmethod
    def map_seller_view(cls, data: any) -> any:
        if isinstance(data, dict): return data

        buyer_name = "Unknown"
        buyer_phone = data.buyer.phone if data.buyer else None
        if data.buyer and data.buyer.profile:
            buyer_name = data.buyer.profile.name

        service_name = "Unknown Service"
        service_image = None
        service_price = 0.0
        if data.listing:
            service_name = data.listing.title
            service_price = float(data.listing.price_amount or 0)
            if data.listing.media:
                service_image = data.listing.media[0].image_url

        result = {k: v for k, v in data.__dict__.items() if not k.startswith('_')}
        result.update({
            "buyer_name": buyer_name,
            "buyer_phone": buyer_phone,
            "service_name": service_name,
            "image_url": service_image,
            "service_price": service_price,
        })
        return result


class SellerOrdersResponse(BaseSchema):
    """Wrapped response for the seller's dashboard with aggregates."""
    total_orders: int
    orders: List[OrderAsSellerResponse]


class OrderAsBuyerResponse(BaseSchema):
    """
    Order response optimized for the buyer's dashboard view.
    """
    id: UUID
    status: OrderStatus
    created_at: datetime
    agreed_price: Optional[int] = None
    seller_completed_at: Optional[datetime] = None
    buyer_completed_at: Optional[datetime] = None

    # Service context
    service_name: str
    image_url: Optional[str] = None
    service_price: float

    # Seller info
    seller_name: str
    seller_phone: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def map_buyer_view(cls, data: any) -> any:
        if isinstance(data, dict): return data

        service_name = "Unknown Service"
        service_image = None
        service_price = 0.0
        if data.listing:
            service_name = data.listing.title
            service_price = float(data.listing.price_amount or 0)
            if data.listing.media:
                service_image = data.listing.media[0].image_url

        seller_name = "Unknown"
        seller_phone = data.seller.phone if data.seller else None
        if data.seller and data.seller.profile:
            seller_name = data.seller.profile.name

        result = {k: v for k, v in data.__dict__.items() if not k.startswith('_')}
        result.update({
            "service_name": service_name,
            "image_url": service_image,
            "service_price": service_price,
            "seller_name": seller_name,
            "seller_phone": seller_phone,
        })
        return result


# ---------------------------------------------------------------------------
# OrderDetailResponse — used by PATCH and general GET
# ---------------------------------------------------------------------------
class OrderDetailResponse(BaseSchema):
    """
    Unified detailed order response including full context and contact info.
    """
    id: UUID
    status: OrderStatus
    proposed_price: int
    agreed_price: Optional[int] = None
    notes: Optional[str] = None
    
    # Timestamps
    created_at: datetime
    accepted_at: Optional[datetime] = None
    seller_completed_at: Optional[datetime] = None
    buyer_completed_at: Optional[datetime] = None
    updated_at: datetime

    # Service context
    service_name: str
    image_url: Optional[str] = None
    category_name: str
    price_type: str
    listing_price: float

    # Seller info
    seller_name: str
    seller_photo_url: Optional[str] = None
    seller_phone: Optional[str] = None

    # Buyer info
    buyer_name: str
    buyer_photo_url: Optional[str] = None
    buyer_phone: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def map_detail_relationships(cls, data: any) -> any:
        if isinstance(data, dict): return data

        # Seller
        seller_name = data.seller.profile.name if data.seller and data.seller.profile else "Unknown"
        seller_photo = data.seller.profile.photo_url if data.seller and data.seller.profile else None
        seller_phone = data.seller.phone if data.seller else None

        # Buyer
        buyer_name = data.buyer.profile.name if data.buyer and data.buyer.profile else "Unknown"
        buyer_photo = data.buyer.profile.photo_url if data.buyer and data.buyer.profile else None
        buyer_phone = data.buyer.phone if data.buyer else None

        # Listing
        service_name = "Unknown Service"
        service_image = None
        category_name = "Other"
        price_type = "fixed"
        listing_price = 0.0

        if data.listing:
            service_name = data.listing.title
            price_type = data.listing.price_type
            listing_price = float(data.listing.price_amount or 0)
            if data.listing.category:
                category_name = data.listing.category.name
            if data.listing.media:
                service_image = data.listing.media[0].image_url

        result = {k: v for k, v in data.__dict__.items() if not k.startswith('_')}
        result.update({
            "service_name": service_name,
            "image_url": service_image,
            "category_name": category_name,
            "price_type": price_type,
            "listing_price": listing_price,
            "seller_name": seller_name,
            "seller_photo_url": seller_photo,
            "seller_phone": seller_phone,
            "buyer_name": buyer_name,
            "buyer_photo_url": buyer_photo,
            "buyer_phone": buyer_phone,
        })
        return result


class OrderCancelResponse(BaseSchema):
    """Response payload for cancel-request endpoint."""
    message: str
    order_id: UUID
