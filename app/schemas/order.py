"""Pydantic schemas for Order resource."""

from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional
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
    createdAt: datetime

    # Buyer info (who's requesting)
    buyerName: str
    buyerPhotoUrl: Optional[str] = None

    # Service context
    serviceName: str
    imageUrl: Optional[str] = None
    categoryName: str

    @model_validator(mode="before")
    @classmethod
    def map_relationships(cls, data: any) -> any:
        """Extract buyer profile, seller profile (for count), and service info."""
        if not hasattr(data, "buyer") or not hasattr(data, "seller"):
            return data

        buyer_name = "Unknown"
        buyer_photo = None
        if data.buyer and data.buyer.profile:
            buyer_name = data.buyer.profile.name
            buyer_photo = data.buyer.profile.photoUrl


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
            "createdAt": data.createdAt,
            "buyerName": buyer_name,
            "buyerPhotoUrl": buyer_photo,
            "serviceName": service_name,
            "imageUrl": service_image,
            "categoryName": category_name,
        }

    model_config = dict(from_attributes=True)


class SellerOrdersResponse(BaseModel):
    """
    Wrapped response for the seller's dashboard.
    Includes total completed orders count for the seller.
    """
    totalOrders: int
    orders: List[OrderAsSellerResponse]

    model_config = dict(from_attributes=True)


# ---------------------------------------------------------------------------
# /orders/me/as-buyer — what a buyer sees in their dashboard
# ---------------------------------------------------------------------------
class OrderAsBuyerResponse(BaseModel):
    """
    Order response for the buyer's dashboard.
    Shows the services ordered by the user.
    """

    id: UUID
    createdAt: datetime

    # Service context
    serviceName: str
    imageUrl: Optional[str] = None
    categoryName: str

    # Seller info
    sellerName: str
    sellerPhotoUrl: Optional[str] = None
    sellerPhone: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def map_relationships(cls, data: any) -> any:
        """Extract service info and seller contact details."""
        service_name = "Unknown Service"
        service_image = None
        category_name = "Other"
        
        if data.listing:
            service_name = data.listing.title
            if data.listing.category:
                category_name = data.listing.category.name
            if data.listing.media:
                service_image = data.listing.media[0].imageUrl

        seller_name = "Unknown"
        seller_photo = None
        seller_phone = None
        if data.seller:
            seller_phone = data.seller.phone
            if data.seller.profile:
                seller_name = data.seller.profile.name
                seller_photo = data.seller.profile.photoUrl

        return {
            "id": data.id,
            "createdAt": data.createdAt,
            "serviceName": service_name,
            "imageUrl": service_image,
            "categoryName": category_name,
            "sellerName": seller_name,
            "sellerPhotoUrl": seller_photo,
            "sellerPhone": seller_phone,
        }

    model_config = dict(from_attributes=True)



# ---------------------------------------------------------------------------
# OrderDetailResponse — used by PATCH and general GET
# ---------------------------------------------------------------------------
class OrderDetailResponse(BaseModel):
    """
    Unified detailed order response for both buyer and seller.
    Includes full service context, pricing, and contact info.
    """

    id: UUID
    status: OrderStatus
    proposedPrice: int
    agreedPrice: Optional[int] = None
    notes: Optional[str] = None
    
    # Timestamps
    createdAt: datetime
    acceptedAt: Optional[datetime] = None
    sellerCompletedAt: Optional[datetime] = None
    buyerCompletedAt: Optional[datetime] = None
    updatedAt: datetime

    # Service context
    serviceName: str
    imageUrl: Optional[str] = None
    categoryName: str
    priceType: str
    listingPrice: float  # The price at the time of listing

    # Seller info
    sellerName: str
    sellerPhotoUrl: Optional[str] = None
    sellerPhone: Optional[str] = None

    # Buyer info
    buyerName: str
    buyerPhotoUrl: Optional[str] = None
    buyerPhone: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def map_relationships(cls, data: any) -> any:
        """Map listing, seller, and buyer data into a unified detail view."""
        if not hasattr(data, "seller") or not hasattr(data, "buyer") or not hasattr(data, "listing"):
            return data

        # Seller mapping
        seller_name = "Unknown"
        seller_photo = None
        seller_phone = data.seller.phone if data.seller else None
        if data.seller and data.seller.profile:
            seller_name = data.seller.profile.name
            seller_photo = data.seller.profile.photoUrl

        # Buyer mapping
        buyer_name = "Unknown"
        buyer_photo = None
        buyer_phone = data.buyer.phone if data.buyer else None
        if data.buyer and data.buyer.profile:
            buyer_name = data.buyer.profile.name
            buyer_photo = data.buyer.profile.photoUrl

        # Listing mapping
        service_name = "Unknown Service"
        service_image = None
        category_name = "Other"
        price_type = "fixed"
        listing_price = 0.0

        if data.listing:
            service_name = data.listing.title
            price_type = data.listing.priceType
            listing_price = float(data.listing.priceAmount or 0)
            if data.listing.category:
                category_name = data.listing.category.name
            if data.listing.media:
                service_image = data.listing.media[0].imageUrl

        return {
            "id": data.id,
            "status": data.status,
            "proposedPrice": data.proposedPrice,
            "agreedPrice": data.agreedPrice,
            "notes": data.notes,
            "createdAt": data.createdAt,
            "acceptedAt": data.acceptedAt,
            "sellerCompletedAt": data.sellerCompletedAt,
            "buyerCompletedAt": data.buyerCompletedAt,
            "updatedAt": data.updatedAt,
            "serviceName": service_name,
            "imageUrl": service_image,
            "categoryName": category_name,
            "priceType": price_type,
            "listingPrice": listing_price,
            "sellerName": seller_name,
            "sellerPhotoUrl": seller_photo,
            "sellerPhone": seller_phone,
            "buyerName": buyer_name,
            "buyerPhotoUrl": buyer_photo,
            "buyerPhone": buyer_phone,
        }

    model_config = dict(from_attributes=True)
