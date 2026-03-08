"""
Order Routes — API endpoints for managing service orders.
"""

import uuid
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session

from app.core import security
from app.db.session import get_db
from app.models.user import User
from app.schemas.order import OrderCreate, OrderResponse, OrderAsSellerResponse, OrderAsBuyerResponse, SellerOrdersResponse, OrderDetailResponse, OrderUpdate, OrderStatus
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
    service = OrderService(db)
    return await service.create_order(obj_in, buyer_id=current_user.id)


@router.get("/me/as-seller", response_model=SellerOrdersResponse)
async def list_my_orders_as_seller(
    status: Optional[OrderStatus] = Query(None, description="Filter by status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(security.get_current_user),
):
    """Retrieve orders where the current user is the seller (incoming requests)."""
    service = OrderService(db)
    return await service.list_seller_orders(user_id=current_user.id, status=status, skip=skip, limit=limit)


@router.get("/me/as-buyer", response_model=List[OrderAsBuyerResponse])
async def list_my_orders_as_buyer(
    status: Optional[OrderStatus] = Query(None, description="Filter by status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(security.get_current_user),
):
    """Retrieve orders where the current user is the buyer (outgoing requests)."""
    service = OrderService(db)
    return await service.list_buyer_orders(user_id=current_user.id, status=status, skip=skip, limit=limit)


@router.get("/{order_id}", response_model=OrderDetailResponse)
async def get_order(
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(security.get_current_user),
):
    """General view for a specific order. Returns full details for involved parties."""
    service = OrderService(db)
    return await service.get_order(order_id, current_user_id=current_user.id)


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
    service = OrderService(db)
    return await service.update_order_status(order_id, obj_in, current_user_id=current_user.id)
