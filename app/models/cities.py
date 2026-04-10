import uuid
from typing import Optional

from sqlalchemy import String, Boolean, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base, TimestampMixin


class City(Base, TimestampMixin):
    """
    Representation of a supported city or geographic region in the marketplace.

    Attributes:
        id (uuid.UUID): Primary key.
        name (str): Display name of the city.
        country (str): Country where the city is located.
        center_point (str): Geographic center (e.g., "lat,lng") as a string.
        is_active (bool): Whether listings in this city are publicly visible.
        slug (str): Unique URL-friendly identifier.
        created_at (datetime): Timestamp of record creation.
        updated_at (datetime): Timestamp of latest update.
    """

    __tablename__ = "cities"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        doc="Unique identifier for the city."
    )

    # Core identification
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        doc="Common name of the city."
    )
    country: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        doc="Country where the city is located."
    )
    slug: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        unique=True,
        doc="URL-friendly identifier for the city."
    )

    # Metadata and Status
    centerPoint: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        doc="Estimated geographic center point ('lat,lng')."
    )
    isActive: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
        doc="Visibility toggle for this city in the interface."
    )

    def __repr__(self) -> str:
        return f"<City(id={self.id}, name='{self.name}', country='{self.country}')>"