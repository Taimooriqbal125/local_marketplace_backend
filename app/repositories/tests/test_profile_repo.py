import uuid
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.db.base_class import Base
from app.models.profile import Profile
from app.models.user import User
from app.repositories.profile_repo import ProfileRepository
from app.schemas.profile import ProfileCreate, ProfileUpdate


@pytest.fixture(scope="function")
def db_session() -> Session:
    """Create a clean in-memory database for each test."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def repo(db_session: Session) -> ProfileRepository:
    """Fixture to provide a ProfileRepository instance."""
    return ProfileRepository(db_session)


@pytest.fixture
def test_user(db_session: Session) -> User:
    """Fixture to provide a test user."""
    user = User(email="profile_test@example.com", hashed_password="pw")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_create_profile(repo: ProfileRepository, test_user: User):
    """Test creating a profile with explicit mapping and Geo conversion."""
    profile_in = ProfileCreate(
        user_id=test_user.id,
        name="Test Profile",
        photo_url="http://photo.com",
        last_location_point={"latitude": 10.0, "longitude": 20.0}
    )
    created = repo.create(profile_in)

    assert created.userId == test_user.id
    assert created.name == "Test Profile"
    assert created.photoUrl == "http://photo.com"
    # Even if WKTElement is mocked as String, it should have been set
    assert created.last_location_point is not None


def test_get_by_user_id(repo: ProfileRepository, test_user: User, db_session: Session):
    """Test fetching profile by user ID with relations."""
    profile = Profile(userId=test_user.id, name="Fetch Me")
    db_session.add(profile)
    db_session.commit()

    fetched = repo.get_by_user_id(test_user.id)
    assert fetched is not None
    assert fetched.name == "Fetch Me"
    assert fetched.user.id == test_user.id


def test_update_profile(repo: ProfileRepository, test_user: User, db_session: Session):
    """Test updating profile fields and Geo coordinates."""
    profile = Profile(userId=test_user.id, name="Old Name")
    db_session.add(profile)
    db_session.commit()

    update_in = ProfileUpdate(
        name="New Name",
        default_location_point={"latitude": 5.0, "longitude": 15.0}
    )
    updated = repo.update(profile, update_in)

    assert updated.name == "New Name"
    assert updated.default_location_point is not None


def test_increment_seller_orders_count(repo: ProfileRepository, test_user: User, db_session: Session):
    """Test atomic increment of completed orders."""
    profile = Profile(userId=test_user.id, name="Seller", sellerCompletedOrdersCount=5)
    db_session.add(profile)
    db_session.commit()

    repo.increment_seller_orders_count(test_user.id)
    db_session.refresh(profile)
    assert profile.sellerCompletedOrdersCount == 6


def test_update_seller_rating(repo: ProfileRepository, test_user: User, db_session: Session):
    """Test average rating calculation."""
    # Start with 2 ratings totaling 8 (avg 4.0)
    profile = Profile(
        userId=test_user.id, 
        name="Rated", 
        sellerRatingAvg=4.0, 
        sellerRatingCount=2
    )
    db_session.add(profile)
    db_session.commit()

    # New rating 1 -> (8+1)/3 = 3.0
    repo.update_seller_rating(test_user.id, 1)
    db_session.refresh(profile)
    
    assert profile.sellerRatingCount == 3
    assert float(profile.sellerRatingAvg) == 3.0


def test_get_all_with_filters(repo: ProfileRepository, db_session: Session):
    """Test filtering by status, banning, and sorting."""
    u1 = User(email="u1@test.com", hashed_password="p")
    u2 = User(email="u2@test.com", hashed_password="p")
    db_session.add_all([u1, u2])
    db_session.commit()

    p1 = Profile(userId=u1.id, name="A", sellerCompletedOrdersCount=10, sellerRatingAvg=4.5)
    p2 = Profile(userId=u2.id, name="B", sellerCompletedOrdersCount=20, sellerRatingAvg=4.8, isBanned=True)
    db_session.add_all([p1, p2])
    db_session.commit()

    # Filter by banned
    banned = repo.get_all(is_banned=True)
    assert len(banned) == 1
    assert banned[0].name == "B"

    # Sort by selling
    selling = repo.get_all(top_selling=True)
    assert selling[0].name == "B"
    assert selling[1].name == "A"
