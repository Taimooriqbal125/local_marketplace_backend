import uuid
from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.db.base_class import Base
from app.models.otp_token import OTPToken, OTPPurpose
from app.repositories.otp_token_repo import OTPTokenRepository


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
def repo(db_session: Session) -> OTPTokenRepository:
    """Fixture to provide an OTPTokenRepository instance."""
    return OTPTokenRepository(db_session)


def test_create_otp(repo: OTPTokenRepository):
    """Test creating a new OTP token."""
    expires = datetime.now(timezone.utc) + timedelta(minutes=10)
    otp = OTPToken(
        email="user@example.com",
        otp_hash="hashed_code",
        purpose=OTPPurpose.SIGNUP_VERIFY,
        expires_at=expires,
        last_sent_at=datetime.now(timezone.utc) # Avoid non-portable server_default 'now()'
    )
    created = repo.create(otp)

    assert created.id is not None
    assert created.otp_hash == "hashed_code"
    assert created.used is False


def test_get_valid_otp(repo: OTPTokenRepository):
    """Test retrieving valid vs invalid OTP tokens."""
    now = datetime.now(timezone.utc)
    email = "test@example.com"
    purpose = OTPPurpose.RESET_PASSWORD

    # 1. Valid OTP
    repo.create(OTPToken(
        email=email, otp_hash="h1", purpose=purpose,
        expires_at=now + timedelta(minutes=5),
        last_sent_at=now
    ))

    # 2. Expired OTP
    repo.create(OTPToken(
        email=email, otp_hash="h2", purpose=purpose,
        expires_at=now - timedelta(minutes=5),
        last_sent_at=now
    ))

    # 3. Max attempts reached
    max_attempts = OTPToken(
        email=email, otp_hash="h3", purpose=purpose,
        expires_at=now + timedelta(minutes=5), attempts=5,
        last_sent_at=now
    )
    repo.create(max_attempts)

    valid = repo.get_valid_otp(email, purpose.value)
    assert valid is not None
    assert valid.otp_hash == "h1"


def test_mark_as_used(repo: OTPTokenRepository):
    """Test marking an OTP as used."""
    otp = repo.create(OTPToken(
        email="a@b.com", otp_hash="h", purpose=OTPPurpose.SIGNUP_VERIFY,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        last_sent_at=datetime.now(timezone.utc)
    ))
    
    repo.mark_as_used(otp)
    assert otp.used is True
    assert otp.used_at is not None


def test_increment_attempts(repo: OTPTokenRepository):
    """Test incrementing failed attempts."""
    otp = repo.create(OTPToken(
        email="a@b.com", otp_hash="h", purpose=OTPPurpose.SIGNUP_VERIFY,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        last_sent_at=datetime.now(timezone.utc)
    ))
    
    assert otp.attempts == 0
    repo.increment_attempts(otp)
    assert otp.attempts == 1


def test_delete_expired(repo: OTPTokenRepository):
    """Test batch deletion of stale OTPs."""
    now = datetime.now(timezone.utc)
    email = "cleanup@example.com"
    purpose = OTPPurpose.SIGNUP_VERIFY

    # Expired
    repo.create(OTPToken(email=email, otp_hash="1", purpose=purpose, expires_at=now - timedelta(minutes=1), last_sent_at=now))
    # Used
    used = repo.create(OTPToken(email=email, otp_hash="2", purpose=purpose, expires_at=now + timedelta(minutes=10), last_sent_at=now))
    repo.mark_as_used(used)
    # Valid
    repo.create(OTPToken(email=email, otp_hash="3", purpose=purpose, expires_at=now + timedelta(minutes=10), last_sent_at=now))

    count = repo.delete_expired(email, purpose.value)
    assert count == 2
    
    # Check what remains
    remaining = repo.db.query(OTPToken).filter(OTPToken.email == email).all()
    assert len(remaining) == 1
    assert remaining[0].otp_hash == "3"
