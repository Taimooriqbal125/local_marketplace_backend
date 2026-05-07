"""
Unit tests for Review Service.
Focuses on validation rules (order state, ownership), reputation updates, and admin permissions.
"""

import uuid
from unittest.mock import MagicMock, AsyncMock, patch

import pytest
from sqlalchemy.orm import Session

from app.services.review_service import (
    ReviewService,
    ReviewNotFoundError,
    OrderNotFoundError,
    OrderStateError,
    ReviewForbiddenError,
    ReviewDuplicateError
)
from app.schemas.review import ReviewCreate


class MockOrder:
    """Mock Order database model."""
    def __init__(self, **kwargs):
        self.id = kwargs.get("id", uuid.uuid4())
        self.buyerId = kwargs.get("buyerId", uuid.uuid4())
        self.sellerId = kwargs.get("sellerId", uuid.uuid4())
        self.status = kwargs.get("status", "completed")
        self.listingId = kwargs.get("listingId", uuid.uuid4())
        self.listing = MagicMock()
        self.listing.title = "Test Service"
        for k, v in kwargs.items():
            setattr(self, k, v)


class MockReview:
    """Mock Review database model."""
    def __init__(self, **kwargs):
        self.id = kwargs.get("id", uuid.uuid4())
        self.reviewerId = kwargs.get("reviewerId", uuid.uuid4())
        self.reviewedUserId = kwargs.get("reviewedUserId", uuid.uuid4())
        self.orderId = kwargs.get("orderId", uuid.uuid4())
        self.rating = kwargs.get("rating", 5)
        for k, v in kwargs.items():
            setattr(self, k, v)


@pytest.fixture
def db_session():
    return MagicMock(spec=Session)


@pytest.fixture
def review_service(db_session):
    """Provides a ReviewService instance with dependencies mocked."""
    service = ReviewService(db_session)
    service.repo = MagicMock()
    service.order_repo = MagicMock()
    service.profile_repo = MagicMock()
    service.notification_service = AsyncMock()
    return service


# ── CREATE Tests ──────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_create_review_success(review_service):
    """Test successful review creation, reputation update, and notification."""
    # Arrange
    buyer_id = uuid.uuid4()
    seller_id = uuid.uuid4()
    order_id = uuid.uuid4()
    obj_in = ReviewCreate(order_id=order_id, rating=5, comment="Great service")
    
    mock_order = MockOrder(id=order_id, buyerId=buyer_id, sellerId=seller_id)
    review_service.order_repo.get.return_value = mock_order
    review_service.repo.get_by_order.return_value = []
    
    mock_review = MockReview(reviewerId=buyer_id, orderId=order_id, rating=5)
    review_service.repo.create.return_value = mock_review
    
    review_service.profile_repo.get_by_user_id.return_value = MagicMock(name="Buyer Name")

    # Act
    result = await review_service.create_review(obj_in, buyer_id)

    # Assert
    assert result.rating == 5
    review_service.repo.create.assert_called_once()
    # Verify reputation update
    review_service.profile_repo.update_seller_rating.assert_called_once_with(seller_id, 5)
    # Verify notification
    review_service.notification_service.send_notification.assert_called_once()


@pytest.mark.anyio
async def test_create_review_order_not_completed(review_service):
    """Test that only completed orders can be reviewed."""
    # Arrange
    order_id = uuid.uuid4()
    obj_in = ReviewCreate(order_id=order_id, rating=5)
    mock_order = MockOrder(status="accepted")
    review_service.order_repo.get.return_value = mock_order

    # Act & Assert
    with pytest.raises(OrderStateError):
        await review_service.create_review(obj_in, uuid.uuid4())


@pytest.mark.anyio
async def test_create_review_not_buyer(review_service):
    """Test that only the buyer of the order can leave a review."""
    # Arrange
    buyer_id = uuid.uuid4()
    attacker_id = uuid.uuid4()
    obj_in = ReviewCreate(order_id=uuid.uuid4(), rating=5)
    mock_order = MockOrder(buyerId=buyer_id)
    review_service.order_repo.get.return_value = mock_order

    # Act & Assert
    with pytest.raises(ReviewForbiddenError):
        await review_service.create_review(obj_in, attacker_id)


@pytest.mark.anyio
async def test_create_review_duplicate(review_service):
    """Test that multiple reviews for the same order are forbidden."""
    # Arrange
    buyer_id = uuid.uuid4()
    order_id = uuid.uuid4()
    obj_in = ReviewCreate(order_id=order_id, rating=5)
    
    mock_order = MockOrder(id=order_id, buyerId=buyer_id)
    review_service.order_repo.get.return_value = mock_order
    review_service.repo.get_by_order.return_value = [MockReview(reviewerId=buyer_id)]

    # Act & Assert
    with pytest.raises(ReviewDuplicateError):
        await review_service.create_review(obj_in, buyer_id)


# ── FETCH & DELETE Tests ──────────────────────────────────────────────────

def test_get_review_success(review_service):
    """Test fetching a review by ID."""
    # Arrange
    review_id = uuid.uuid4()
    mock_review = MockReview(id=review_id)
    review_service.repo.get.return_value = mock_review

    # Act
    result = review_service.get_review(review_id)

    # Assert
    assert result.id == review_id
    review_service.repo.get.assert_called_once_with(review_id)


def test_delete_review_success(review_service):
    """Test that the author can delete their own review."""
    # Arrange
    review_id = uuid.uuid4()
    reviewer_id = uuid.uuid4()
    mock_review = MockReview(id=review_id, reviewerId=reviewer_id)
    review_service.repo.get.return_value = mock_review

    # Act
    review_service.delete_review(review_id, reviewer_id)

    # Assert
    review_service.repo.delete.assert_called_once_with(mock_review)


def test_delete_review_forbidden(review_service):
    """Test that non-authors cannot delete a review."""
    # Arrange
    review_id = uuid.uuid4()
    mock_review = MockReview(reviewerId=uuid.uuid4())
    review_service.repo.get.return_value = mock_review

    # Act & Assert
    with pytest.raises(ReviewForbiddenError):
        review_service.delete_review(review_id, uuid.uuid4())


# ── ADMIN Tests ───────────────────────────────────────────────────────────

def test_list_all_reviews_admin_only(review_service):
    """Test that only admins can access the full review list."""
    # Arrange
    admin_user = MagicMock(is_admin=True)
    regular_user = MagicMock(is_admin=False)
    
    # Act & Assert (Admin)
    review_service.list_all_reviews(admin_user)
    review_service.repo.get_all_filtered.assert_called_once()
    
    # Act & Assert (Regular)
    with pytest.raises(ReviewForbiddenError):
        review_service.list_all_reviews(regular_user)
