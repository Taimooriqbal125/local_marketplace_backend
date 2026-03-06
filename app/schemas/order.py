"""Pydantic schemas for Order resource."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


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


# ---------------------------------------------------------------------------
# /orders/me/as-seller — what a seller sees in their dashboard
# ---------------------------------------------------------------------------
class OrderAsSellerResponse(BaseModel):
    """
    Order response for the seller's dashboard.
    Shows who is requesting their service.
    """

    id: UUID
    status: OrderStatus
    proposedPrice: int
    notes: Optional[str] = None
    createdAt: datetime

    # Buyer info (who's requesting)
    buyerName: str
    buyerPhotoUrl: Optional[str] = None

    # Service context
    serviceName: str
    categoryName: str

    @model_validator(mode="before")
    @classmethod
    def map_relationships(cls, data: any) -> any:
        """Extract buyer profile and service info."""
        if not hasattr(data, "buyer"):
            return data

        buyer_name = "Unknown"
        buyer_photo = None
        if data.buyer and data.buyer.profile:
            buyer_name = data.buyer.profile.name
            buyer_photo = data.buyer.profile.photoUrl

        service_name = "Unknown Service"
        category_name = "Other"
        if data.listing:
            service_name = data.listing.title
            if data.listing.category:
                category_name = data.listing.category.name

        return {
            "id": data.id,
            "status": data.status,
            "proposedPrice": data.proposedPrice,
            "notes": data.notes,
            "createdAt": data.createdAt,
            "buyerName": buyer_name,
            "buyerPhotoUrl": buyer_photo,
            "serviceName": service_name,
            "categoryName": category_name,
        }

    model_config = dict(from_attributes=True)


# ---------------------------------------------------------------------------
# /orders/me/as-buyer — what a buyer sees in their dashboard
# ---------------------------------------------------------------------------
class OrderAsBuyerResponse(BaseModel):
    """
    Order response for the buyer's dashboard.
    Shows who is providing the service.
    """

    id: UUID
    status: OrderStatus
    proposedPrice: int
    notes: Optional[str] = None
    createdAt: datetime

    # Seller info (who's providing)
    sellerName: str
    sellerPhotoUrl: Optional[str] = None

    # Service context
    serviceName: str
    serviceImageUrl: Optional[str] = None
    categoryName: str

    @model_validator(mode="before")
    @classmethod
    def map_relationships(cls, data: any) -> any:
        """Extract seller profile and service info."""
        if not hasattr(data, "seller"):
            return data

        seller_name = "Unknown"
        seller_photo = None
        if data.seller and data.seller.profile:
            seller_name = data.seller.profile.name
            seller_photo = data.seller.profile.photoUrl

        service_name = "Unknown Service"
        service_image = None
        category_name = "Other"
        if data.listing:
            service_name = data.listing.title
            if data.listing.category:
                category_name = data.listing.category.name
            if data.listing.media:
                service_image = data.listing.media[0].imageUrl

        return {
            "id": data.id,
            "status": data.status,
            "proposedPrice": data.proposedPrice,
            "notes": data.notes,
            "createdAt": data.createdAt,
            "sellerName": seller_name,
            "sellerPhotoUrl": seller_photo,
            "serviceName": service_name,
            "serviceImageUrl": service_image,
            "categoryName": category_name,
        }

    model_config = dict(from_attributes=True)



# ---------------------------------------------------------------------------
# /orders/{order_id} — focused detail response
# ---------------------------------------------------------------------------
class OrderDetailResponse(BaseModel):
    """
    Focused order detail response for /orders/{order_id}.
    Only essential tracking fields plus seller and service names.
    """

    id: UUID
    status: OrderStatus
    sellerCompletedAt: Optional[datetime] = None
    buyerCompletedAt: Optional[datetime] = None

    # Enriched fields
    sellerName: str
    buyerName: str
    serviceName: str

    @model_validator(mode="before")
    @classmethod
    def map_relationships(cls, data: any) -> any:
        """Extract seller name and service name from ORM relationships."""
        if not hasattr(data, "seller"):
            return data

        # Seller profile
        seller_name = "Unknown"
        if data.seller and data.seller.profile:
            seller_name = data.seller.profile.name

        # Buyer profile
        buyer_name = "Unknown"
        if data.buyer and data.buyer.profile:
            buyer_name = data.buyer.profile.name

        # Service listing
        service_name = "Unknown Service"
        if data.listing:
            service_name = data.listing.title

        return {
            "id": data.id,
            "status": data.status,
            "sellerCompletedAt": data.sellerCompletedAt,
            "buyerCompletedAt": data.buyerCompletedAt,
            "sellerName": seller_name,
            "buyerName": buyer_name,
            "serviceName": service_name,
        }

    model_config = dict(from_attributes=True)
