"""
Database initialization.
Creates all tables defined in our models.
"""

from sqlalchemy import text
from app.db.session import engine
from app.models import User, Post, Review, Base  # Import everything so Base knows all tables


def init_db() -> None:
    """
    Create all tables that don't exist yet.
    Called once when the app starts up.
    """
    # PostGIS extension must exist before Geography columns can be created
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        conn.commit()
    Base.metadata.create_all(bind=engine)
