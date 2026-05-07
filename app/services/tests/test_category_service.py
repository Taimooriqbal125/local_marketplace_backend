"""
Unit tests for Category Service.
Focuses on business logic, validation, and interaction with the Repository layer.
"""

import uuid
from datetime import datetime
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import app.services.category_service as category_service_module
from app.services.category_service import CategoryService, CategoryNotFoundError, CategoryConflictError
from app.schemas.category import CategoryCreate, CategoryUpdate


class MockCategory:
    """
    Mock database model for testing.
    Pydantic's from_attributes/model_validate requires objects to have attributes 
    that match the schema fields.
    """
    def __init__(self, **kwargs):
        self.id = kwargs.get("id", uuid.uuid4())
        self.name = kwargs.get("name", "Test Category")
        self.slug = kwargs.get("slug", "test-category")
        self.sort_order = kwargs.get("sort_order", 0)
        self.is_active = kwargs.get("is_active", True)
        self.parent_id = kwargs.get("parent_id", None)
        self.created_at = kwargs.get("created_at", datetime.now())
        self.updated_at = kwargs.get("updated_at", datetime.now())
        # To handle recursively building children in get_category_tree
        self.children = kwargs.get("children", [])
        
        # Add any other kwargs directly to the instance
        for key, value in kwargs.items():
            setattr(self, key, value)


@pytest.fixture
def db_session():
    """Mock database session."""
    return MagicMock(spec=Session)


@pytest.fixture
def category_service(db_session):
    """CategoryService instance with mocked repository."""
    service = CategoryService(db_session)
    # We replace the real repository with a mock to isolate the service logic
    service.repo = MagicMock()
    return service


# ── GET Tests ─────────────────────────────────────────────────────────────

def test_get_category_success(category_service):
    """Test fetching a category successfully."""
    # Arrange
    cat_id = uuid.uuid4()
    mock_cat = MockCategory(id=cat_id)
    category_service.repo.get.return_value = mock_cat

    # Act
    result = category_service.get_category(cat_id)

    # Assert
    assert result.id == cat_id
    assert result.name == mock_cat.name
    category_service.repo.get.assert_called_once_with(cat_id)


def test_get_category_not_found(category_service):
    """Test fetching a non-existent category raises CategoryNotFoundError."""
    # Arrange
    cat_id = uuid.uuid4()
    category_service.repo.get.return_value = None

    # Act & Assert
    with pytest.raises(CategoryNotFoundError):
        category_service.get_category(cat_id)


def test_get_category_by_slug_success(category_service):
    """Test fetching a category by slug successfully."""
    # Arrange
    slug = "electronics"
    mock_cat = MockCategory(slug=slug)
    category_service.repo.get_by_slug.return_value = mock_cat

    # Act
    result = category_service.get_category_by_slug(slug)

    # Assert
    assert result.slug == slug
    category_service.repo.get_by_slug.assert_called_once_with(slug)


# ── CREATE Tests ──────────────────────────────────────────────────────────

def test_create_category_success(category_service):
    """Test creating a category successfully."""
    # Arrange
    obj_in = CategoryCreate(name="New Category", slug="new-category")
    mock_cat = MockCategory(id=uuid.uuid4(), name=obj_in.name, slug=obj_in.slug)
    category_service.repo.get_by_slug.return_value = None
    category_service.repo.create.return_value = mock_cat

    # Act
    result = category_service.create_category(obj_in)

    # Assert
    assert result.name == obj_in.name
    assert result.slug == obj_in.slug
    category_service.repo.get_by_slug.assert_called_once_with(obj_in.slug)
    category_service.repo.create.assert_called_once_with(obj_in)


def test_create_category_slug_conflict(category_service):
    """Test creating a category with an existing slug raises CategoryConflictError."""
    # Arrange
    obj_in = CategoryCreate(name="Conflict", slug="conflict")
    category_service.repo.get_by_slug.return_value = MockCategory()

    # Act & Assert
    with pytest.raises(CategoryConflictError, match="already exists"):
        category_service.create_category(obj_in)


def test_create_category_integrity_error(category_service):
    """Test that database IntegrityError is translated to CategoryConflictError."""
    # Arrange
    obj_in = CategoryCreate(name="DB Fail", slug="db-fail")
    category_service.repo.get_by_slug.return_value = None
    category_service.repo.create.side_effect = IntegrityError(None, None, None)

    # Act & Assert
    with pytest.raises(CategoryConflictError):
        category_service.create_category(obj_in)


# ── UPDATE Tests ──────────────────────────────────────────────────────────

def test_update_category_success(category_service):
    """Test updating a category successfully."""
    # Arrange
    cat_id = uuid.uuid4()
    obj_in = CategoryUpdate(name="Updated Name")
    existing_cat = MockCategory(id=cat_id, name="Old Name")
    updated_cat = MockCategory(id=cat_id, name="Updated Name")
    
    category_service.repo.get.return_value = existing_cat
    category_service.repo.update.return_value = updated_cat

    # Act
    result = category_service.update_category(cat_id, obj_in)

    # Assert
    assert result.name == "Updated Name"
    category_service.repo.update.assert_called_once()


