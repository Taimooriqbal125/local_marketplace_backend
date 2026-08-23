"""
Unit tests for Order Service.
Focuses on state transitions, multi-role access control, and notification triggers.
"""

import uuid
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock, patch

import pytest
from sqlalchemy.orm import Session

from app.services.order_service import (
    OrderService,
    OrderNotFoundError,
    OrderForbiddenError,
    OrderStateError,
    ListingNotFoundError
)
from app.schemas.order import OrderCreate, OrderUpdate
from app.models.notification import NotificationType


class MockOrder:
    """Mock Order database model."""
    def __init__(self, **kwargs):
        self.id = kwargs.get("id", uuid.uuid4())
        self.buyerId = kwargs.get("buyerId", uuid.uuid4())
        self.sellerId = kwargs.get("sellerId", uuid.uuid4())
        self.listingId = kwargs.get("listingId", uuid.uuid4())
        self.status = kwargs.get("status", "requested")
        self.buyerCompletedAt = kwargs.get("buyerCompletedAt", None)
        self.sellerCompletedAt = kwargs.get("sellerCompletedAt", None)
        self.cancelledAt = kwargs.get("cancelledAt", None)

        # Relationships read by OrderService._ensure_relations_loaded()
        # to force eager loading before response serialization.
        self.listing = kwargs.get("listing", MagicMock(media=[], category=MagicMock()))
        self.seller = kwargs.get("seller", MagicMock(profile=MagicMock()))
        self.buyer = kwargs.get("buyer", MagicMock(profile=MagicMock()))

        for k, v in kwargs.items():
            setattr(self, k, v)


class MockProfile:
    """Mock Profile database model."""
    def __init__(self, name="Test User"):
        self.name = name
        self.user = MagicMock()
        self.user.email = "test@example.com"
        self.user.phone = "+923001234567"
        self.sellerCompletedOrdersCount = 10


@pytest.fixture
def db_session():
    return MagicMock(spec=Session)


@pytest.fixture
def order_service(db_session):
    """Provides an OrderService instance with all dependencies mocked."""
    service = OrderService(db_session)
    service.repo = MagicMock()
    service.listing_repo = MagicMock()
    service.notification_service = AsyncMock()
    return service


# ── CREATE Tests ──────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_create_order_success(order_service):
    """Test successful order creation and notification dispatch."""
    # Arrange
    buyer_id = uuid.uuid4()
    seller_id = uuid.uuid4()
    listing_id = uuid.uuid4()
    obj_in = OrderCreate(listing_id=listing_id, proposed_price=500)
    
    mock_listing = MagicMock(id=listing_id, sellerId=seller_id, title="Test Service")
    order_service.listing_repo.get.return_value = mock_listing
    
    mock_order = MockOrder(id=uuid.uuid4(), buyerId=buyer_id, sellerId=seller_id)
    order_service.repo.create.return_value = mock_order
    order_service.repo.get.return_value = mock_order

    with patch("app.services.order_service.ProfileRepository") as mock_profile_repo:
        mock_profile_repo.return_value.get_by_user_id.return_value = MockProfile("Buyer Name")
        
        # Act
        result = await order_service.create_order(obj_in, buyer_id)

        # Assert
        assert result.id == mock_order.id
        order_service.repo.create.assert_called_once()
        order_service.notification_service.send_notification.assert_called_once()
        
        # Verify notification content
        call_kwargs = order_service.notification_service.send_notification.call_args[1]
        assert call_kwargs["user_id"] == seller_id
        assert call_kwargs["type"] == NotificationType.ORDER_REQUESTED
        assert "Buyer Name" in call_kwargs["body"]


@pytest.mark.anyio
async def test_create_order_purchase_own_service(order_service):
    """Test that a seller cannot purchase their own service."""
    # Arrange
    user_id = uuid.uuid4()
    obj_in = OrderCreate(listing_id=uuid.uuid4(), proposed_price=500)
    order_service.listing_repo.get.return_value = MagicMock(sellerId=user_id)

    # Act & Assert
    with pytest.raises(OrderStateError, match="cannot purchase your own"):
        await order_service.create_order(obj_in, user_id)


