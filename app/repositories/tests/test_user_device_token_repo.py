"""
Test suite for UserDeviceToken Repository.

Tests the database operations for user device tokens with comprehensive coverage
of CRUD operations, filtering, status management, and cleanup operations.
"""

import uuid
from datetime import datetime, timezone, timedelta
from typing import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.db.base_class import Base
from app.models.user import User
from app.models.user_device_tokens import UserDeviceToken
from app.repositories.user_device_token_repo import UserDeviceTokenRepository
from app.schemas.user_device_tokens import UserDeviceTokenCreate, UserDeviceTokenUpdate


# ─────────────────────────────────────────────────────────────────────────────
# FIXTURES
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    """
    Create a clean in-memory SQLite database for each test.

    Provides test isolation by creating a fresh database for each test function
    and cleaning up after the test completes.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()

    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def repo(db_session: Session) -> UserDeviceTokenRepository:
    """Fixture to provide a UserDeviceTokenRepository instance."""
    return UserDeviceTokenRepository(db_session)


@pytest.fixture
def test_user(db_session: Session) -> User:
    """Create a test user in the database."""
    user = User(email="test@example.com", hashed_password="securepassword")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_users(db_session: Session) -> list[User]:
    """Create multiple test users in the database."""
    users = [
        User(email=f"user{i}@example.com", hashed_password=f"password{i}")
        for i in range(1, 4)
    ]
    db_session.add_all(users)
    db_session.commit()
    for user in users:
        db_session.refresh(user)
    return users


@pytest.fixture
def sample_device_token_data() -> UserDeviceTokenCreate:
    """Provide sample device token creation data."""
    return UserDeviceTokenCreate(
        expo_push_token="ExponentPushToken[test_token_123]",
        device_type="android",
        device_name="Samsung Galaxy S21"
    )


@pytest.fixture
def sample_device_token_data_ios() -> UserDeviceTokenCreate:
    """Provide sample iOS device token creation data."""
    return UserDeviceTokenCreate(
        expo_push_token="ExponentPushToken[ios_token_456]",
        device_type="ios",
        device_name="iPhone 13"
    )


# ─────────────────────────────────────────────────────────────────────────────
# SINGLE RECORD LOOKUPS
# ─────────────────────────────────────────────────────────────────────────────

class TestGetById:
    """Tests for get() method - fetch token by ID."""

    def test_get_existing_token(
        self,
        repo: UserDeviceTokenRepository,
        test_user: User,
        sample_device_token_data: UserDeviceTokenCreate,
    ) -> None:
        """Test successful retrieval of an existing token by ID."""
        # Arrange: Create a device token
        created_token = repo.create(test_user.id, sample_device_token_data)

        # Act: Fetch the token by ID
        fetched_token = repo.get(created_token.id)

        # Assert: Verify the token is retrieved correctly
        assert fetched_token is not None
        assert fetched_token.id == created_token.id
        assert fetched_token.expo_push_token == "ExponentPushToken[test_token_123]"
        assert fetched_token.deviceType == "android"
        assert fetched_token.isActive is True

    def test_get_nonexistent_token(
        self,
        repo: UserDeviceTokenRepository,
    ) -> None:
        """Test that fetching a nonexistent token returns None."""
        # Arrange: Use a random ID that doesn't exist
        random_id = uuid.uuid4()

        # Act: Attempt to fetch non-existent token
        result = repo.get(random_id)

        # Assert: Verify None is returned
        assert result is None

    def test_get_after_deletion(
        self,
        repo: UserDeviceTokenRepository,
        test_user: User,
        sample_device_token_data: UserDeviceTokenCreate,
    ) -> None:
        """Test that a deleted token cannot be retrieved."""
        # Arrange: Create and delete a token
        created_token = repo.create(test_user.id, sample_device_token_data)
        repo.delete(created_token)

        # Act: Attempt to retrieve deleted token
        result = repo.get(created_token.id)

        # Assert: Verify None is returned
        assert result is None


class TestGetByToken:
    """Tests for get_by_token() method - fetch token by token string."""

    def test_get_by_token_existing(
        self,
        repo: UserDeviceTokenRepository,
        test_user: User,
        sample_device_token_data: UserDeviceTokenCreate,
    ) -> None:
        """Test successful retrieval of token by token string."""
        # Arrange: Create a device token
        token_string = "ExponentPushToken[test_token_123]"
        repo.create(test_user.id, sample_device_token_data)

        # Act: Fetch token by token string
        fetched_token = repo.get_by_token(token_string)

        # Assert: Verify correct token is retrieved
        assert fetched_token is not None
        assert fetched_token.expo_push_token == token_string
        assert fetched_token.userId == test_user.id

    def test_get_by_token_nonexistent(
        self,
        repo: UserDeviceTokenRepository,
    ) -> None:
        """Test that fetching nonexistent token string returns None."""
        # Act: Attempt to fetch non-existent token
        result = repo.get_by_token("NonexistentToken[xyz]")

        # Assert: Verify None is returned
        assert result is None

    @pytest.mark.parametrize("token_string", [
        "ExponentPushToken[long_valid_token_abc123def456]",
        "ExponentPushToken[short]",
        "ExponentPushToken[special_chars_!@#$%]",
    ])
    def test_get_by_token_various_formats(
        self,
        repo: UserDeviceTokenRepository,
        test_user: User,
        token_string: str,
    ) -> None:
        """Test token retrieval with various token string formats."""
        # Arrange: Create token with custom string
        token_data = UserDeviceTokenCreate(
            expo_push_token=token_string,
            device_type="android",
            device_name="Test Device"
        )
        repo.create(test_user.id, token_data)

        # Act: Retrieve by token string
        result = repo.get_by_token(token_string)

        # Assert: Verify retrieval succeeds
        assert result is not None
        assert result.expo_push_token == token_string


# ─────────────────────────────────────────────────────────────────────────────
# COLLECTION QUERIES
# ─────────────────────────────────────────────────────────────────────────────

class TestGetAllByUser:
    """Tests for get_all_by_user() method - fetch all tokens for a user."""

    def test_get_all_by_user_multiple_tokens(
        self,
        repo: UserDeviceTokenRepository,
        test_user: User,
        db_session: Session,
    ) -> None:
        """Test retrieving multiple tokens for a single user."""
        # Arrange: Create multiple tokens for same user
        token1_data = UserDeviceTokenCreate(
            expo_push_token="token1",
            device_type="android",
            device_name="Phone"
        )
        token2_data = UserDeviceTokenCreate(
            expo_push_token="token2",
            device_type="ios",
            device_name="Tablet"
        )
        repo.create(test_user.id, token1_data)
        repo.create(test_user.id, token2_data)

        # Act: Get all tokens for user
        tokens = repo.get_all_by_user(test_user.id, active_only=False)

        # Assert: Verify all tokens are returned
        assert len(tokens) == 2
        token_strings = {t.expo_push_token for t in tokens}
        assert "token1" in token_strings
        assert "token2" in token_strings

    def test_get_all_by_user_empty_result(
        self,
        repo: UserDeviceTokenRepository,
        test_user: User,
    ) -> None:
        """Test retrieving tokens for user with no tokens."""
        # Act: Get all tokens for user with no tokens
        tokens = repo.get_all_by_user(test_user.id)

        # Assert: Verify empty list is returned
        assert tokens == []

    def test_get_all_by_user_active_only_filter(
        self,
        repo: UserDeviceTokenRepository,
        test_user: User,
        db_session: Session,
    ) -> None:
        """Test filtering tokens by active status."""
        # Arrange: Create active and inactive tokens
        token1_data = UserDeviceTokenCreate(
            expo_push_token="active_token",
            device_type="android",
            device_name="Active Device"
        )
        token2_data = UserDeviceTokenCreate(
            expo_push_token="inactive_token",
            device_type="ios",
            device_name="Inactive Device"
        )
        token1 = repo.create(test_user.id, token1_data)
        token2 = repo.create(test_user.id, token2_data)

        # Deactivate token2
        repo.deactivate_token("inactive_token")

        # Act: Get only active tokens
        active_tokens = repo.get_all_by_user(test_user.id, active_only=True)

        # Assert: Verify only active token is returned
        assert len(active_tokens) == 1
        assert active_tokens[0].expo_push_token == "active_token"

    def test_get_all_by_user_includes_both_active_and_inactive(
        self,
        repo: UserDeviceTokenRepository,
        test_user: User,
        db_session: Session,
    ) -> None:
        """Test retrieving all tokens including inactive when active_only=False."""
        # Arrange: Create active and inactive tokens
        token1_data = UserDeviceTokenCreate(
            expo_push_token="active_token",
            device_type="android",
            device_name="Active"
        )
        token2_data = UserDeviceTokenCreate(
            expo_push_token="inactive_token",
            device_type="ios",
            device_name="Inactive"
        )
        repo.create(test_user.id, token1_data)
        repo.create(test_user.id, token2_data)
        repo.deactivate_token("inactive_token")

        # Act: Get all tokens regardless of active status
        all_tokens = repo.get_all_by_user(test_user.id, active_only=False)

        # Assert: Verify both active and inactive tokens are returned
        assert len(all_tokens) == 2

    def test_get_all_by_user_isolation_from_other_users(
        self,
        repo: UserDeviceTokenRepository,
        test_users: list[User],
    ) -> None:
        """Test that tokens from one user don't appear in another user's list."""
        # Arrange: Create tokens for different users
        user1, user2 = test_users[0], test_users[1]
        token_data_1 = UserDeviceTokenCreate(
            expo_push_token="user1_token",
            device_type="android",
            device_name="User1 Phone"
        )
        token_data_2 = UserDeviceTokenCreate(
            expo_push_token="user2_token",
            device_type="ios",
            device_name="User2 Phone"
        )
        repo.create(user1.id, token_data_1)
        repo.create(user2.id, token_data_2)

        # Act: Get tokens for user1
        user1_tokens = repo.get_all_by_user(user1.id, active_only=False)

        # Assert: Verify only user1's token is returned
        assert len(user1_tokens) == 1
        assert user1_tokens[0].expo_push_token == "user1_token"


# ─────────────────────────────────────────────────────────────────────────────
# WRITE OPERATIONS - CREATE
# ─────────────────────────────────────────────────────────────────────────────

class TestCreate:
    """Tests for create() method - insert new device token."""

    def test_create_basic_token(
        self,
        repo: UserDeviceTokenRepository,
        test_user: User,
        sample_device_token_data: UserDeviceTokenCreate,
    ) -> None:
        """Test successful creation of a new device token."""
        # Act: Create a device token
        created_token = repo.create(test_user.id, sample_device_token_data)

        # Assert: Verify token is created with correct attributes
        assert created_token.id is not None
        assert created_token.userId == test_user.id
        assert created_token.expo_push_token == "ExponentPushToken[test_token_123]"
        assert created_token.deviceType == "android"
        assert created_token.deviceName == "Samsung Galaxy S21"
        assert created_token.isActive is True
        assert created_token.created_at is not None

    def test_create_token_without_device_name(
        self,
        repo: UserDeviceTokenRepository,
        test_user: User,
    ) -> None:
        """Test creating a token without an optional device name."""
        # Arrange: Create token data without device_name
        token_data = UserDeviceTokenCreate(
            expo_push_token="ExponentPushToken[no_name_token]",
            device_type="ios",
            device_name=None
        )

        # Act: Create token
        created_token = repo.create(test_user.id, token_data)

        # Assert: Verify token is created with None device name
        assert created_token.deviceName is None

    def test_create_token_persists_in_db(
        self,
        repo: UserDeviceTokenRepository,
        test_user: User,
        sample_device_token_data: UserDeviceTokenCreate,
    ) -> None:
        """Test that created token persists in database."""
        # Act: Create a token
        created_token = repo.create(test_user.id, sample_device_token_data)

        # Act: Retrieve it immediately
        fetched_token = repo.get(created_token.id)

        # Assert: Verify token persisted
        assert fetched_token is not None
        assert fetched_token.expo_push_token == created_token.expo_push_token

    def test_create_multiple_tokens_for_same_user(
        self,
        repo: UserDeviceTokenRepository,
        test_user: User,
    ) -> None:
        """Test creating multiple tokens for the same user."""
        # Arrange: Prepare multiple token data
        token_data_1 = UserDeviceTokenCreate(
            expo_push_token="token_1",
            device_type="android",
            device_name="Phone"
        )
        token_data_2 = UserDeviceTokenCreate(
            expo_push_token="token_2",
            device_type="ios",
            device_name="iPad"
        )

        # Act: Create both tokens
        token1 = repo.create(test_user.id, token_data_1)
        token2 = repo.create(test_user.id, token_data_2)

        # Assert: Verify both tokens created with unique IDs
        assert token1.id != token2.id
        assert token1.expo_push_token == "token_1"
        assert token2.expo_push_token == "token_2"

    @pytest.mark.parametrize("device_type", [
        "android",
        "ios",
        "web",
        "macos",
        "windows"
    ])
    def test_create_token_various_device_types(
        self,
        repo: UserDeviceTokenRepository,
        test_user: User,
        device_type: str,
    ) -> None:
        """Test creating tokens for various device types."""
        # Arrange: Create token data with specific device type
        token_data = UserDeviceTokenCreate(
            expo_push_token=f"token_{device_type}",
            device_type=device_type,
            device_name=f"{device_type} Device"
        )

        # Act: Create token
        created_token = repo.create(test_user.id, token_data)

        # Assert: Verify device type is stored correctly
        assert created_token.deviceType == device_type


# ─────────────────────────────────────────────────────────────────────────────
# WRITE OPERATIONS - UPDATE
# ─────────────────────────────────────────────────────────────────────────────

class TestUpdate:
    """Tests for update() method - modify existing token."""

    def test_update_device_name(
        self,
        repo: UserDeviceTokenRepository,
        test_user: User,
        db_session: Session,
        sample_device_token_data: UserDeviceTokenCreate,
    ) -> None:
        """Test updating only the device name."""
        # Arrange: Create a token
        created_token = repo.create(test_user.id, sample_device_token_data)

        # Act: Update device name via direct attribute set (same approach as UserRepository)
        created_token.deviceName = "Updated Device Name"
        db_session.commit()
        fetched = repo.get(created_token.id)

        # Assert: Verify name was updated
        assert fetched.deviceName == "Updated Device Name"
        assert fetched.expo_push_token == sample_device_token_data.expo_push_token

    def test_update_is_active_status(
        self,
        repo: UserDeviceTokenRepository,
        test_user: User,
        db_session: Session,
        sample_device_token_data: UserDeviceTokenCreate,
    ) -> None:
        """Test updating the active/inactive status."""
        # Arrange: Create a token
        created_token = repo.create(test_user.id, sample_device_token_data)
        assert created_token.isActive is True

        # Act: Deactivate token via direct attribute set
        created_token.isActive = False
        db_session.commit()
        fetched = repo.get(created_token.id)

        # Assert: Verify status was updated
        assert fetched.isActive is False

    def test_update_last_used_at(
        self,
        repo: UserDeviceTokenRepository,
        test_user: User,
        db_session: Session,
        sample_device_token_data: UserDeviceTokenCreate,
    ) -> None:
        """Test updating the last used timestamp."""
        # Arrange: Create a token
        created_token = repo.create(test_user.id, sample_device_token_data)
        assert created_token.lastUsedAt is None

        # Act: Update last used timestamp via direct attribute set
        now = datetime.now(timezone.utc)
        created_token.lastUsedAt = now
        db_session.commit()
        fetched = repo.get(created_token.id)

        # Assert: Verify timestamp was updated
        assert fetched.lastUsedAt is not None
        assert fetched.lastUsedAt.date() == now.date()

    def test_update_multiple_fields(
        self,
        repo: UserDeviceTokenRepository,
        test_user: User,
        db_session: Session,
        sample_device_token_data: UserDeviceTokenCreate,
    ) -> None:
        """Test updating multiple fields in one operation."""
        # Arrange: Create a token
        created_token = repo.create(test_user.id, sample_device_token_data)

        # Act: Update multiple fields via direct attribute set
        now = datetime.now(timezone.utc)
        created_token.isActive = False
        created_token.lastUsedAt = now
        created_token.deviceName = "Multi-updated Device"
        db_session.commit()
        fetched = repo.get(created_token.id)

        # Assert: Verify all fields updated
        assert fetched.isActive is False
        assert fetched.lastUsedAt is not None
        assert fetched.deviceName == "Multi-updated Device"

    def test_update_with_partial_data(
        self,
        repo: UserDeviceTokenRepository,
        test_user: User,
        db_session: Session,
        sample_device_token_data: UserDeviceTokenCreate,
    ) -> None:
        """Test updating only specific fields leaving others unchanged."""
        # Arrange: Create a token with device name
        created_token = repo.create(test_user.id, sample_device_token_data)
        original_name = created_token.deviceName

        # Act: Update only is_active via direct attribute set
        created_token.isActive = False
        db_session.commit()
        fetched = repo.get(created_token.id)

        # Assert: Verify device name unchanged, status changed
        assert fetched.deviceName == original_name
        assert fetched.isActive is False

    def test_update_persists_changes(
        self,
        repo: UserDeviceTokenRepository,
        test_user: User,
        db_session: Session,
        sample_device_token_data: UserDeviceTokenCreate,
    ) -> None:
        """Test that update changes persist in database."""
        # Arrange: Create a token
        created_token = repo.create(test_user.id, sample_device_token_data)

        # Act: Update and retrieve
        created_token.deviceName = "Persistent Name"
        db_session.commit()
        fetched_token = repo.get(created_token.id)

        # Assert: Verify changes persisted
        assert fetched_token.deviceName == "Persistent Name"


# ─────────────────────────────────────────────────────────────────────────────
# WRITE OPERATIONS - DELETE
# ─────────────────────────────────────────────────────────────────────────────

class TestDelete:
    """Tests for delete() method - remove token record."""

    def test_delete_existing_token(
        self,
        repo: UserDeviceTokenRepository,
        test_user: User,
        sample_device_token_data: UserDeviceTokenCreate,
    ) -> None:
        """Test deleting an existing token."""
        # Arrange: Create a token
        created_token = repo.create(test_user.id, sample_device_token_data)

        # Act: Delete the token
        repo.delete(created_token)

        # Assert: Verify token no longer exists
        assert repo.get(created_token.id) is None

    def test_delete_removes_from_user_list(
        self,
        repo: UserDeviceTokenRepository,
        test_user: User,
        db_session: Session,
    ) -> None:
        """Test that deleted token no longer appears in user's token list."""
        # Arrange: Create two tokens, delete one
        token_data_1 = UserDeviceTokenCreate(
            expo_push_token="token_1",
            device_type="android",
            device_name="Phone"
        )
        token_data_2 = UserDeviceTokenCreate(
            expo_push_token="token_2",
            device_type="ios",
            device_name="Tablet"
        )
        token1 = repo.create(test_user.id, token_data_1)
        token2 = repo.create(test_user.id, token_data_2)

        # Act: Delete first token
        repo.delete(token1)

        # Act: Get remaining tokens
        remaining = repo.get_all_by_user(test_user.id, active_only=False)

        # Assert: Verify only one token remains
        assert len(remaining) == 1
        assert remaining[0].id == token2.id


