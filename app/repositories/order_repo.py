"""
Order Repository — handles database operations for service orders.
"""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from app.models.order import Order
from app.schemas.order import OrderCreate, OrderUpdate


class OrderRepository:
    """Class-based repository for Order."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ── Single-record Lookups ────────────────────────────────────────────────

    def get(self, order_id: uuid.UUID) -> Optional[Order]:
        """Fetch a specific order by its primary key, with seller and listing relations."""
        from sqlalchemy.orm import joinedload
        from app.models.user import User

        from app.models.service_listing import ServiceListing

        return (
            self.db.query(Order)
            .options(
                joinedload(Order.seller).joinedload(User.profile),
                joinedload(Order.buyer).joinedload(User.profile),
                joinedload(Order.listing).joinedload(ServiceListing.media),
                joinedload(Order.listing).joinedload(ServiceListing.category),
            )
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

    def get_by_buyer(self, buyer_id: uuid.UUID, status: Optional[str] = None, skip: int = 0, limit: int = 20) -> list[Order]:
        """Return orders requested by a specific buyer, with seller and listing context."""
        from sqlalchemy.orm import joinedload
        from app.models.user import User
        from app.models.service_listing import ServiceListing

        query = (
            self.db.query(Order)
            .options(
                joinedload(Order.listing).joinedload(ServiceListing.category),
                joinedload(Order.listing).joinedload(ServiceListing.media),
            )
            .filter(Order.buyerId == buyer_id)
        )
        if status:
            query = query.filter(Order.status == status)
        return (
            query
            .order_by(Order.createdAt.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_seller(self, seller_id: uuid.UUID, status: Optional[str] = None, skip: int = 0, limit: int = 20) -> list[Order]:
        """Return orders received by a specific seller, with buyer and listing context."""
        from sqlalchemy.orm import joinedload
        from app.models.user import User
        from app.models.service_listing import ServiceListing

        query = (
            self.db.query(Order)
            .options(
                joinedload(Order.buyer).joinedload(User.profile),
                joinedload(Order.listing).joinedload(ServiceListing.category),
            )
            .filter(Order.sellerId == seller_id)
        )
        if status:
            query = query.filter(Order.status == status)
        return (
            query
            .order_by(Order.createdAt.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_user(self, user_id: uuid.UUID, status: Optional[str] = None, skip: int = 0, limit: int = 20) -> list[Order]:
        """Return orders where the user is either the buyer or the seller."""
        from sqlalchemy.orm import joinedload
        from app.models.user import User
        from app.models.service_listing import ServiceListing

        query = (
            self.db.query(Order)
            .options(
                joinedload(Order.buyer).joinedload(User.profile),
                joinedload(Order.listing).joinedload(ServiceListing.category),
                joinedload(Order.listing).joinedload(ServiceListing.media),
            )
            .filter(or_(Order.buyerId == user_id, Order.sellerId == user_id))
        )
        if status:
            query = query.filter(Order.status == status)
        return (
            query
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
        
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def mark_as_accepted(self, order: Order, agreed_price: Optional[int] = None) -> Order:
        """Transition status to 'accepted' and set acceptedAt."""
        from datetime import datetime, timezone
        order.status = "accepted"
        order.acceptedAt = datetime.now(timezone.utc)
        if agreed_price:
            order.agreedPrice = agreed_price
        self.db.commit()
        self.db.refresh(order)
        return order

    def mark_seller_complete(self, order: Order) -> Order:
        """Record seller work completion."""
        from datetime import datetime, timezone
        order.status = "completed"
        order.sellerCompletedAt = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(order)
        return order

    def mark_buyer_complete(self, order: Order) -> Order:
        """Record buyer satisfaction and final completion."""
        from datetime import datetime, timezone
        order.status = "completed"
        order.buyerCompletedAt = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(order)
        return order

    def delete(self, db_obj: Order) -> None:
        """Remove an order record from the database."""
        self.db.delete(db_obj)
        self.db.commit()
