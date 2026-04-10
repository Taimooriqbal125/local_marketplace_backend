"""
Order Repository — handles database operations for service orders.
Modernized to SQLAlchemy 2.0 select syntax and safely bridges snake_case schemas with camelCase DB columns.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from app.models.order import Order
from app.models.user import User
from app.models.service_listing import ServiceListing
from app.schemas.order import OrderCreate, OrderUpdate


# Map snake_case schema keys to camelCase SQLAlchemy model properties
ORDER_MODEL_MAP = {
    "listing_id": "listingId",
    "buyer_id": "buyerId",
    "seller_id": "sellerId",
    "proposed_price": "proposedPrice",
    "agreed_price": "agreedPrice",
    "accepted_at": "acceptedAt",
    "seller_completed_at": "sellerCompletedAt",
    "buyer_completed_at": "buyerCompletedAt",
}


class OrderRepository:
    """Class-based repository for Order."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ── Single-record Lookups ────────────────────────────────────────────────

    def get(self, order_id: uuid.UUID) -> Optional[Order]:
        """Fetch a specific order by its primary key, with seller and listing relations."""
        stmt = (
            select(Order)
            .options(
                joinedload(Order.seller).joinedload(User.profile),
                joinedload(Order.buyer).joinedload(User.profile),
                joinedload(Order.listing).joinedload(ServiceListing.media),
                joinedload(Order.listing).joinedload(ServiceListing.category),
            )
            .where(Order.id == order_id)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    # ── Collection Queries ───────────────────────────────────────────────────

    def get_all(self, skip: int = 0, limit: int = 20) -> List[Order]:
        """Return a paginated list of all orders."""
        stmt = (
            select(Order)
            .order_by(Order.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_by_buyer(self, buyer_id: uuid.UUID, status: Optional[str] = None, skip: int = 0, limit: int = 20) -> List[Order]:
        """Return orders requested by a specific buyer, with seller and listing context."""
        stmt = (
            select(Order)
            .options(
                joinedload(Order.seller).joinedload(User.profile),
                joinedload(Order.listing).joinedload(ServiceListing.media),
            )
            .where(Order.buyerId == buyer_id)
        )
        if status:
            stmt = stmt.where(Order.status == status)
            
        stmt = stmt.order_by(Order.created_at.desc()).offset(skip).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def get_by_seller(self, seller_id: uuid.UUID, status: Optional[str] = None, skip: int = 0, limit: int = 20) -> List[Order]:
        """Return orders received by a specific seller, with buyer and listing context."""
        stmt = (
            select(Order)
            .options(
                joinedload(Order.buyer).joinedload(User.profile),
                joinedload(Order.listing).joinedload(ServiceListing.media),
            )
            .where(Order.sellerId == seller_id)
        )
        if status:
            stmt = stmt.where(Order.status == status)
            
        stmt = stmt.order_by(Order.created_at.desc()).offset(skip).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def get_by_user(self, user_id: uuid.UUID, status: Optional[str] = None, skip: int = 0, limit: int = 20) -> List[Order]:
        """Return orders where the user is either the buyer or the seller."""
        stmt = (
            select(Order)
            .options(
                joinedload(Order.buyer).joinedload(User.profile),
                joinedload(Order.listing).joinedload(ServiceListing.category),
                joinedload(Order.listing).joinedload(ServiceListing.media),
            )
            .where(or_(Order.buyerId == user_id, Order.sellerId == user_id))
        )
        if status:
            stmt = stmt.where(Order.status == status)
            
        stmt = stmt.order_by(Order.created_at.desc()).offset(skip).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def get_by_listing(self, listing_id: uuid.UUID, skip: int = 0, limit: int = 20) -> List[Order]:
        """Return all orders associated with a specific listing."""
        stmt = (
            select(Order)
            .where(Order.listingId == listing_id)
            .order_by(Order.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())

    # ── Write Operations ─────────────────────────────────────────────────────

    def create(self, obj_in: OrderCreate, buyer_id: uuid.UUID, seller_id: uuid.UUID) -> Order:
        """Insert a new order request with explicit mapping."""
        data = obj_in.model_dump()
        db_data = {
            "buyerId": buyer_id,
            "sellerId": seller_id,
            "status": "requested"
        }
        
        for key, value in data.items():
            model_key = ORDER_MODEL_MAP.get(key, key)
            db_data[model_key] = value

        db_obj = Order(**db_data)
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def update(self, db_obj: Order, obj_in: OrderUpdate) -> Order:
        """Apply updates to an existing order (status, agreedPrice, etc.) using safe mapping."""
        update_data = obj_in.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            model_key = ORDER_MODEL_MAP.get(key, key)
            setattr(db_obj, model_key, value)
        
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def mark_as_accepted(self, order: Order, agreed_price: Optional[int] = None) -> Order:
        """Transition status to 'accepted' and set acceptedAt."""
        order.status = "accepted"
        order.acceptedAt = datetime.now(timezone.utc)
        if agreed_price is not None:
            order.agreedPrice = agreed_price
            
        self.db.commit()
        self.db.refresh(order)
        return order

    def mark_seller_complete(self, order: Order) -> Order:
        """Record seller work completion."""
        order.sellerCompletedAt = datetime.now(timezone.utc)
        if order.buyerCompletedAt and order.sellerCompletedAt:
            order.status = "completed"
            
        self.db.commit()
        self.db.refresh(order)
        return order

    def mark_buyer_complete(self, order: Order) -> Order:
        """Record buyer satisfaction and final completion."""
        order.buyerCompletedAt = datetime.now(timezone.utc)
        if order.buyerCompletedAt and order.sellerCompletedAt:
            order.status = "completed"
            
        self.db.commit()
        self.db.refresh(order)
        return order

    def delete(self, db_obj: Order) -> None:
        """Remove an order record from the database."""
        self.db.delete(db_obj)
        self.db.commit()
