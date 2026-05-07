import uuid
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.db.base_class import Base
from app.models.category import Category
from app.schemas.category import CategoryCreate, CategoryUpdate
from app.repositories.category_repo import CategoryRepository


@pytest.fixture(scope="function")
def db_session() -> Session:
    """Create a clean in-memory database for each test."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    # Create only the required tables for Category tests
    Category.__table__.create(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def repo(db_session: Session) -> CategoryRepository:
    """Fixture to provide a CategoryRepository instance."""
    return CategoryRepository(db_session)


def test_create_category(repo: CategoryRepository):
    """Test creating a new category."""
    category_in = CategoryCreate(
        name="Electronics",
        slug="electronics",
        sort_order=1,
        is_active=True
    )
    category = repo.create(category_in)

    assert category.id is not None
    assert category.name == "Electronics"
    assert category.slug == "electronics"
    assert category.sort_order == 1
    assert category.is_active is True


def test_get_category(repo: CategoryRepository):
    """Test fetching a category by ID."""
    category_in = CategoryCreate(name="Furniture", slug="furniture")
    created = repo.create(category_in)

    fetched = repo.get(created.id)
    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.name == "Furniture"


def test_get_category_not_found(repo: CategoryRepository):
    """Test fetching a non-existent category."""
    random_id = uuid.uuid4()
    fetched = repo.get(random_id)
    assert fetched is None


def test_get_by_slug(repo: CategoryRepository):
    """Test fetching a category by slug."""
    category_in = CategoryCreate(name="Health", slug="health-and-fitness")
    created = repo.create(category_in)

    fetched = repo.get_by_slug("health-and-fitness")
    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.slug == "health-and-fitness"


def test_get_all(repo: CategoryRepository):
    """Test fetching a paginated list of categories."""
    # Create 3 categories
    for i in range(3):
        repo.create(CategoryCreate(name=f"Cat {i}", slug=f"cat-{i}"))

    all_cats = repo.get_all(skip=0, limit=10)
    assert len(all_cats) == 3

    paginated = repo.get_all(skip=1, limit=1)
    assert len(paginated) == 1
    assert paginated[0].slug == "cat-1"


def test_get_parent_categories(repo: CategoryRepository):
    """Test fetching only top-level categories."""
    parent = repo.create(CategoryCreate(name="Parent", slug="parent"))
    repo.create(CategoryCreate(name="Child", slug="child", parent_id=parent.id))

    parents = repo.get_parent_categories()
    assert len(parents) == 1
    assert parents[0].slug == "parent"


def test_get_children(repo: CategoryRepository):
    """Test fetching child categories for a parent."""
    parent = repo.create(CategoryCreate(name="Home", slug="home"))
    child1 = repo.create(CategoryCreate(name="Kitchen", slug="kitchen", parent_id=parent.id))
    child2 = repo.create(CategoryCreate(name="Bedroom", slug="bedroom", parent_id=parent.id))
    
    # Create another category that isn't a child
    repo.create(CategoryCreate(name="Outdoor", slug="outdoor"))

    children = repo.get_children(parent.id)
    assert len(children) == 2
    slugs = [c.slug for c in children]
    assert "kitchen" in slugs
    assert "bedroom" in slugs


def test_get_tree(repo: CategoryRepository):
    """Test fetching the full tree (all children) for a parent."""
    parent = repo.create(CategoryCreate(name="Tech", slug="tech"))
    repo.create(CategoryCreate(name="AI", slug="ai", parent_id=parent.id))
    repo.create(CategoryCreate(name="Web", slug="web", parent_id=parent.id))

    tree = repo.get_tree(parent.id)
    assert len(tree) == 2


def test_update_category(repo: CategoryRepository):
    """Test updating an existing category."""
    created = repo.create(CategoryCreate(name="Old Name", slug="old-slug"))
    
    update_in = CategoryUpdate(name="New Name", is_active=False)
    updated = repo.update(created, update_in)

    assert updated.name == "New Name"
    assert updated.slug == "old-slug"  # Slug should remain unchanged if not in update_in
    assert updated.is_active is False


def test_delete_category(repo: CategoryRepository):
    """Test deleting a category."""
    created = repo.create(CategoryCreate(name="To Delete", slug="to-delete"))
    category_id = created.id

    repo.delete(created)
    
    fetched = repo.get(category_id)
    assert fetched is None
