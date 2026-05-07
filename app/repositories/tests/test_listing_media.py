import uuid
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.models.listing_media import ListingMedia
from app.schemas.listing_media import ListingMediaCreate, ListingMediaUpdate
from app.repositories.listing_media import ListingMediaRepository


@pytest.fixture(scope="function")
def db_session() -> Session:
    """Create a clean in-memory database for each test."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    # Create only the required table for ListingMedia tests
    ListingMedia.__table__.create(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def repo(db_session: Session) -> ListingMediaRepository:
    """Fixture to provide a ListingMediaRepository instance."""
    return ListingMediaRepository(db_session)


def test_create_media(repo: ListingMediaRepository):
    """Test creating a new media record."""
    listing_id = uuid.uuid4()
    media_in = ListingMediaCreate(
        listing_id=listing_id,
        image_url="https://example.com/image.jpg",
        sort_order=1,
        cloudinary_public_id="sample_id"
    )
    media = repo.create(media_in)

    assert media.id is not None
    assert media.listingId == listing_id
    assert media.imageUrl == "https://example.com/image.jpg"
    assert media.sortOrder == 1
    assert media.cloudinaryPublicId == "sample_id"


def test_get_media(repo: ListingMediaRepository):
    """Test fetching a specific media record by ID."""
    listing_id = uuid.uuid4()
    media_in = ListingMediaCreate(
        listing_id=listing_id,
        image_url="https://example.com/photo.png"
    )
    created = repo.create(media_in)

    fetched = repo.get(created.id)
    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.imageUrl == "https://example.com/photo.png"


def test_get_by_listing(repo: ListingMediaRepository):
    """Test fetching all media for a specific listing, ordered by sortOrder."""
    listing_id = uuid.uuid4()
    # Create media out of order
    repo.create(ListingMediaCreate(listing_id=listing_id, image_url="img2.jpg", sort_order=2))
    repo.create(ListingMediaCreate(listing_id=listing_id, image_url="img1.jpg", sort_order=1))
    
    # Create media for another listing
    repo.create(ListingMediaCreate(listing_id=uuid.uuid4(), image_url="img3.jpg", sort_order=1))

    results = repo.get_by_listing(listing_id)
    assert len(results) == 2
    assert results[0].imageUrl == "img1.jpg"
    assert results[1].imageUrl == "img2.jpg"


def test_update_media(repo: ListingMediaRepository):
    """Test updating an existing media record."""
    listing_id = uuid.uuid4()
    created = repo.create(ListingMediaCreate(listing_id=listing_id, image_url="old.jpg", sort_order=0))
    
    update_in = ListingMediaUpdate(image_url="new.jpg", sort_order=5)
    updated = repo.update(created, update_in)

    assert updated.imageUrl == "new.jpg"
    assert updated.sortOrder == 5


def test_delete_media(repo: ListingMediaRepository):
    """Test deleting a media record."""
    listing_id = uuid.uuid4()
    created = repo.create(ListingMediaCreate(listing_id=listing_id, image_url="delete.jpg"))
    media_id = created.id

    repo.delete(created)
    
    fetched = repo.get(media_id)
    assert fetched is None
