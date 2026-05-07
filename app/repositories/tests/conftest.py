import sys
from unittest.mock import MagicMock
from sqlalchemy import String, event
import sqlalchemy as sa

# --- Global Geoalchemy2 Mocking ---
# This must happen before any models that import geoalchemy2 are loaded.
# Since pytest collects tests, we do it at the module level of conftest.

mock_geo = MagicMock()
mock_geo_elements = MagicMock()
mock_geo_shape = MagicMock()
mock_geo_functions = MagicMock()

# Map geo functions to sa.func so they produce valid SQL expressions
mock_geo_functions.ST_Distance = sa.func.ST_Distance
mock_geo_functions.ST_DWithin = sa.func.ST_DWithin

class MockGeography(String):
    def __init__(self, *args, **kwargs):
        super().__init__()

class MockWKTElement(str):
    def __new__(cls, data, srid=4326):
        return super().__new__(cls, data)

mock_geo.Geography = MockGeography
mock_geo_elements.WKTElement = MockWKTElement

sys.modules["geoalchemy2"] = mock_geo
sys.modules["geoalchemy2.elements"] = mock_geo_elements
sys.modules["geoalchemy2.shape"] = mock_geo_shape
sys.modules["geoalchemy2.functions"] = mock_geo_functions


@event.listens_for(sa.engine.Engine, "connect")
def receive_connect(dbapi_connection, connection_record):
    """Register SQLite-compatible versions of PostGIS functions."""
    # This ensures that even if a test doesn't explicitly mock them, 
    # the database engine will know how to handle these names.
    cursor = dbapi_connection.cursor()
    try:
        dbapi_connection.create_function("ST_Distance", 2, lambda x, y: 5000.0)
        dbapi_connection.create_function("ST_DWithin", 3, lambda x, y, z: True)
        dbapi_connection.create_function("now", 0, lambda: "2026-01-01 00:00:00")
    except Exception:
        pass
    finally:
        cursor.close()
