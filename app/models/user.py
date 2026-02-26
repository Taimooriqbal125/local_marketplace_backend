import uuid
from sqlalchemy import Column, String, DateTime, Boolean, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base_class import Base

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    phone = Column(String(20), unique=True, nullable=True)
    email = Column(String(255), unique=True, nullable=True)

    passwordHash = Column(String(255), nullable=False)

    createdAt = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    isAdmin = Column(Boolean, nullable=False, server_default=text("false"))
    profile = relationship("Profile", back_populates="user", uselist=False, cascade="all, delete-orphan")