# ─────────────────────────────────────────────────────────────────────────────
# SPECIAL OPERATIONS
# ─────────────────────────────────────────────────────────────────────────────

class TestDeactivateToken:
    """Tests for deactivate_token() method - mark token as inactive."""

    def test_deactivate_existing_token(
        self,
        repo: UserDeviceTokenRepository,
        test_user: User,
        sample_device_token_data: UserDeviceTokenCreate,
    ) -> None:
        """Test deactivating an active token."""
        # Arrange: Create an active token
        created_token = repo.create(test_user.id, sample_device_token_data)
        assert created_token.isActive is True

        # Act: Deactivate token
        result = repo.deactivate_token("ExponentPushToken[test_token_123]")

        # Assert: Verify deactivation was successful
        assert result is True
        fetched = repo.get_by_token("ExponentPushToken[test_token_123]")
        assert fetched.isActive is False

    def test_deactivate_already_inactive_token(
        self,
        repo: UserDeviceTokenRepository,
        test_user: User,
        sample_device_token_data: UserDeviceTokenCreate,
    ) -> None:
        """Test deactivating a token that's already inactive."""
        # Arrange: Create and deactivate a token
        created_token = repo.create(test_user.id, sample_device_token_data)
        token_string = "ExponentPushToken[test_token_123]"
        repo.deactivate_token(token_string)

        # Act: Deactivate again
        result = repo.deactivate_token(token_string)

        # Assert: Verify operation still succeeds
        assert result is True
        fetched = repo.get_by_token(token_string)
        assert fetched.isActive is False

    def test_deactivate_nonexistent_token(
        self,
        repo: UserDeviceTokenRepository,
    ) -> None:
        """Test deactivating a token that doesn't exist."""
        # Act: Attempt to deactivate non-existent token
        result = repo.deactivate_token("NonexistentToken[xyz]")

        # Assert: Verify False is returned
        assert result is False

    def test_deactivate_returns_true_on_success(
        self,
        repo: UserDeviceTokenRepository,
        test_user: User,
    ) -> None:
        """Test that deactivate returns True on successful deactivation."""
        # Arrange: Create a token
        token_data = UserDeviceTokenCreate(
            expo_push_token="test_token_success",
            device_type="android",
            device_name="Test"
        )
        repo.create(test_user.id, token_data)

        # Act: Deactivate token
        result = repo.deactivate_token("test_token_success")

        # Assert: Verify True is returned
        assert result is True


