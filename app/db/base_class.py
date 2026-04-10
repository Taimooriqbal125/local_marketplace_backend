from datetime import datetime, timezone
from typing import Any
from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, declared_attr


class TimestampMixin:
    """Mixin to add created_at and updated_at timestamps."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )


class Base(DeclarativeBase):
    """
    Base class for all SQLAlchemy models.
    Provides automatic tablename generation and common functionality.
    """

    id: Any
    __name__: str

    # Generate __tablename__ automatically from class name
    @declared_attr.directive
    def __tablename__(cls) -> str:
        """
        Generate tablename automatically.
        Example: User -> user, Category -> category
        """
        return cls.__name__.lower()

    def __repr__(self) -> str:
        """Simple repr for debugging."""
        return f"<{self.__class__.__name__}(id={getattr(self, 'id', 'N/A')})>"
