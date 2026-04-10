"""
Order Routes — API endpoints for managing service orders.
"""

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core import security
from app.db.session import get_db
from app.models.user import User
from app.schemas.order import OrderCreate, OrderResponse, OrderAsBuyerResponse, SellerOrdersResponse, OrderDetailResponse, OrderUpdate, OrderStatus, OrderCancelResponse
from app.services.order_service import OrderService

router = APIRouter(
    prefix="/orders",
    tags=["Orders"],
)

@router.post("/", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order(
    obj_in: OrderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(security.get_current_user),
):
    """
    Create a new order request for a service listing.
    """
    return await OrderService(db).create_order(obj_in, buyer_id=current_user.id)

@router.get("/me/as-seller", response_model=SellerOrdersResponse)
async def list_my_orders_as_seller(
    status: Optional[OrderStatus] = Query(None, description="Filter by status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(security.get_current_user),
):
    """Retrieve orders where the current user is the seller (incoming requests)."""
    return await OrderService(db).list_seller_orders(user_id=current_user.id, status=status, skip=skip, limit=limit)

@router.get("/me/as-buyer", response_model=List[OrderAsBuyerResponse])
async def list_my_orders_as_buyer(
    status: Optional[OrderStatus] = Query(None, description="Filter by status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(security.get_current_user),
):
    """Retrieve orders where the current user is the buyer (outgoing requests)."""
    return await OrderService(db).list_buyer_orders(user_id=current_user.id, status=status, skip=skip, limit=limit)

@router.get("/{order_id}", response_model=OrderDetailResponse)
async def get_order(
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(security.get_current_user),
):
    """General view for a specific order. Returns full details for involved parties."""
    return await OrderService(db).get_order(order_id, current_user_id=current_user.id)

@router.delete("/{order_id}/cancel-request", response_model=OrderCancelResponse, status_code=status.HTTP_200_OK)
async def cancel_order_request(
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(security.get_current_user),
):
    """
    Cancel a buyer order request by deleting it.
    Allowed only for the buyer who created the order, and only when status is 'requested'.
    """
    return await OrderService(db).cancel_order_request(order_id=order_id, current_user_id=current_user.id)

@router.patch("/{order_id}", response_model=OrderDetailResponse)
async def update_order_status(
    order_id: uuid.UUID,
    obj_in: OrderUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(security.get_current_user),
):
    """
    Update an order's status (accept, complete, cancel).
    The service layer handles role-based authorization.
    """
    return await OrderService(db).update_order_status(order_id, obj_in, current_user_id=current_user.id)
