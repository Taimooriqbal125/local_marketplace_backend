import uuid
from decimal import Decimal
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.db.base_class import Base
from app.models.service_listing import ServiceListing
from app.models.user import User
from app.models.category import Category
from app.models.cities import City
from app.repositories.service_listing_repo import ServiceListingRepository
from app.schemas.services_listing import ServiceListingCreate, ServiceListingUpdate


@pytest.fixture(scope="function")
def db_session() -> Session:
    """Create a clean in-memory database for each test. (Geo functions handled in conftest.py)"""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def repo(db_session: Session) -> ServiceListingRepository:
    """Fixture to provide a ServiceListingRepository instance."""
    return ServiceListingRepository(db_session)


@pytest.fixture
def setup_data(db_session: Session):
    """Fixture to provide baseline entities."""
    user = User(email="seller@test.com", hashed_password="pw")
    cat = Category(name="Home", slug="home")
    city = City(name="London", slug="london", country="UK")
    db_session.add_all([user, cat, city])
    db_session.commit()
    return user, cat, city


def test_create_listing(repo: ServiceListingRepository, setup_data):
    """Test inserting a listing with location mapping."""
    user, cat, city = setup_data
    listing_in = ServiceListingCreate(
        category_id=cat.id,
        city_id=city.id,
        title="Plumbing",
        description="Fix pipes",
        price_type="hourly",
        price_amount=50.0,
        service_location="North London",
        service_radius_km=15.0,
        service_location_point={"latitude": 51.5, "longitude": -0.1}
    )
    
    created = repo.create(listing_in, seller_id=user.id)
    assert created.id is not None
    assert created.title == "Plumbing"
    assert created.priceAmount == 50.0
    assert created.sellerId == user.id


def test_get_filtered(repo: ServiceListingRepository, setup_data, db_session: Session):
    """Test complex filtering (status, category, search)."""
    user, cat, city = setup_data
    
    # 1. Active listing
    l1 = ServiceListing(
        sellerId=user.id, categoryId=cat.id, cityId=city.id,
        title="Gardening", status="active", priceAmount=30.0,
        serviceLocation="Loc", serviceRadiusKm=10.0
    )
    # 2. Draft listing
    l2 = ServiceListing(
        sellerId=user.id, categoryId=cat.id, cityId=city.id,
        title="Cleaning", status="draft", priceAmount=20.0,
        serviceLocation="Loc", serviceRadiusKm=10.0
    )
    db_session.add_all([l1, l2])
    db_session.commit()

    # Filter by status
    active_results, total = repo.get_filtered(status="active")
    assert total == 1
    assert active_results[0].title == "Gardening"

    # Filter by search term
    search_results, total = repo.get_filtered(search="Clean")
    assert total == 1
    assert search_results[0].title == "Cleaning"


def test_get_nearby(repo: ServiceListingRepository, setup_data, db_session: Session):
    """Test proximity search logic (with SQLite mock functions)."""
    user, cat, city = setup_data
    listing = ServiceListing(
        sellerId=user.id, categoryId=cat.id, cityId=city.id,
        title="Nearby", status="active", serviceRadiusKm=10.0,
        serviceLocation="Loc", service_location="POINT(-0.1 51.5)"
    )
    db_session.add(listing)
    db_session.commit()

    results, total = repo.get_nearby(
        latitude=51.5, longitude=-0.1, radius_km=10.0
    )
    
    assert total == 1
    assert results[0][0].title == "Nearby"
    # distance_km should be 5.0 (from our SQLite function mock)
    assert results[0][1] == 5.0


def test_update_listing(repo: ServiceListingRepository, setup_data, db_session: Session):
    """Test partial updates and mapping."""
    user, cat, city = setup_data
    listing = ServiceListing(
        sellerId=user.id, categoryId=cat.id, title="Old Title",
        serviceLocation="Loc", serviceRadiusKm=10.0
    )
    db_session.add(listing)
    db_session.commit()

    update_in = ServiceListingUpdate(title="New Title", is_negotiable=True)
    updated = repo.update(listing, update_in)

    assert updated.title == "New Title"
    assert updated.isNegotiable is True


def test_get_by_seller(repo: ServiceListingRepository, setup_data, db_session: Session):
    """Test fetching listings owned by a specific seller."""
    user, cat, city = setup_data
    listing = ServiceListing(
        sellerId=user.id, categoryId=cat.id, title="Seller List",
        serviceLocation="Loc", serviceRadiusKm=10.0
    )
    db_session.add(listing)
    db_session.commit()

    results = repo.get_by_seller(user.id)
    assert len(results) == 1
    assert results[0].title == "Seller List"