# ── GET Tests ─────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_get_order_access_denied(order_service):
    """Test that unrelated users cannot view an order."""
    # Arrange
    order_id = uuid.uuid4()
    other_user_id = uuid.uuid4()
    mock_order = MockOrder(buyerId=uuid.uuid4(), sellerId=uuid.uuid4())
    order_service.repo.get.return_value = mock_order

    # Act & Assert
    with pytest.raises(OrderForbiddenError):
        await order_service.get_order(order_id, other_user_id)


# ── STATE TRANSITION Tests ────────────────────────────────────────────────

@pytest.mark.anyio
async def test_accept_order_success(order_service):
    """Test that a seller can accept a requested order."""
    # Arrange
    order_id = uuid.uuid4()
    seller_id = uuid.uuid4()
    mock_order = MockOrder(id=order_id, sellerId=seller_id, status="requested")
    
    order_service.repo.get.return_value = mock_order
    order_service.repo.mark_as_accepted.return_value = MockOrder(status="accepted")
    
    with patch("app.services.order_service.ProfileRepository") as mock_profile_repo:
        mock_profile_repo.return_value.get_by_user_id.return_value = MockProfile("Seller Name")
        
        # Act
        obj_in = OrderUpdate(status="accepted", agreed_price=100.0)
        result = await order_service.update_order_status(order_id, obj_in, seller_id)

        # Assert
        assert result.status == "accepted"
        order_service.repo.mark_as_accepted.assert_called_once()
        order_service.notification_service.send_notification.assert_called_once()


@pytest.mark.anyio
async def test_complete_order_buyer_confirmation(order_service):
    """Test that a buyer can confirm an order as completed."""
    # Arrange
    order_id = uuid.uuid4()
    buyer_id = uuid.uuid4()
    mock_order = MockOrder(id=order_id, buyerId=buyer_id, status="accepted", buyerCompletedAt=None)
    
    order_service.repo.get.return_value = mock_order
    order_service.repo.mark_buyer_complete.return_value = MockOrder(buyerCompletedAt=datetime.now())

    with patch("app.services.order_service.ProfileRepository") as mock_profile_repo:
        mock_profile_repo.return_value.get_by_user_id.return_value = MockProfile("Buyer")
        
        # Act
        obj_in = OrderUpdate(status="completed")
        result = await order_service.update_order_status(order_id, obj_in, buyer_id)

        # Assert
        assert result.buyerCompletedAt is not None
        order_service.repo.mark_buyer_complete.assert_called_once()


@pytest.mark.anyio
async def test_complete_order_seller_finalization_pending_buyer(order_service):
    """Test that a seller cannot finalize an order if the buyer hasn't confirmed."""
    # Arrange
    order_id = uuid.uuid4()
    seller_id = uuid.uuid4()
    mock_order = MockOrder(id=order_id, sellerId=seller_id, status="accepted", buyerCompletedAt=None)
    order_service.repo.get.return_value = mock_order

    # Act & Assert
    obj_in = OrderUpdate(status="completed")
    with pytest.raises(OrderStateError, match="Buyer confirmation is pending"):
        await order_service.update_order_status(order_id, obj_in, seller_id)


@pytest.mark.anyio
async def test_cancel_order_buyer_pre_acceptance(order_service):
    """Test that a buyer can cancel an order before it is accepted."""
    # Arrange
    order_id = uuid.uuid4()
    buyer_id = uuid.uuid4()
    mock_order = MockOrder(id=order_id, buyerId=buyer_id, status="requested")
    order_service.repo.get.return_value = mock_order
    order_service.repo.mark_as_cancelled.return_value = MockOrder(status="cancelled", cancelledAt=datetime.now())

    with patch("app.services.order_service.ProfileRepository") as mock_profile_repo:
        mock_profile_repo.return_value.get_by_user_id.return_value = MockProfile("Buyer")
        
        # Act
        obj_in = OrderUpdate(status="cancelled")
        result = await order_service.update_order_status(order_id, obj_in, buyer_id)

        # Assert
        assert result.status == "cancelled"
        assert result.cancelledAt is not None
        order_service.notification_service.send_notification.assert_called_once()


def test_cleanup_cancelled_orders(order_service):
    """Test deleting cancelled orders through the cleanup service."""
    order_service.repo.delete_cancelled_orders.return_value = 4

    result = order_service.cleanup_cancelled_orders(retention_days=14)

    assert result == {"deleted_count": 4}
    order_service.repo.delete_cancelled_orders.assert_called_once()