class TestUpdateLastUsed:
    """Tests for update_last_used() method - refresh usage timestamp."""

    def test_update_last_used_existing_token(
        self,
        repo: UserDeviceTokenRepository,
        test_user: User,
        sample_device_token_data: UserDeviceTokenCreate,
    ) -> None:
        """Test updating the last used timestamp for an active token."""
        # Arrange: Create a token with null lastUsedAt
        created_token = repo.create(test_user.id, sample_device_token_data)
        assert created_token.lastUsedAt is None

        # Act: Update last used timestamp
        result = repo.update_last_used("ExponentPushToken[test_token_123]")

        # Assert: Verify timestamp was updated
        assert result is True
        fetched = repo.get_by_token("ExponentPushToken[test_token_123]")
        assert fetched.lastUsedAt is not None

    def test_update_last_used_multiple_times(
        self,
        repo: UserDeviceTokenRepository,
        test_user: User,
        sample_device_token_data: UserDeviceTokenCreate,
    ) -> None:
        """Test updating last used timestamp multiple times."""
        # Arrange: Create a token
        token_string = "ExponentPushToken[test_token_123]"
        created_token = repo.create(test_user.id, sample_device_token_data)

        # Act: Update last used twice
        repo.update_last_used(token_string)
        first_update = repo.get_by_token(token_string).lastUsedAt

        import time
        time.sleep(0.01)  # Small delay to ensure different timestamps

        repo.update_last_used(token_string)
        second_update = repo.get_by_token(token_string).lastUsedAt

        # Assert: Verify second update is later
        assert second_update >= first_update

    def test_update_last_used_nonexistent_token(
        self,
        repo: UserDeviceTokenRepository,
    ) -> None:
        """Test updating last used for a nonexistent token."""
        # Act: Attempt to update non-existent token
        result = repo.update_last_used("NonexistentToken[xyz]")

        # Assert: Verify False is returned
        assert result is False

    def test_update_last_used_inactive_token(
        self,
        repo: UserDeviceTokenRepository,
        test_user: User,
        sample_device_token_data: UserDeviceTokenCreate,
    ) -> None:
        """Test that last used can be updated on inactive tokens."""
        # Arrange: Create and deactivate a token
        token_string = "ExponentPushToken[test_token_123]"
        repo.create(test_user.id, sample_device_token_data)
        repo.deactivate_token(token_string)

        # Act: Update last used on inactive token
        result = repo.update_last_used(token_string)

        # Assert: Verify operation succeeds
        assert result is True
        fetched = repo.get_by_token(token_string)
        assert fetched.lastUsedAt is not None