def test_update_category_not_found(category_service):
    """Test updating a non-existent category raises CategoryNotFoundError."""
    # Arrange
    cat_id = uuid.uuid4()
    category_service.repo.get.return_value = None

    # Act & Assert
    with pytest.raises(CategoryNotFoundError):
        category_service.update_category(cat_id, CategoryUpdate(name="Fail"))


# ── DELETE Tests ──────────────────────────────────────────────────────────

def test_delete_category_success(category_service):
    """Test deleting a category successfully."""
    # Arrange
    cat_id = uuid.uuid4()
    mock_cat = MockCategory(id=cat_id)
    category_service.repo.get.return_value = mock_cat

    # Act
    category_service.delete_category(cat_id)

    # Assert
    category_service.repo.delete.assert_called_once_with(mock_cat)


# ── TREE Tests ────────────────────────────────────────────────────────────

def test_get_category_tree(category_service):
    """Test building the full category tree hierarchy from a flat list."""
    # Arrange
    parent_id = uuid.uuid4()
    child_id = uuid.uuid4()
    
    # Mock data: 1 parent, 1 child
    all_cats = [
        MockCategory(id=parent_id, name="Parent", parent_id=None),
        MockCategory(id=child_id, name="Child", parent_id=parent_id),
    ]
    category_service.repo.get_all.return_value = all_cats

    # Act
    tree = category_service.get_category_tree()

    # Assert
    assert len(tree) == 1
    assert tree[0].id == parent_id
    assert len(tree[0].children) == 1
    assert tree[0].children[0].id == child_id
    assert tree[0].children[0].name == "Child"


# ── LISTING Tests ─────────────────────────────────────────────────────────

def test_list_categories(category_service):
    """Test listing categories with pagination."""
    # Arrange
    mock_cats = [MockCategory(), MockCategory()]
    category_service.repo.get_all.return_value = mock_cats

    # Act
    result = category_service.list_categories(skip=0, limit=10)

    # Assert
    assert len(result) == 2
    category_service.repo.get_all.assert_called_once_with(skip=0, limit=10)


def test_list_categories_uses_cache(category_service, monkeypatch):
    """Test cached category listings bypass the repository."""
    cached_category = MockCategory(name="Cached Category", slug="cached-category")

    monkeypatch.setattr(
        category_service_module,
        "get_cache_sync",
        lambda key: [
            {
                "id": str(cached_category.id),
                "name": cached_category.name,
                "slug": cached_category.slug,
                "sort_order": cached_category.sort_order,
                "is_active": cached_category.is_active,
                "parent_id": None,
                "created_at": cached_category.created_at.isoformat(),
                "updated_at": cached_category.updated_at.isoformat(),
            }
        ],
    )

    result = category_service.list_categories(skip=0, limit=10)

    assert len(result) == 1
    assert result[0].slug == "cached-category"
    category_service.repo.get_all.assert_not_called()


def test_create_category_invalidates_cache(category_service, monkeypatch):
    """Test category writes invalidate cached category lists."""
    invalidated_patterns = []

    monkeypatch.setattr(category_service_module, "delete_cache_pattern_sync", invalidated_patterns.append)
    category_service.repo.get_by_slug.return_value = None
    category_service.repo.create.return_value = MockCategory(name="New Category", slug="new-category")

    category_service.create_category(CategoryCreate(name="New Category", slug="new-category"))

    assert invalidated_patterns == ["categories:*"]


def test_list_parent_categories(category_service):
    """Test listing only parent categories."""
    # Arrange
    mock_cats = [MockCategory(parent_id=None)]
    category_service.repo.get_parent_categories.return_value = mock_cats

    # Act
    result = category_service.list_parent_categories()

    # Assert
    assert len(result) == 1
    category_service.repo.get_parent_categories.assert_called_once()


def test_list_categories_by_parent_success(category_service):
    """Test listing child categories for a valid parent."""
    # Arrange
    parent_id = uuid.uuid4()
    category_service.repo.get.return_value = MockCategory(id=parent_id)
    category_service.repo.get_children.return_value = [MockCategory(parent_id=parent_id)]

    # Act
    result = category_service.list_categories_by_parent(parent_id)

    # Assert
    assert len(result) == 1
    category_service.repo.get_children.assert_called_once()


def test_list_categories_by_parent_not_found(category_service):
    """Test listing child categories for a non-existent parent raises 404."""
    # Arrange
    parent_id = uuid.uuid4()
    category_service.repo.get.return_value = None

    # Act & Assert
    with pytest.raises(CategoryNotFoundError, match="Parent category not found"):
        category_service.list_categories_by_parent(parent_id)


# ── ADMIN Tests ───────────────────────────────────────────────────────────

def test_get_category_admin_success(category_service):
    """Test fetching category details for admin (includes children attribute)."""
    # Arrange
    cat_id = uuid.uuid4()
    mock_cat = MockCategory(id=cat_id)
    category_service.repo.get.return_value = mock_cat

    # Act
    result = category_service.get_category_admin(cat_id)

    # Assert
    assert result.id == cat_id
    # TreeOut includes children list
    assert hasattr(result, "children")
