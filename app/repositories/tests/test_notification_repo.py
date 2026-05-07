import uuid
from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.models.notification import Notification
from app.schemas.notification import NotificationCreate, NotificationUpdate
from app.repositories.notification_repo import NotificationRepository


@pytest.fixture(scope="function")
def db_session() -> Session:
    """Create a clean in-memory database for each test."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    # Create only the required table for Notification tests
    Notification.__table__.create(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def repo(db_session: Session) -> NotificationRepository:
    """Fixture to provide a NotificationRepository instance."""
    return NotificationRepository(db_session)


def test_create_notification(repo: NotificationRepository):
    """Test creating a new notification."""
    user_id = uuid.uuid4()
    notif_in = NotificationCreate(
        user_id=user_id,
        type="order_requested",
        title="New Order",
        body="You have a new order request."
    )
    notif = repo.create(notif_in)

    assert notif.id is not None
    assert notif.userId == user_id
    assert notif.type == "order_requested"
    assert notif.isRead is False
    assert notif.readAt is None


def test_get_notification(repo: NotificationRepository):
    """Test fetching a specific notification by ID."""
    user_id = uuid.uuid4()
    created = repo.create(NotificationCreate(
        user_id=user_id,
        type="test",
        title="Title",
        body="Body"
    ))

    fetched = repo.get(created.id)
    assert fetched is not None
    assert fetched.id == created.id


def test_get_all_by_user(repo: NotificationRepository):
    """Test fetching all notifications for a user, sorted by recency."""
    user_id = uuid.uuid4()
    # Create 3 notifications
    repo.create(NotificationCreate(user_id=user_id, type="t1", title="T1", body="B1"))
    repo.create(NotificationCreate(user_id=user_id, type="t2", title="T2", body="B2"))
    
    # Another user
    repo.create(NotificationCreate(user_id=uuid.uuid4(), type="t3", title="T3", body="B3"))

    results = repo.get_all_by_user(user_id)
    assert len(results) == 2


def test_get_unread_by_user(repo: NotificationRepository):
    """Test fetching only unread notifications for a user."""
    user_id = uuid.uuid4()
    n1 = repo.create(NotificationCreate(user_id=user_id, type="t1", title="T1", body="B1"))
    n2 = repo.create(NotificationCreate(user_id=user_id, type="t2", title="T2", body="B2"))
    
    # Mark one as read
    repo.mark_as_read(n1)

    unread = repo.get_unread_by_user(user_id)
    assert len(unread) == 1
    assert unread[0].id == n2.id


def test_update_notification_mark_read(repo: NotificationRepository):
    """Test updating notification status via update method."""
    notif = repo.create(NotificationCreate(user_id=uuid.uuid4(), type="t", title="T", body="B"))
    assert notif.isRead is False

    updated = repo.update(notif, NotificationUpdate(is_read=True))
    assert updated.isRead is True
    assert updated.readAt is not None


def test_mark_as_read(repo: NotificationRepository):
    """Test marking a single notification as read."""
    notif = repo.create(NotificationCreate(user_id=uuid.uuid4(), type="t", title="T", body="B"))
    repo.mark_as_read(notif)
    
    assert notif.isRead is True
    assert notif.readAt is not None


def test_mark_all_as_read(repo: NotificationRepository):
    """Test marking all unread notifications for a user as read."""
    user_id = uuid.uuid4()
    repo.create(NotificationCreate(user_id=user_id, type="t1", title="T1", body="B1"))
    repo.create(NotificationCreate(user_id=user_id, type="t2", title="T2", body="B2"))
    
    updated_count = repo.mark_all_as_read(user_id)
    assert updated_count == 2

    # Calling again should return 0 (no unread notifications)
    assert repo.mark_all_as_read(user_id) == 0


def test_delete_notification(repo: NotificationRepository):
    """Test deleting a notification."""
    notif = repo.create(NotificationCreate(user_id=uuid.uuid4(), type="t", title="T", body="B"))
    notif_id = notif.id

    repo.delete(notif)
    assert repo.get(notif_id) is None


def test_delete_all_for_user(repo: NotificationRepository):
    """Test deleting all notifications for a user."""
    user_id = uuid.uuid4()
    repo.create(NotificationCreate(user_id=user_id, type="t1", title="T1", body="B1"))
    repo.create(NotificationCreate(user_id=user_id, type="t2", title="T2", body="B2"))

    count = repo.delete_all_for_user(user_id)
    assert count == 2
    assert len(repo.get_all_by_user(user_id)) == 0


def test_delete_expired_notifications(repo: NotificationRepository, db_session: Session):
    """Test deletion of old read/unread notifications."""
    user_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    
    # 1. Old read notification (expired)
    n_read_old = repo.create(NotificationCreate(user_id=user_id, type="r_old", title="RO", body="BO"))
    repo.mark_as_read(n_read_old)
    # Manually backdate readAt
    n_read_old.readAt = now - timedelta(days=31)
    db_session.commit()

    # 2. Recent read notification (not expired)
    n_read_new = repo.create(NotificationCreate(user_id=user_id, type="r_new", title="RN", body="BN"))
    repo.mark_as_read(n_read_new)
    n_read_new.readAt = now - timedelta(days=1)
    db_session.commit()

    # 3. Old unread notification (expired)
    n_unread_old = repo.create(NotificationCreate(user_id=user_id, type="u_old", title="UO", body="BO"))
    # Manually backdate created_at
    n_unread_old.created_at = now - timedelta(days=91)
    db_session.commit()

    # 4. Recent unread notification (not expired)
    repo.create(NotificationCreate(user_id=user_id, type="u_new", title="UN", body="BN"))

    # Run cleanup (default policy is usually 30 days read, 90 days unread - check settings or pass explicitly)
    deleted_count = repo.delete_expired_notifications(read_days=30, unread_days=90)
    
    assert deleted_count == 2
    all_notifs = repo.get_all_by_user(user_id)
    types = [n.type for n in all_notifs]
    assert "r_old" not in types
    assert "u_old" not in types
    assert "r_new" in types
    assert "u_new" in types
