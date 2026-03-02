"""
Order Service — encapsulates business logic for managing orders.
"""

import uuid
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.repositories.order_repo import OrderRepository
from app.repositories.service_listing_repo import ServiceListingRepository
from app.schemas.order import OrderCreate, OrderUpdate


class OrderService:
    """Service layer for Order business logic."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = OrderRepository(db)
        self.listing_repo = ServiceListingRepository(db)

    def create_order(self, obj_in: OrderCreate, buyer_id: uuid.UUID):
        """
        Create a new order request.
        Validates listing existence and prevents self-purchase.
        """
        # 1. Fetch listing to get seller identification
        listing = self.listing_repo.get(obj_in.listingId)
        if not listing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Service listing not found",
            )

        # 2. Prevent self-purchase
        if listing.sellerId == buyer_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot purchase your own service listing",
            )

        # 3. Create order record
        return self.repo.create(obj_in, buyer_id=buyer_id, seller_id=listing.sellerId)

    def get_order(self, order_id: uuid.UUID):
        """Fetch an order by ID or raise 404."""
        order = self.repo.get(order_id)
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found",
            )
        return order

    def list_my_orders(self, user_id: uuid.UUID, role: str = "buyer", skip: int = 0, limit: int = 20):
        """
        List orders where the user is either the buyer or the seller.
        """
        if role == "seller":
            return self.repo.get_by_seller(user_id, skip=skip, limit=limit)
        return self.repo.get_by_buyer(user_id, skip=skip, limit=limit)

    def update_order_status(self, order_id: uuid.UUID, obj_in: OrderUpdate, current_user_id: uuid.UUID):
        """
        Update order status with ownership/role enforcement.
        """
        order = self.get_order(order_id)

        # Role-based status transition rules
        if obj_in.status:
            # Sellers can 'accept' or 'complete'
            if obj_in.status in ["accepted", "completed"]:
                if order.sellerId != current_user_id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Only the seller can accept or complete an order",
                    )
            
            # Buyers can 'cancel' only if still 'requested'
            elif obj_in.status == "cancelled":
                is_seller = order.sellerId == current_user_id
                is_buyer = order.buyerId == current_user_id
                
                if not (is_seller or is_buyer):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="You are not authorized to cancel this order",
                    )
                
                if is_buyer and order.status != "requested":
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Buyers can only cancel an order before it is accepted",
                    )

        return self.repo.update(order, obj_in)
