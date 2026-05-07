"""
Unit tests for ServiceListing Service.
Focuses on pricing rules, ownership security, and proximity search orchestration.
"""

import uuid
from decimal import Decimal
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from app.services.service_listing_service import (
    ServiceListingService,
    ListingNotFoundError,
    ListingForbiddenError,
    DuplicateListingError,
    InvalidPricingRuleError
)
from app.schemas.services_listing import ServiceListingCreate, ServiceListingUpdate


class MockListing:
    """Mock ServiceListing database model."""
    def __init__(self, **kwargs):
        self.id = kwargs.get("id", uuid.uuid4())
        self.sellerId = kwargs.get("sellerId", uuid.uuid4())
        self.title = kwargs.get("title", "Test Service")
        self.description = kwargs.get("description", "Test Description")
        self.priceType = kwargs.get("priceType", "hourly")
        self.priceAmount = kwargs.get("priceAmount", Decimal("50.00"))
        self.isNegotiable = kwargs.get("isNegotiable", True)
        self.serviceLocation = kwargs.get("serviceLocation", "Islamabad, Pakistan")
        self.serviceRadiusKm = kwargs.get("serviceRadiusKm", 10.0)
        self.status = kwargs.get("status", "active")
        self.createdAt = kwargs.get("createdAt", datetime.now(timezone.utc))
        self.updatedAt = kwargs.get("updatedAt", datetime.now(timezone.utc))
        self.categoryId = kwargs.get("categoryId", uuid.uuid4())
        self.cityId = kwargs.get("cityId", uuid.uuid4())

        # Mock Relationships for Pydantic validators
        self.category = MagicMock()
        self.category.name = "Test Category"
        self.city = MagicMock()
        self.city.name = "Islamabad"
        self.media = []
        self.seller = MagicMock()
        self.seller.profile = MagicMock()
        self.seller.profile.name = "Seller Name"
        self.seller.profile.photoUrl = "http://example.com/photo.jpg"
        self.seller.profile.sellerRatingAvg = Decimal("4.5")
        self.seller.profile.sellerRatingCount = 10
        self.seller.phone = "+923001234567"

        # Add any other fields dynamically
        for key, value in kwargs.items():
            setattr(self, key, value)


@pytest.fixture
def db_session():
    return MagicMock(spec=Session)


@pytest.fixture
def listing_service(db_session):
    """Provides a ServiceListingService instance with mocked repository."""
    service = ServiceListingService(db_session)
    service.repo = MagicMock()
    return service


# ── PRICING RULE Tests ───────────────────────────────────────────────────

def test_validate_pricing_rules_success(listing_service):
    """Test valid pricing rule combinations."""
    # Should not raise
    listing_service._validate_pricing_rules(price_type="fixed", is_negotiable=False)
    listing_service._validate_pricing_rules(price_type="hourly", is_negotiable=True)


def test_validate_pricing_rules_invalid_type(listing_service):
    """Test that unsupported price types raise InvalidPricingRuleError."""
    with pytest.raises(InvalidPricingRuleError, match="one of: fixed"):
        listing_service._validate_pricing_rules(price_type="monthly", is_negotiable=False)


def test_validate_pricing_rules_fixed_negotiable_conflict(listing_service):
    """Test that fixed price cannot be negotiable."""
    with pytest.raises(InvalidPricingRuleError, match="cannot be negotiable"):
        listing_service._validate_pricing_rules(price_type="fixed", is_negotiable=True)


# ── CREATE Tests ──────────────────────────────────────────────────────────

def test_create_listing_success(listing_service):
    """Test successful listing creation."""
    # Arrange
    seller_id = uuid.uuid4()
    obj_in = ServiceListingCreate(
        title="Valid Title",
        description="Unique Description",
        price_type="hourly",
        is_negotiable=True,
        price_amount=50.0,
        service_location="Islamabad",
        service_radius_km=10.0,
        category_id=uuid.uuid4(),
        city_id=uuid.uuid4()
    )
    listing_service.repo.get_by_title_and_description.return_value = None
    listing_service.repo.create.return_value = MockListing(title="Valid Title")

    # Act
    result = listing_service.create_listing(obj_in, seller_id)

    # Assert
    assert result.title == "Valid Title"
    listing_service.repo.create.assert_called_once()


