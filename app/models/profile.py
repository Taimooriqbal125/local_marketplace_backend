import uuid
from sqlalchemy import Column, String, DateTime, Boolean, Integer, Numeric, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from geoalchemy2 import Geography

from app.db.base_class import Base


class Profile(Base):
    __tablename__ = "profiles"

    # userId (UUID) — PK, FK -> users.id, Required, Unique
    userId = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )

    # name (string) — Required
    name = Column(String(100), nullable=False)

    # bio (text) — Optional
    bio = Column(String, nullable=True)

    # sellercompleted order
    sellerCompletedOrdersCount = Column(Integer, nullable=False, server_default=text("0"))

    # photoUrl (string) — Optional
    photoUrl = Column(String(500), nullable=True)

    # sellerRatingAvg (decimal 3,2) — Required, Default: 0.00
    sellerRatingAvg = Column(Numeric(3, 2), nullable=False, server_default=text("0.00"))

    # sellerRatingCount (int) — Required, Default: 0
    sellerRatingCount = Column(Integer, nullable=False, server_default=text("0"))

    # sellerStatus (enum: none, active, suspended) — Required, Default: none
    sellerStatus = Column(String(20), nullable=False, server_default=text("'none'"))

    # ✅ PostGIS Geography Location Fields (POINT, WGS84)
    last_location_point = Column(Geography(geometry_type="POINT", srid=4326), nullable=True)
    last_location_at = Column(DateTime(timezone=True), nullable=True)
    last_location_accuracy_m = Column(Integer, nullable=True)
    last_location_source = Column(String(20), nullable=True)
    default_location_point = Column(Geography(geometry_type="POINT", srid=4326), nullable=True)

    # ✅ Privacy/consent (store only if enabled)
    location_tracking_enabled = Column(Boolean, nullable=False, server_default=text("false"))

    # isBanned (boolean) — Required, Default: false
    isBanned = Column(Boolean, nullable=False, server_default=text("false"))

    # createdAt / updatedAt — Required, Default: now()
    createdAt = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updatedAt = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationship back to User (optional but recommended)
    user = relationship("User", back_populates="profile", uselist=False)