# ─────────────────────────────────────────────────────────────────────────────
# CLEANUP OPERATIONS
# ─────────────────────────────────────────────────────────────────────────────

class TestDeleteInactiveTokens:
    """Tests for delete_inactive_tokens() method - cleanup old inactive tokens."""

    def test_delete_inactive_tokens_before_date(
        self,
        repo: UserDeviceTokenRepository,
        test_user: User,
        db_session: Session,
    ) -> None:
        """Test deleting inactive tokens older than cutoff date."""
        # Arrange: Create active and inactive tokens with old timestamps
        old_time = datetime.now(timezone.utc) - timedelta(days=30)

        token_data_1 = UserDeviceTokenCreate(
            expo_push_token="old_inactive_token",
            device_type="android",
            device_name="Old Phone"
        )
        token_data_2 = UserDeviceTokenCreate(
            expo_push_token="recent_inactive_token",
            device_type="ios",
            device_name="Recent Phone"
        )

        # Create tokens
        old_token = repo.create(test_user.id, token_data_1)
        recent_token = repo.create(test_user.id, token_data_2)
        old_token_id = old_token.id
        recent_token_id = recent_token.id

        # Make both inactive
        repo.deactivate_token("old_inactive_token")
        repo.deactivate_token("recent_inactive_token")

        # Manually set old_token's created_at to old date
        old_token.created_at = old_time
        db_session.commit()

        # Act: Delete inactive tokens before cutoff
        cutoff = datetime.now(timezone.utc) - timedelta(days=10)
        deleted_count = repo.delete_inactive_tokens(cutoff)

        # Assert: Verify old token was deleted, recent kept
        assert deleted_count == 1
        assert repo.get(old_token_id) is None
        assert repo.get(recent_token_id) is not None

    def test_delete_inactive_tokens_uses_last_used_at_if_available(
        self,
        repo: UserDeviceTokenRepository,
        test_user: User,
        db_session: Session,
    ) -> None:
        """Test that lastUsedAt is preferred over created_at for deletion."""
        # Arrange: Create token and set last used to old time
        old_time = datetime.now(timezone.utc) - timedelta(days=30)

        token_data = UserDeviceTokenCreate(
            expo_push_token="old_use_token",
            device_type="android",
            device_name="Test"
        )
        token = repo.create(test_user.id, token_data)
        token_id = token.id
        repo.deactivate_token("old_use_token")

        # Set lastUsedAt to old time
        token.lastUsedAt = old_time
        db_session.commit()

        # Act: Delete inactive tokens before cutoff
        cutoff = datetime.now(timezone.utc) - timedelta(days=10)
        deleted_count = repo.delete_inactive_tokens(cutoff)

        # Assert: Verify token was deleted based on lastUsedAt
        assert deleted_count == 1
        assert repo.get(token_id) is None

    def test_delete_inactive_tokens_preserves_active(
        self,
        repo: UserDeviceTokenRepository,
        test_user: User,
        db_session: Session,
    ) -> None:
        """Test that active tokens are not deleted."""
        # Arrange: Create multiple tokens with mixed status
        old_time = datetime.now(timezone.utc) - timedelta(days=30)
        token_ids = []
        
        for i in range(3):
            token_data = UserDeviceTokenCreate(
                expo_push_token=f"token_{i}",
                device_type="android",
                device_name=f"Device {i}"
            )
            token = repo.create(test_user.id, token_data)
            token_ids.append(token.id)

        # Make first two inactive and set to old time
        for i in range(2):
            repo.deactivate_token(f"token_{i}")
            # Get token and set created_at to old time
            token = repo.get_by_token(f"token_{i}")
            token.created_at = old_time
            db_session.commit()

        # Act: Delete old inactive tokens
        cutoff = datetime.now(timezone.utc) - timedelta(days=10)
        deleted_count = repo.delete_inactive_tokens(cutoff)

        # Assert: Verify inactive tokens deleted, active preserved
        assert deleted_count == 2  # First two should be deleted
        remaining = repo.get_all_by_user(test_user.id, active_only=False)
        # Remaining should include only the active token
        assert len(remaining) == 1
        assert remaining[0].isActive is True
        assert remaining[0].expo_push_token == "token_2"

    def test_delete_inactive_tokens_empty_database(
        self,
        repo: UserDeviceTokenRepository,
    ) -> None:
        """Test deleting inactive tokens from empty database."""
        # Act: Delete from empty database
        cutoff = datetime.now(timezone.utc)
        deleted_count = repo.delete_inactive_tokens(cutoff)

        # Assert: Verify no error, 0 deleted
        assert deleted_count == 0

    def test_delete_inactive_tokens_with_null_last_used_at(
        self,
        repo: UserDeviceTokenRepository,
        test_user: User,
        db_session: Session,
    ) -> None:
        """Test deletion logic when lastUsedAt is NULL (falls back to created_at)."""
        # Arrange: Create inactive token with null lastUsedAt
        old_time = datetime.now(timezone.utc) - timedelta(days=30)

        token_data = UserDeviceTokenCreate(
            expo_push_token="null_last_used_token",
            device_type="android",
            device_name="Test"
        )
        token = repo.create(test_user.id, token_data)
        token_id = token.id
        repo.deactivate_token("null_last_used_token")

        # Verify lastUsedAt is null and set created_at to old
        assert token.lastUsedAt is None
        token.created_at = old_time
        db_session.commit()

        # Act: Delete inactive tokens with old cutoff
        cutoff = datetime.now(timezone.utc) - timedelta(days=10)
        deleted_count = repo.delete_inactive_tokens(cutoff)

        # Assert: Verify token deleted based on created_at fallback
        assert deleted_count == 1
        assert repo.get(token_id) is None

    def test_delete_inactive_tokens_no_change_for_recent(
        self,
        repo: UserDeviceTokenRepository,
        test_user: User,
    ) -> None:
        """Test that recently created inactive tokens are not deleted."""
        # Arrange: Create new inactive token
        token_data = UserDeviceTokenCreate(
            expo_push_token="recent_token",
            device_type="android",
            device_name="Recent Device"
        )
        token = repo.create(test_user.id, token_data)
        token_id = token.id
        repo.deactivate_token("recent_token")

        # Act: Try to delete with past cutoff date (recent tokens won't qualify)
        # If cutoff is now - 10 days, tokens created now (after the cutoff) won't be deleted
        cutoff = datetime.now(timezone.utc) - timedelta(days=10)
        deleted_count = repo.delete_inactive_tokens(cutoff)

        # Assert: Verify token is not deleted because it's recent (created after cutoff)
        assert deleted_count == 0
        assert repo.get(token_id) is not None


