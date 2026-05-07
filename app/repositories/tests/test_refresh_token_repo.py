import uuid
from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.db.base_class import Base
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.repositories.refresh_token_repo import RefreshTokenRepository


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
def repo(db_session: Session) -> RefreshTokenRepository:
    """Fixture to provide a RefreshTokenRepository instance."""
    return RefreshTokenRepository(db_session)


@pytest.fixture
def test_user(db_session: Session) -> User:
    """Fixture to provide a test user."""
    user = User(email="test@example.com", hashed_password="pw")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_create_token(repo: RefreshTokenRepository, test_user: User):
    """Test creating a new refresh token."""
    expires = datetime.now(timezone.utc) + timedelta(days=7)
    token = RefreshToken(
        user_id=test_user.id,
        token_hash="sample_hash",
        expires_at=expires
    )
    created = repo.create(token)

    assert created.id is not None
    assert created.token_hash == "sample_hash"
    assert created.user_id == test_user.id


def test_get_valid_by_token_hash(repo: RefreshTokenRepository, test_user: User):
    """Test fetching valid vs invalid tokens by hash."""
    now = datetime.now(timezone.utc)
    
    # 1. Valid token
    repo.create(RefreshToken(
        user_id=test_user.id,
        token_hash="valid",
        expires_at=now + timedelta(hours=1)
    ))
    
    # 2. Expired token
    repo.create(RefreshToken(
        user_id=test_user.id,
        token_hash="expired",
        expires_at=now - timedelta(hours=1)
    ))
    
    # 3. Revoked token
    revoked = repo.create(RefreshToken(
        user_id=test_user.id,
        token_hash="revoked",
        expires_at=now + timedelta(hours=1)
    ))
    repo.revoke(revoked)

    assert repo.get_valid_by_token_hash("valid") is not None
    assert repo.get_valid_by_token_hash("expired") is None
    assert repo.get_valid_by_token_hash("revoked") is None


def test_get_by_user(repo: RefreshTokenRepository, test_user: User):
    """Test fetching tokens by user ID with revocation filter."""
    repo.create(RefreshToken(user_id=test_user.id, token_hash="h1", expires_at=datetime.now(timezone.utc)))
    revoked = repo.create(RefreshToken(user_id=test_user.id, token_hash="h2", expires_at=datetime.now(timezone.utc)))
    repo.revoke(revoked)

    # All tokens
    assert len(repo.get_by_user(test_user.id)) == 2
    # Only active
    assert len(repo.get_by_user(test_user.id, include_revoked=False)) == 1


def test_revoke_all_for_user(repo: RefreshTokenRepository, test_user: User):
    """Test mass revocation."""
    repo.create(RefreshToken(user_id=test_user.id, token_hash="h1", expires_at=datetime.now(timezone.utc)))
    repo.create(RefreshToken(user_id=test_user.id, token_hash="h2", expires_at=datetime.now(timezone.utc)))
    
    count = repo.revoke_all_for_user(test_user.id)
    assert count == 2
    assert all(t.revoked for t in repo.get_by_user(test_user.id))


def test_delete_stale_tokens(repo: RefreshTokenRepository, test_user: User, db_session: Session):
    """Test cleanup of old tokens."""
    now = datetime.now(timezone.utc)
    
    # 1. Expired (stale)
    repo.create(RefreshToken(
        user_id=test_user.id,
        token_hash="expired_stale",
        expires_at=now - timedelta(days=31)
    ))
    
    # 2. Revoked long ago (stale)
    revoked_old = repo.create(RefreshToken(
        user_id=test_user.id,
        token_hash="revoked_stale",
        expires_at=now + timedelta(days=1)
    ))
    repo.revoke(revoked_old, revoked_at=now - timedelta(days=31))
    
    # 3. Valid (not stale)
    repo.create(RefreshToken(
        user_id=test_user.id,
        token_hash="valid_keep",
        expires_at=now + timedelta(days=1)
    ))

    deleted = repo.delete_stale_tokens(
        revoked_before=now - timedelta(days=30),
        expired_before=now - timedelta(days=30)
    )
    
    assert deleted == 2
    remaining = repo.get_all()
    assert len(remaining) == 1
    assert remaining[0].token_hash == "valid_keep"
