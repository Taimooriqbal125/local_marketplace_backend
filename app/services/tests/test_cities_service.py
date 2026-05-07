"""
Unit tests for City Service.
Focuses on business logic, validation, and interaction with the Repository layer.
"""

import uuid
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import app.services.cities_service as cities_service_module
from app.services.cities_service import CityService, CityNotFoundError, CityConflictError
from app.schemas.cities import CityCreate, CityUpdate


class MockCity:
    """
    Mock database model for testing.
    Pydantic's from_attributes/model_validate requires objects to have attributes 
    that match the schema fields.
    """
    def __init__(self, **kwargs):
        self.id = kwargs.get("id", uuid.uuid4())
        self.name = kwargs.get("name", "Test City")
        self.country = kwargs.get("country", "Test Country")
        self.slug = kwargs.get("slug", "test-city")
        self.is_active = kwargs.get("is_active", True)
        self.center_point = kwargs.get("center_point", "33.6844,73.0479") # Islamabad coordinates as default
        
        # Add any other kwargs directly to the instance
        for key, value in kwargs.items():
            setattr(self, key, value)


@pytest.fixture
def db_session():
    """Mock database session."""
    return MagicMock(spec=Session)


@pytest.fixture
def city_service(db_session):
    """CityService instance with mocked repository."""
    service = CityService(db_session)
    # Replace real repository with a mock to isolate service logic
    service.repo = MagicMock()
    return service


# ── GET Tests ─────────────────────────────────────────────────────────────

def test_get_city_success(city_service):
    """Test fetching a city by ID successfully."""
    # Arrange
    city_id = uuid.uuid4()
    mock_city = MockCity(id=city_id, name="Islamabad")
    city_service.repo.get.return_value = mock_city

    # Act
    result = city_service.get_city(city_id)

    # Assert
    assert result.id == city_id
    assert result.name == "Islamabad"
    city_service.repo.get.assert_called_once_with(city_id)


def test_get_city_not_found(city_service):
    """Test fetching a non-existent city by ID raises CityNotFoundError."""
    # Arrange
    city_id = uuid.uuid4()
    city_service.repo.get.return_value = None

    # Act & Assert
    with pytest.raises(CityNotFoundError):
        city_service.get_city(city_id)


def test_get_city_by_slug_success(city_service):
    """Test fetching a city by slug successfully."""
    # Arrange
    slug = "karachi"
    mock_city = MockCity(slug=slug, name="Karachi")
    city_service.repo.get_by_slug.return_value = mock_city

    # Act
    result = city_service.get_city_by_slug(slug)

    # Assert
    assert result.slug == slug
    assert result.name == "Karachi"
    city_service.repo.get_by_slug.assert_called_once_with(slug)


# ── LIST Tests ────────────────────────────────────────────────────────────

def test_list_cities(city_service):
    """Test listing cities with pagination."""
    # Arrange
    mock_cities = [MockCity(name="City 1"), MockCity(name="City 2")]
    city_service.repo.get_all.return_value = mock_cities

    # Act
    result = city_service.list_cities(skip=0, limit=5)

    # Assert
    assert len(result) == 2
    assert result[0].name == "City 1"
    city_service.repo.get_all.assert_called_once_with(skip=0, limit=5)


def test_list_cities_uses_cache(city_service, monkeypatch):
    """Test cached city listings bypass the repository."""
    cached_city = MockCity(name="Cached City", slug="cached-city")

    monkeypatch.setattr(
        cities_service_module,
        "get_cache_sync",
        lambda key: [
            {
                "id": str(cached_city.id),
                "name": cached_city.name,
                "country": cached_city.country,
                "slug": cached_city.slug,
                "is_active": cached_city.is_active,
                "center_point": cached_city.center_point,
            }
        ],
    )

    result = city_service.list_cities(skip=0, limit=5)

    assert len(result) == 1
    assert result[0].slug == "cached-city"
    city_service.repo.get_all.assert_not_called()


def test_create_city_invalidates_cache(city_service, monkeypatch):
    """Test city writes invalidate cached city lists."""
    invalidated_patterns = []

    monkeypatch.setattr(cities_service_module, "delete_cache_pattern_sync", invalidated_patterns.append)
    city_service.repo.get_by_slug.return_value = None
    city_service.repo.get_by_name_and_country.return_value = None
    city_service.repo.create.return_value = MockCity(name="New City", country="Pakistan", slug="new-city")

    city_service.create_city(CityCreate(name="New City", country="Pakistan", slug="new-city"))

    assert invalidated_patterns == ["cities:*"]


