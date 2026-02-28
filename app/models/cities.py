import uuid
from sqlalchemy import String, DateTime, Boolean, Float, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.db.base_class import Base

class City(Base):
	__tablename__ = "cities"
	__table_args__ = (
		# Enforce uniqueness for name, country, slug combination
		UniqueConstraint("name", "country", "slug", name="uq_cities_name_country_slug"),
	)

	id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
	name: Mapped[str] = mapped_column(String(100), nullable=False)
	country: Mapped[str] = mapped_column(String(100), nullable=False)
	centerPoint: Mapped[str] = mapped_column(String(50), nullable=True)  # e.g. "lat,lng" as string
	isActive: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
	slug: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)