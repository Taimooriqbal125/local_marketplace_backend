import uuid
from sqlalchemy import Column, String, DateTime, Boolean, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base_class import Base

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    email = Column(String(255), unique=True, nullable=False)
    phone = Column(String(20), unique=True, nullable=True)

    hashed_password = Column(String(255), nullable=False)

    is_active = Column(Boolean, nullable=False, server_default=text("true"))
    is_admin = Column(Boolean, nullable=False, server_default=text("false"))
    
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    profile = relationship("Profile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    posts = relationship("Post", back_populates="owner", cascade="all, delete-orphan")
    service_listings = relationship("ServiceListing", back_populates="seller", cascade="all, delete-orphan")

    # Orders where this user is the buyer
    orders_as_buyer = relationship("Order", back_populates="buyer", foreign_keys="[Order.buyerId]")
    
    # Orders where this user is the seller
    orders_as_seller = relationship("Order", back_populates="seller", foreign_keys="[Order.sellerId]")

    # Reviews
    reviews_given = relationship("Review", back_populates="reviewer", foreign_keys="[Review.reviewerId]")
    reviews_received = relationship("Review", back_populates="reviewed_user", foreign_keys="[Review.reviewedUserId]")