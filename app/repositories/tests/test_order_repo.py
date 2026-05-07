import uuid
from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.db.base_class import Base
from app.models.order import Order
from app.models.user import User
from app.models.profile import Profile
from app.models.category import Category
from app.models.service_listing import ServiceListing
from app.models.listing_media import ListingMedia
from app.schemas.order import OrderCreate, OrderUpdate
from app.repositories.order_repo import OrderRepository


@pytest.fixture(scope="function")
def db_session() -> Session:
    """Create a clean in-memory database with all required tables."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    
    # Ensure all models are registered for create_all
    Base.metadata.create_all(bind=engine)
    
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def repo(db_session: Session) -> OrderRepository:
    return OrderRepository(db_session)


@pytest.fixture
def setup_data(db_session: Session):
    """Helper to create minimum required related entities for Order tests."""
    # 1. Create Category
    cat = Category(name="Test Cat", slug="test-cat")
    db_session.add(cat)
    
    # 2. Create Seller & Buyer
    seller = User(email="seller@example.com", phone="123456", hashed_password="pw")
    buyer = User(email="buyer@example.com", phone="789012", hashed_password="pw")
    db_session.add_all([seller, buyer])
    db_session.flush() # Get IDs
    
    # 3. Create Profiles
    s_prof = Profile(userId=seller.id, name="Seller Name")
    b_prof = Profile(userId=buyer.id, name="Buyer Name")
    db_session.add_all([s_prof, b_prof])
    
    # 4. Create Listing
    listing = ServiceListing(
        sellerId=seller.id,
        categoryId=cat.id,
        title="Test Service",
        serviceLocation="City",
        serviceRadiusKm=10.0,
        priceAmount=100.0,
        status="active"
    )
    db_session.add(listing)
    db_session.flush()

    # 5. Add Media
    media = ListingMedia(listingId=listing.id, imageUrl="https://img.com/1.jpg")
    db_session.add(media)
    
    db_session.commit()
    
    return {
        "buyer": buyer,
        "seller": seller,
        "listing": listing,
        "category": cat
    }


def test_create_order(repo: OrderRepository, setup_data):
    """Test creating a new order request."""
    data = setup_data
    order_in = OrderCreate(
        listing_id=data["listing"].id,
        proposed_price=90,
        notes="Please do it fast"
    )
    
    order = repo.create(order_in, buyer_id=data["buyer"].id, seller_id=data["seller"].id)
    
    assert order.id is not None
    assert order.status == "requested"
    assert order.proposedPrice == 90
    assert order.buyerId == data["buyer"].id
    assert order.sellerId == data["seller"].id


def test_get_order_with_relations(repo: OrderRepository, setup_data):
    """Test fetching an order and verifying joined relationships."""
    data = setup_data
    order_in = OrderCreate(listing_id=data["listing"].id, proposed_price=100)
    created = repo.create(order_in, buyer_id=data["buyer"].id, seller_id=data["seller"].id)
    
    fetched = repo.get(created.id)
    
    assert fetched is not None
    assert fetched.id == created.id
    # Check relations (should be loaded due to joinedload)
    assert fetched.buyer.profile.name == "Buyer Name"
    assert fetched.seller.profile.name == "Seller Name"
    assert fetched.listing.title == "Test Service"
    assert len(fetched.listing.media) == 1


def test_get_by_buyer_and_seller(repo: OrderRepository, setup_data):
    """Test filtering orders by role."""
    data = setup_data
    repo.create(OrderCreate(listing_id=data["listing"].id, proposed_price=50), 
                buyer_id=data["buyer"].id, seller_id=data["seller"].id)
    
    # Check buyer side
    buyer_orders = repo.get_by_buyer(data["buyer"].id)
    assert len(buyer_orders) == 1
    
    # Check seller side
    seller_orders = repo.get_by_seller(data["seller"].id)
    assert len(seller_orders) == 1


def test_get_by_user_composite(repo: OrderRepository, setup_data, db_session: Session):
    """Test the 'get_by_user' method which checks both buyer and seller roles."""
    data = setup_data
    
    # Order 1: Current user is buyer
    repo.create(OrderCreate(listing_id=data["listing"].id, proposed_price=10), 
                buyer_id=data["buyer"].id, seller_id=data["seller"].id)
    
    # Order 2: Current user is seller
    # For this we need another buyer
    buyer2 = User(email="buyer2@example.com", phone="222", hashed_password="p")
    db_session.add(buyer2)
    db_session.flush()
    repo.create(OrderCreate(listing_id=data["listing"].id, proposed_price=20), 
                buyer_id=buyer2.id, seller_id=data["buyer"].id) # data["buyer"] is seller here
    
    results = repo.get_by_user(data["buyer"].id)
    assert len(results) == 2


def test_order_lifecycle_updates(repo: OrderRepository, setup_data):
    """Test status transitions: accepted -> seller_complete -> buyer_complete."""
    data = setup_data
    order = repo.create(OrderCreate(listing_id=data["listing"].id, proposed_price=100), 
                        buyer_id=data["buyer"].id, seller_id=data["seller"].id)
    
    # 1. Accept
    accepted = repo.mark_as_accepted(order, agreed_price=95)
    assert accepted.status == "accepted"
    assert accepted.agreedPrice == 95
    assert accepted.acceptedAt is not None
    
    # 2. Seller Complete
    sc = repo.mark_seller_complete(accepted)
    assert sc.sellerCompletedAt is not None
    assert sc.status == "accepted" # Status only changes to 'completed' when BOTH are done
    
    # 3. Buyer Complete
    bc = repo.mark_buyer_complete(sc)
    assert bc.buyerCompletedAt is not None
    assert bc.status == "completed"


def test_cancelled_order_cleanup(repo: OrderRepository, setup_data, db_session: Session):
    """Test deleting cancelled orders outside the retention window."""
    data = setup_data
    now = datetime.now(timezone.utc)

    stale_order = repo.create(
        OrderCreate(listing_id=data["listing"].id, proposed_price=100),
        buyer_id=data["buyer"].id,
        seller_id=data["seller"].id,
    )
    stale_order.status = "cancelled"
    stale_order.cancelledAt = now - timedelta(days=31)
    db_session.commit()

    fresh_order = repo.create(
        OrderCreate(listing_id=data["listing"].id, proposed_price=110),
        buyer_id=data["buyer"].id,
        seller_id=data["seller"].id,
    )
    fresh_order.status = "cancelled"
    fresh_order.cancelledAt = now - timedelta(days=5)
    db_session.commit()

    deleted = repo.delete_cancelled_orders(before=now - timedelta(days=30))

    assert deleted == 1
    remaining = repo.get_by_buyer(data["buyer"].id)
    assert len(remaining) == 1
    assert remaining[0].id == fresh_order.id


def test_delete_order(repo: OrderRepository, setup_data):
    """Test deleting an order."""
    data = setup_data
    order = repo.create(OrderCreate(listing_id=data["listing"].id, proposed_price=100), 
                        buyer_id=data["buyer"].id, seller_id=data["seller"].id)
    order_id = order.id

    repo.delete(order)
    assert repo.get(order_id) is None
