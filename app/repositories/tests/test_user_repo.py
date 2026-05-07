import uuid
from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.db.base_class import Base
from app.models.user import User
from app.repositories.user_repo import UserRepository


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
def repo(db_session: Session) -> UserRepository:
    """Fixture to provide a UserRepository instance."""
    return UserRepository(db_session)


def test_create_user(repo: UserRepository):
    """Test inserting a new user."""
    user = User(email="new@test.com", hashed_password="pw")
    created = repo.create(user)
    assert created.id is not None
    assert created.email == "new@test.com"


def test_get_by_email(repo: UserRepository, db_session: Session):
    """Test user lookup by email."""
    email = "findme@test.com"
    db_session.add(User(email=email, hashed_password="pw"))
    db_session.commit()

    user = repo.get_by_email(email)
    assert user is not None
    assert user.email == email


def test_get_by_phone(repo: UserRepository, db_session: Session):
    """Test user lookup by phone."""
    phone = "123456789"
    db_session.add(User(email="phone@test.com", phone=phone, hashed_password="pw"))
    db_session.commit()

    user = repo.get_by_phone(phone)
    assert user is not None
    assert user.phone == phone


def test_get_all_filters(repo: UserRepository, db_session: Session):
    """Test paginated and filtered list."""
    u1 = User(email="u1@test.com", hashed_password="p", is_active=True, is_admin=False)
    u2 = User(email="u2@test.com", hashed_password="p", is_active=False, is_admin=True)
    db_session.add_all([u1, u2])
    db_session.commit()

    # Active only
    active = repo.get_all(is_active=True)
    assert len(active) == 1
    assert active[0].email == "u1@test.com"

    # Admin only
    admins = repo.get_all(is_admin=True)
    assert len(admins) == 1
    assert admins[0].email == "u2@test.com"


def test_touch_last_active(repo: UserRepository, db_session: Session):
    """Test throttling logic for updating activity timestamp."""
    user = User(email="active@test.com", hashed_password="p")
    db_session.add(user)
    db_session.commit()

    # 1. Initial touch
    repo.touch_last_active_if_stale(user)
    first_touch = user.last_active_at
    assert first_touch is not None

    # 2. Touch again immediately (should be stale-check-skipped)
    repo.touch_last_active_if_stale(user, min_interval=timedelta(minutes=10))
    assert user.last_active_at == first_touch

    # 3. Force update with small interval
    user.last_active_at = datetime.now(timezone.utc) - timedelta(minutes=11)
    repo.touch_last_active_if_stale(user, min_interval=timedelta(minutes=10))
    assert user.last_active_at > first_touch


def test_update_user(repo: UserRepository, db_session: Session):
    """Test updating user attributes."""
    user = User(email="old@test.com", hashed_password="p")
    db_session.add(user)
    db_session.commit()

    repo.update(user, {"email": "new@test.com", "is_admin": True})
    assert user.email == "new@test.com"
    assert user.is_admin is True
