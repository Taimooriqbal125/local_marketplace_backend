"""
Order Repository — handles database operations for service orders.
"""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.models.order import Order
from app.schemas.order import OrderCreate, OrderUpdate


class OrderRepository:
    """Class-based repository for Order."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ── Single-record Lookups ────────────────────────────────────────────────

    def get(self, order_id: uuid.UUID) -> Optional[Order]:
        """Fetch a specific order by its primary key."""
        return (
            self.db.query(Order)
            .filter(Order.id == order_id)
            .first()
        )

    # ── Collection Queries ───────────────────────────────────────────────────

    def get_all(self, skip: int = 0, limit: int = 20) -> list[Order]:
        """Return a paginated list of all orders."""
        return (
            self.db.query(Order)
            .order_by(Order.createdAt.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_buyer(self, buyer_id: uuid.UUID, skip: int = 0, limit: int = 20) -> list[Order]:
        """Return orders requested by a specific buyer."""
        return (
            self.db.query(Order)
            .filter(Order.buyerId == buyer_id)
            .order_by(Order.createdAt.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_seller(self, seller_id: uuid.UUID, skip: int = 0, limit: int = 20) -> list[Order]:
        """Return orders received by a specific seller."""
        return (
            self.db.query(Order)
            .filter(Order.sellerId == seller_id)
            .order_by(Order.createdAt.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_listing(self, listing_id: uuid.UUID, skip: int = 0, limit: int = 20) -> list[Order]:
        """Return all orders associated with a specific listing."""
        return (
            self.db.query(Order)
            .filter(Order.listingId == listing_id)
            .order_by(Order.createdAt.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    # ── Write Operations ─────────────────────────────────────────────────────

    def create(self, obj_in: OrderCreate, buyer_id: uuid.UUID, seller_id: uuid.UUID) -> Order:
        """Insert a new order request."""
        db_obj = Order(
            listingId=obj_in.listingId,
            buyerId=buyer_id,
            sellerId=seller_id,
            proposedPrice=obj_in.proposedPrice,
            notes=obj_in.notes,
            status="requested"
        )
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def update(self, db_obj: Order, obj_in: OrderUpdate) -> Order:
        """Apply updates to an existing order (status, agreedPrice, etc.)."""
        update_data = obj_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_obj, field, value)
        
        # Internal lifecycle management: update timestamps based on status
        if obj_in.status == "accepted":
            from sqlalchemy.sql import func
            db_obj.acceptedAt = func.now()
        elif obj_in.status == "completed":
            from sqlalchemy.sql import func
            db_obj.sellerCompletedAt = func.now()

        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def delete(self, db_obj: Order) -> None:
        """Remove an order record from the database."""
        self.db.delete(db_obj)
        self.db.commit()
