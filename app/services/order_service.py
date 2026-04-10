"""
Order Service — encapsulates business logic for managing orders.
"""

import uuid
from typing import List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.repositories.order_repo import OrderRepository
from app.repositories.service_listing_repo import ServiceListingRepository
from app.repositories.profile_repo import ProfileRepository
from app.schemas.order import OrderCreate, OrderUpdate
from app.services.notification_service import NotificationService
from app.models.notification import NotificationType
from app.models.order import Order


class ListingNotFoundError(HTTPException):
    def __init__(self, detail: str = "Service listing not found"):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


class OrderNotFoundError(HTTPException):
    def __init__(self, detail: str = "Order not found"):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


class OrderForbiddenError(HTTPException):
    def __init__(self, detail: str = "You are not authorized to view or modify this order"):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


class OrderStateError(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


class OrderService:
    """Service layer for Order business logic."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = OrderRepository(db)
        self.listing_repo = ServiceListingRepository(db)
        self.notification_service = NotificationService(db)

    def _get_user_details(self, user_id: uuid.UUID) -> Tuple[str, str, str]:
        """Helper to fetch name, email and phone for a user."""
        profile = ProfileRepository(self.db).get_by_user_id(user_id)
        if not profile:
            return "Unknown User", "N/A", "N/A"
        
        name = profile.name
        email = profile.user.email if profile.user else "N/A"
        phone = profile.user.phone if profile.user else "N/A"
        return name, email, phone

    async def create_order(self, obj_in: OrderCreate, buyer_id: uuid.UUID):
        """Create a new order request."""
        listing = self.listing_repo.get(obj_in.listing_id)
        if not listing:
            raise ListingNotFoundError()

        if listing.sellerId == buyer_id:
            raise OrderStateError("You cannot purchase your own service listing")

        order = self.repo.create(obj_in, buyer_id=buyer_id, seller_id=listing.sellerId)
        order_with_relations = self.repo.get(order.id)

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

        return order_with_relations or order

    async def get_order(self, order_id: uuid.UUID, current_user_id: uuid.UUID) -> Order:
        """Fetch an order by ID enforcing access control."""
        order = self.repo.get(order_id)
        if not order:
            raise OrderNotFoundError()
        
        if order.buyerId != current_user_id and order.sellerId != current_user_id:
            raise OrderForbiddenError()
            
        return order

    async def list_seller_orders(self, user_id: uuid.UUID, status: Optional[str] = None, skip: int = 0, limit: int = 20):
        orders = self.repo.get_by_seller(user_id, status=status, skip=skip, limit=limit)
        
        profile = ProfileRepository(self.db).get_by_user_id(user_id)
        total_orders = profile.sellerCompletedOrdersCount if profile else 0
        
        return {
            "totalOrders": total_orders,
            "orders": orders
        }

    async def list_buyer_orders(self, user_id: uuid.UUID, status: Optional[str] = None, skip: int = 0, limit: int = 20):
        return self.repo.get_by_buyer(user_id, status=status, skip=skip, limit=limit)

    async def cancel_order_request(self, order_id: uuid.UUID, current_user_id: uuid.UUID):
        order = self.repo.get(order_id)
        if not order:
            raise OrderNotFoundError()

        if order.buyerId != current_user_id:
            raise OrderForbiddenError("Only the buyer who requested this service can cancel it")

        if order.status != "requested":
            raise OrderStateError("Only orders in 'requested' status can be cancelled")

        self.repo.delete(order)
        return {
            "message": "Order request cancelled successfully",
            "orderId": order_id,
        }

    async def update_order_status(self, order_id: uuid.UUID, obj_in: OrderUpdate, current_user_id: uuid.UUID):
        """Update order status delegating to specific state transition handlers."""
        order = await self.get_order(order_id, current_user_id=current_user_id)
        
        if not obj_in.status:
            return self.repo.update(order, obj_in)

        if obj_in.status == "accepted":
            return await self._accept_order(order, obj_in.agreed_price, current_user_id)
        elif obj_in.status == "completed":
            return await self._complete_order(order, current_user_id)
        elif obj_in.status == "cancelled":
            return await self._cancel_order(order, obj_in, current_user_id)
            
        return self.repo.update(order, obj_in)

    async def _accept_order(self, order: Order, agreed_price, current_user_id: uuid.UUID) -> Order:
        if order.sellerId != current_user_id:
            raise OrderForbiddenError("Only the seller can accept an order request")
            
        if order.status != "requested":
            raise OrderStateError(f"Cannot accept order in '{order.status}' status")
            
        updated_order = self.repo.mark_as_accepted(order, agreed_price=agreed_price)
        
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

    async def _complete_order(self, order: Order, current_user_id: uuid.UUID) -> Order:
        if order.status not in ("accepted", "completed"):
            raise OrderStateError(f"Cannot complete an order in '{order.status}' status")

        is_buyer = order.buyerId == current_user_id
        is_seller = order.sellerId == current_user_id

        if is_buyer:
            if order.buyerCompletedAt:
                raise OrderStateError("You have already confirmed this order as completed")
                
            updated_order = self.repo.mark_buyer_complete(order)
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
            
        if is_seller:
            if not order.buyerCompletedAt:
                raise OrderStateError("Buyer confirmation is pending; please ask the buyer to mark completion first")
                
            if order.sellerCompletedAt:
                raise OrderStateError("You have already marked this order as completed")
                
            result = self.repo.mark_seller_complete(order)
            ProfileRepository(self.db).increment_seller_orders_count(order.sellerId)
            
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

        raise OrderForbiddenError("Unauthorized role")

    async def _cancel_order(self, order: Order, obj_in: OrderUpdate, current_user_id: uuid.UUID) -> Order:
        is_buyer = order.buyerId == current_user_id
        
        if is_buyer and order.status != "requested":
            raise OrderStateError("Buyers can only cancel an order before it is accepted")
            
        updated_order = self.repo.update(order, obj_in)
        
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
