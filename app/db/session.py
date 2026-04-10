"""
Database session setup.

Key concepts:
  - Engine      → the connection to the database
  - SessionLocal → a factory that creates new database sessions
  - get_db()    → a FastAPI *dependency* that gives each request its own session
                   and automatically closes it when the request is done
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator

from app.core.config import settings

# ---------- Engine ----------
# Neon requires SSL. We enforce it here to prevent 'SSL SYSCALL error: EOF detected'.
connect_args = {}
if "neon.tech" in settings.DATABASE_URL:
    connect_args["sslmode"] = "require"

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,   # detect dropped connections automatically
    pool_size=10,
    max_overflow=20,
    connect_args=connect_args,
)

# ---------- Session Factory ----------
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# ---------- Dependency ----------
def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency.
    Usage in a route:  db: Session = Depends(get_db)

    Opens a session, yields it to the route, then closes it — even if
    an error occurs (the `finally` block guarantees cleanup).
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