# ── CREATE Tests ──────────────────────────────────────────────────────────

def test_create_city_success(city_service):
    """Test creating a city successfully."""
    # Arrange
    obj_in = CityCreate(name="Lahore", country="Pakistan")
    mock_city = MockCity(id=uuid.uuid4(), name=obj_in.name, country=obj_in.country, slug="lahore")
    
    city_service.repo.get_by_slug.return_value = None
    city_service.repo.get_by_name_and_country.return_value = None
    city_service.repo.create.return_value = mock_city

    # Act
    result = city_service.create_city(obj_in)

    # Assert
    assert result.name == "Lahore"
    assert result.slug == "lahore"
    city_service.repo.get_by_slug.assert_called_once_with("lahore")
    city_service.repo.create.assert_called_once_with(obj_in)


def test_create_city_slug_conflict(city_service):
    """Test creating a city with an existing slug raises CityConflictError."""
    # Arrange
    obj_in = CityCreate(name="Lahore", country="Pakistan", slug="lahore")
    city_service.repo.get_by_slug.return_value = MockCity(slug="lahore")

    # Act & Assert
    with pytest.raises(CityConflictError, match="slug 'lahore' already exists"):
        city_service.create_city(obj_in)


def test_create_city_name_country_conflict(city_service):
    """Test creating a city with the same name and country raises CityConflictError."""
    # Arrange
    obj_in = CityCreate(name="Lahore", country="Pakistan")
    city_service.repo.get_by_slug.return_value = None
    city_service.repo.get_by_name_and_country.return_value = MockCity(name="Lahore", country="Pakistan")

    # Act & Assert
    with pytest.raises(CityConflictError, match="already exists in 'Pakistan'"):
        city_service.create_city(obj_in)


def test_create_city_integrity_error(city_service):
    """Test that database IntegrityError is translated to CityConflictError during creation."""
    # Arrange
    obj_in = CityCreate(name="Unique Name", country="Unique Country")
    city_service.repo.get_by_slug.return_value = None
    city_service.repo.get_by_name_and_country.return_value = None
    city_service.repo.create.side_effect = IntegrityError(None, None, None)

    # Act & Assert
    with pytest.raises(CityConflictError):
        city_service.create_city(obj_in)


# ── UPDATE Tests ──────────────────────────────────────────────────────────

def test_update_city_success(city_service):
    """Test updating a city successfully."""
    # Arrange
    city_id = uuid.uuid4()
    obj_in = CityUpdate(name="Multan", center_point="30.1575,71.5249")
    existing_city = MockCity(id=city_id, name="Old Name")
    updated_city = MockCity(id=city_id, name="Multan", center_point="30.1575,71.5249")
    
    city_service.repo.get.return_value = existing_city
    city_service.repo.update.return_value = updated_city

    # Act
    result = city_service.update_city(city_id, obj_in)

    # Assert
    assert result.name == "Multan"
    assert result.center_point == "30.1575,71.5249"
    city_service.repo.update.assert_called_once()


def test_update_city_integrity_error(city_service):
    """Test that database IntegrityError is translated to CityConflictError during update."""
    # Arrange
    city_id = uuid.uuid4()
    city_service.repo.get.return_value = MockCity(id=city_id)
    city_service.repo.update.side_effect = IntegrityError(None, None, None)

    # Act & Assert
    with pytest.raises(CityConflictError, match="slug already exists"):
        city_service.update_city(city_id, CityUpdate(slug="conflict-slug"))


# ── DELETE Tests ──────────────────────────────────────────────────────────

def test_delete_city_success(city_service):
    """Test deleting a city successfully."""
    # Arrange
    city_id = uuid.uuid4()
    mock_city = MockCity(id=city_id)
    city_service.repo.get.return_value = mock_city

    # Act
    city_service.delete_city(city_id)

    # Assert
    city_service.repo.delete.assert_called_once_with(mock_city)


def test_delete_city_not_found(city_service):
    """Test deleting a non-existent city raises CityNotFoundError."""
    # Arrange
    city_id = uuid.uuid4()
    city_service.repo.get.return_value = None

    # Act & Assert
    with pytest.raises(CityNotFoundError):
        city_service.delete_city(city_id)
