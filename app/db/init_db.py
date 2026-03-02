"""
Database initialization.
Creates all tables defined in our models.
"""

from app.db.session import engine
from app.models import User, Post, Review, Base  # Import everything so Base knows all tables


def init_db() -> None:
    """
    Create all tables that don't exist yet.
    Called once when the app starts up.
    """
    Base.metadata.create_all(bind=engine)