def test_create_listing_duplicate(listing_service):
    """Test that duplicate title and description are rejected."""
    # Arrange
    obj_in = ServiceListingCreate(
        title="Dup", description="Dup", price_type="fixed", is_negotiable=False,
        price_amount=10, service_location="Loc", service_radius_km=5,
        category_id=uuid.uuid4(), city_id=uuid.uuid4()
    )
    listing_service.repo.get_by_title_and_description.return_value = MockListing()

    # Act & Assert
    with pytest.raises(DuplicateListingError):
        listing_service.create_listing(obj_in, uuid.uuid4())


# ── UPDATE & PERMISSION Tests ─────────────────────────────────────────────

def test_update_listing_success_by_owner(listing_service):
    """Test successful update by the listing owner."""
    # Arrange
    listing_id = uuid.uuid4()
    seller_id = uuid.uuid4()
    mock_listing = MockListing(sellerId=seller_id)
    listing_service.repo.get.return_value = mock_listing
    
    # Ensure no duplicate conflict on title change
    listing_service.repo.get_by_title_and_description.return_value = None
    
    update_data = ServiceListingUpdate(title="Updated")
    listing_service.repo.update.return_value = MockListing(title="Updated")

    # Act
    result = listing_service.update_listing(listing_id, update_data, seller_id)

    # Assert
    assert result.title == "Updated"
    listing_service.repo.update.assert_called_once()


def test_update_listing_forbidden(listing_service):
    """Test that non-owners cannot update a listing."""
    # Arrange
    seller_id = uuid.uuid4()
    attacker_id = uuid.uuid4()
    listing_service.repo.get.return_value = MockListing(sellerId=seller_id)

    # Act & Assert
    with pytest.raises(ListingForbiddenError):
        listing_service.update_listing(uuid.uuid4(), ServiceListingUpdate(), attacker_id)


def test_update_listing_admin_bypass(listing_service):
    """Test that an admin can update any listing."""
    # Arrange
    seller_id = uuid.uuid4()
    admin_id = uuid.uuid4()
    listing_service.repo.get.return_value = MockListing(sellerId=seller_id)
    listing_service.repo.update.return_value = MockListing()
    # Ensure no duplicate conflict
    listing_service.repo.get_by_title_and_description.return_value = None

    # Act
    listing_service.update_listing(uuid.uuid4(), ServiceListingUpdate(), admin_id, is_admin=True)

    # Assert
    listing_service.repo.update.assert_called_once()


def test_update_listing_ban_restriction(listing_service):
    """Test that only admins can ban or modify banned listings."""
    # Arrange
    seller_id = uuid.uuid4()
    listing_service.repo.get.return_value = MockListing(sellerId=seller_id, status="banned")

    # Act & Assert
    with pytest.raises(ListingForbiddenError):
        listing_service.update_listing(uuid.uuid4(), ServiceListingUpdate(title="Try Edit"), seller_id)


# ── DELETE Tests ──────────────────────────────────────────────────────────

def test_delete_listing_success(listing_service):
    """Test successful listing deletion."""
    # Arrange
    seller_id = uuid.uuid4()
    mock_listing = MockListing(sellerId=seller_id)
    listing_service.repo.get.return_value = mock_listing

    # Act
    listing_service.delete_listing(uuid.uuid4(), seller_id)

    # Assert
    listing_service.repo.delete.assert_called_once_with(mock_listing)


# ── QUERY Tests ───────────────────────────────────────────────────────────

def test_list_listings_pagination(listing_service):
    """Test that listing pagination correctly computes skip/limit."""
    # Arrange
    listing_service.repo.get_filtered.return_value = ([], 0)

    # Act
    listing_service.list_listings(page=3, page_size=10)

    # Assert
    # skip = (3-1) * 10 = 20
    listing_service.repo.get_filtered.assert_called_once()
    args = listing_service.repo.get_filtered.call_args[1]
    assert args["skip"] == 20
    assert args["limit"] == 10
