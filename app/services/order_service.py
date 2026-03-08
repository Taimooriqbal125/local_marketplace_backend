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
from app.services.notification_service import NotificationService
from app.models.notification import NotificationType


class OrderService:
    """Service layer for Order business logic."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = OrderRepository(db)
        self.listing_repo = ServiceListingRepository(db)
        self.notification_service = NotificationService(db)

    def _get_user_details(self, user_id: uuid.UUID):
        """Helper to fetch name, email and phone for a user."""
        profile = get_profile_by_user_id(self.db, user_id)
        if not profile:
            return "Unknown User", "N/A", "N/A"
        
        name = profile.name
        email = profile.user.email if profile.user else "N/A"
        phone = profile.user.phone if profile.user else "N/A"
        return name, email, phone

    async def create_order(self, obj_in: OrderCreate, buyer_id: uuid.UUID):
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
        order = self.repo.create(obj_in, buyer_id=buyer_id, seller_id=listing.sellerId)

        # 4. Trigger Notification for Seller
        buyer_name, buyer_email, buyer_phone = self._get_user_details(buyer_id)
        await self.notification_service.send_notification(
            user_id=listing.sellerId,
            sender_id=buyer_id,
            order_id=order.id,
            listing_id=listing.id,
            type=NotificationType.ORDER_REQUESTED,
            title="New Order Received",
            body=f"{buyer_name} has requested your service '{listing.title}'. You may contact them at {buyer_email} or {buyer_phone}."
        )

        return order

    async def get_order(self, order_id: uuid.UUID, current_user_id: uuid.UUID):
        """Fetch an order by ID, raise 404 if not found, or 403 if unauthorized."""
        order = self.repo.get(order_id)
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found",
            )
        
        # Security: Only buyer or seller (or admin in future) can see this
        if order.buyerId != current_user_id and order.sellerId != current_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to view this order",
            )
            
        return order

    async def list_seller_orders(self, user_id: uuid.UUID, status: Optional[str] = None, skip: int = 0, limit: int = 20):
        """List orders where the user is the seller (incoming requests), wrapped with total count."""
        
        # 1. Fetch the orders
        orders = self.repo.get_by_seller(user_id, status=status, skip=skip, limit=limit)
        
        # 2. Fetch the seller profile for the total count
        profile = get_profile_by_user_id(self.db, user_id)
        total_orders = profile.sellerCompletedOrdersCount if profile else 0
        
        # 3. Return wrapped response
        return {
            "totalOrders": total_orders,
            "orders": orders
        }

    async def list_buyer_orders(self, user_id: uuid.UUID, status: Optional[str] = None, skip: int = 0, limit: int = 20):
        """List orders where the user is the buyer (outgoing requests)."""
        return self.repo.get_by_buyer(user_id, status=status, skip=skip, limit=limit)

    async def update_order_status(self, order_id: uuid.UUID, obj_in: OrderUpdate, current_user_id: uuid.UUID):
        """
        Update order status with ownership/role enforcement.
        """
        order = await self.get_order(order_id, current_user_id=current_user_id)
        is_seller = order.sellerId == current_user_id
        is_buyer = order.buyerId == current_user_id

        # 1. Status transition logic
        if obj_in.status:
            # Case A: Seller accepts
            if obj_in.status == "accepted":
                if not is_seller:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Only the seller can accept an order request",
                    )
                if order.status != "requested":
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Cannot accept order in '{order.status}' status",
                    )
                updated_order = self.repo.mark_as_accepted(order, agreed_price=obj_in.agreedPrice)
                
                # Notify Buyer
                seller_name, seller_email, seller_phone = self._get_user_details(current_user_id)
                await self.notification_service.send_notification(
                    user_id=order.buyerId,
                    sender_id=current_user_id,
                    order_id=order.id,
                    type=NotificationType.ORDER_ACCEPTED,
                    title="Order Accepted",
                    body=f"Your order request has been accepted by {seller_name}. You may contact them at {seller_email} or {seller_phone}."
                )
                return updated_order

            # Case B: Completion (Buyer-first flow)
            if obj_in.status == "completed":
                if order.status != "accepted" and order.status != "completed":
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Cannot complete an order in '{order.status}' status",
                    )

                # Buyer confirms satisfaction FIRST
                if is_buyer:
                    if order.buyerCompletedAt:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="You have already confirmed this order as completed",
                        )
                    updated_order = self.repo.mark_buyer_complete(order)
                    
                    # Notify Seller
                    buyer_name, _, _ = self._get_user_details(current_user_id)
                    await self.notification_service.send_notification(
                        user_id=order.sellerId,
                        sender_id=current_user_id,
                        order_id=order.id,
                        type=NotificationType.BUYER_MARKED_COMPLETED,
                        title="Buyer Confirmed Completion",
                        body=f"{buyer_name} has marked the order as completed. Please finalize it."
                    )
                    return updated_order
                
                # Seller finalizes AFTER buyer confirmation
                if is_seller:
                    if not order.buyerCompletedAt:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Please request the buyer to confirm completion first",
                        )
                    if order.sellerCompletedAt:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="You have already marked this order as completed",
                        )
                    result = self.repo.mark_seller_complete(order)
                    # Increment seller completed order count
                    increment_seller_orders_count(self.db, order.sellerId)
                    
                    # Notify Buyer
                    seller_name, _, _ = self._get_user_details(current_user_id)
                    await self.notification_service.send_notification(
                        user_id=order.buyerId,
                        sender_id=current_user_id,
                        order_id=order.id,
                        type=NotificationType.ORDER_COMPLETED,
                        title="Order Finalized",
                        body=f"{seller_name} has finalized the order. We’d appreciate it if you could leave a review."
                    )
                    return result

                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized role")

            # Case C: Cancellation
            elif obj_in.status == "cancelled":
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
                
                updated_order = self.repo.update(order, obj_in)
                
                # Notify the other party
                target_user_id = order.sellerId if is_buyer else order.buyerId
                canceller_name, _, _ = self._get_user_details(current_user_id)
                await self.notification_service.send_notification(
                    user_id=target_user_id,
                    sender_id=current_user_id,
                    order_id=order.id,
                    type=NotificationType.ORDER_CANCELLED,
                    title="Order Cancelled",
                    body=f"{canceller_name} has cancelled the order. You may try placing another request later."
                )
                return updated_order

        return self.repo.update(order, obj_in)

    # Note: Notification deletion is handled in NotificationService and its own routes.
    # Removed incorrect implementation here to avoid repository confusion.