# ─────────────────────────────────────────────────────────────────────────────
# EDGE CASES AND DATA CONSISTENCY
# ─────────────────────────────────────────────────────────────────────────────

class TestDataConsistency:
    """Tests for data integrity and edge cases."""

    def test_token_uniqueness_constraint(
        self,
        repo: UserDeviceTokenRepository,
        test_user: User,
    ) -> None:
        """Test that duplicate tokens cannot be created (uniqueness constraint)."""
        # Arrange: Create first token
        token_data = UserDeviceTokenCreate(
            expo_push_token="unique_token",
            device_type="android",
            device_name="Phone"
        )
        repo.create(test_user.id, token_data)

        # Act & Assert: Attempt to create duplicate should fail
        with pytest.raises(Exception):  # SQLAlchemy IntegrityError
            repo.create(test_user.id, token_data)

    def test_user_deletion_removes_tokens(
        self,
        repo: UserDeviceTokenRepository,
        db_session: Session,
        sample_device_token_data: UserDeviceTokenCreate,
    ) -> None:
        """Test that tokens are properly associated with users."""
        # Arrange: Create user and token
        user = User(email="removal@example.com", hashed_password="securepassword")
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        
        token = repo.create(user.id, sample_device_token_data)
        token_id = token.id

        # Act: Manually delete token before user deletion
        repo.delete(token)

        # Act & Assert: User can now be deleted without foreign key conflict
        db_session.delete(user)
        db_session.commit()  # Should not raise constraint error

        # Assert: Verify token is gone
        assert repo.get(token_id) is None

    def test_timestamps_are_set_on_creation(
        self,
        repo: UserDeviceTokenRepository,
        test_user: User,
        sample_device_token_data: UserDeviceTokenCreate,
    ) -> None:
        """Test that created_at and updated_at are automatically set."""
        # Act: Create token
        created_token = repo.create(test_user.id, sample_device_token_data)

        # Assert: Verify timestamps exist
        assert created_token.created_at is not None
        assert created_token.updated_at is not None

    def test_get_all_by_user_with_nonexistent_user_id(
        self,
        repo: UserDeviceTokenRepository,
    ) -> None:
        """Test querying tokens for a user that doesn't exist."""
        # Act: Query with non-existent user ID
        tokens = repo.get_all_by_user(uuid.uuid4())

        # Assert: Verify empty list returned (no error)
        assert tokens == []
