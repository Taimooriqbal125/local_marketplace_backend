"""
Order Routes — API endpoints for managing service orders.
"""

import uuid
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core import security
from app.db.session import get_db
from app.models.user import User
from app.schemas.order import OrderCreate, OrderResponse, OrderUpdate
from app.services.order_service import OrderService

router = APIRouter(
    prefix="/orders",
    tags=["Orders"],
)


@router.post("/", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
def create_order(
    obj_in: OrderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(security.get_current_user),
):
    """
    Create a new order request for a service listing.
    """
    service = OrderService(db)
    return service.create_order(obj_in, buyer_id=current_user.id)


@router.get("/me", response_model=List[OrderResponse])
def list_my_orders(
    role: Literal["buyer", "seller"] = Query("buyer", description="View orders as buyer or seller"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(security.get_current_user),
):
    """
    Retrieve orders associated with the current user.
    """
    service = OrderService(db)
    return service.list_my_orders(user_id=current_user.id, role=role, skip=skip, limit=limit)


@router.get("/{order_id}", response_model=OrderResponse)
def get_order(
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(security.get_current_user),
):
    """
    Get detailed information for a specific order.
    Note: In a production app, we'd add checks ensuring only buyer/seller/admin can see this.
    """
    service = OrderService(db)
    return service.get_order(order_id)


@router.patch("/{order_id}", response_model=OrderResponse)
def update_order_status(
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
    return service.update_order_status(order_id, obj_in, current_user_id=current_user.id)
