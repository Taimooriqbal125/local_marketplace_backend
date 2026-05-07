import uuid
from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.db.base_class import Base
from app.models.review import Review
from app.models.order import Order
from app.models.user import User
from app.models.profile import Profile
from app.models.category import Category
from app.models.service_listing import ServiceListing
from app.models.listing_media import ListingMedia
from app.schemas.review import ReviewCreate
from app.repositories.review_repo import ReviewRepository


@pytest.fixture(scope="function")
def db_session() -> Session:
    """Create a clean in-memory database with all required tables."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def repo(db_session: Session) -> ReviewRepository:
    return ReviewRepository(db_session)


@pytest.fixture
def setup_data(db_session: Session):
    """Helper to create minimum required related entities for Review tests."""
    # 1. Create Category
    cat = Category(name="Test Cat", slug="test-cat")
    db_session.add(cat)
    
    # 2. Create Seller & Buyer
    seller = User(email="seller@example.com", phone="123456", hashed_password="pw")
    buyer = User(email="buyer@example.com", phone="789012", hashed_password="pw")
    db_session.add_all([seller, buyer])
    db_session.flush()
    
    # 3. Create Profiles
    db_session.add_all([
        Profile(userId=seller.id, name="Seller Name"),
        Profile(userId=buyer.id, name="Buyer Name")
    ])
    
    # 4. Create Listing
    listing = ServiceListing(
        sellerId=seller.id,
        categoryId=cat.id,
        title="Service",
        serviceLocation="Loc",
        serviceRadiusKm=10.0,
        priceAmount=100.0,
        status="active"
    )
    db_session.add(listing)
    db_session.flush()

    # 5. Create Order
    order = Order(listingId=listing.id, buyerId=buyer.id, sellerId=seller.id, status="completed", proposedPrice=100)
    db_session.add(order)
    db_session.commit()
    
    return {
        "buyer": buyer,
        "seller": seller,
        "listing": listing,
        "order": order
    }


def test_create_review(repo: ReviewRepository, setup_data):
    """Test creating a new review."""
    data = setup_data
    review_in = ReviewCreate(
        order_id=data["order"].id,
        rating=5,
        comment="Great service!"
    )
    
    review = repo.create(review_in, reviewer_id=data["buyer"].id, reviewed_user_id=data["seller"].id)
    
    assert review.id is not None
    assert review.rating == 5
    assert review.comment == "Great service!"
    assert review.reviewed_user.profile.name == "Seller Name"


def test_get_review(repo: ReviewRepository, setup_data):
    """Test fetching a review by ID."""
    data = setup_data
    created = repo.create(ReviewCreate(order_id=data["order"].id, rating=4), 
                          reviewer_id=data["buyer"].id, reviewed_user_id=data["seller"].id)
    
    fetched = repo.get(created.id)
    assert fetched is not None
    assert fetched.id == created.id


def test_get_by_order(repo: ReviewRepository, setup_data):
    """Test fetching reviews for an order."""
    data = setup_data
    # Buyer reviews seller
    repo.create(ReviewCreate(order_id=data["order"].id, rating=5), 
                reviewer_id=data["buyer"].id, reviewed_user_id=data["seller"].id)
    # Seller reviews buyer
    repo.create(ReviewCreate(order_id=data["order"].id, rating=4), 
                reviewer_id=data["seller"].id, reviewed_user_id=data["buyer"].id)
    
    reviews = repo.get_by_order(data["order"].id)
    assert len(reviews) == 2


def test_get_received_by_user(repo: ReviewRepository, setup_data):
    """Test fetching reviews received by a user."""
    data = setup_data
    repo.create(ReviewCreate(order_id=data["order"].id, rating=5), 
                reviewer_id=data["buyer"].id, reviewed_user_id=data["seller"].id)
    
    received = repo.get_received_by_user(data["seller"].id)
    assert len(received) == 1
    assert received[0].rating == 5
    assert received[0].reviewer.profile.name == "Buyer Name"


def test_get_given_by_user(repo: ReviewRepository, setup_data):
    """Test fetching reviews authored by a user."""
    data = setup_data
    repo.create(ReviewCreate(order_id=data["order"].id, rating=5), 
                reviewer_id=data["buyer"].id, reviewed_user_id=data["seller"].id)
    
    given = repo.get_given_by_user(data["buyer"].id)
    assert len(given) == 1
    assert given[0].rating == 5


def test_get_by_listing(repo: ReviewRepository, setup_data):
    """Test fetching reviews for a listing."""
    data = setup_data
    repo.create(ReviewCreate(order_id=data["order"].id, rating=5), 
                reviewer_id=data["buyer"].id, reviewed_user_id=data["seller"].id)
    
    reviews = repo.get_by_listing(data["listing"].id)
    assert len(reviews) == 1


def test_get_all_filtered(repo: ReviewRepository, setup_data):
    """Test admin filtering of reviews."""
    data = setup_data
    repo.create(ReviewCreate(order_id=data["order"].id, rating=3), 
                reviewer_id=data["buyer"].id, reviewed_user_id=data["seller"].id)
    
    all_notifs = repo.get_all_filtered(start_date=datetime.now(timezone.utc))
    assert len(all_notifs) == 0 # because they were created 'now', filter might be strict
    
    all_notifs = repo.get_all_filtered()
    assert len(all_notifs) == 1


def test_delete_review(repo: ReviewRepository, setup_data):
    """Test deleting a review."""
    data = setup_data
    review = repo.create(ReviewCreate(order_id=data["order"].id, rating=5), 
                        reviewer_id=data["buyer"].id, reviewed_user_id=data["seller"].id)
    review_id = review.id

    repo.delete(review)
    assert repo.get(review_id) is None
