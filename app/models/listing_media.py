import uuid
from sqlalchemy import Column, String, Integer, ForeignKey, DateTime, text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.db.base_class import Base

class ListingMedia(Base):
    """
    Model representing media files (images) associated with a ServiceListing.
    """
    __tablename__ = "listing_media"
    __table_args__ = (
        # Ensure that the same image URL isn't added multiple times to the same listing
        UniqueConstraint("listingId", "imageUrl", name="uq_listing_media_listing_image"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )

    listingId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("service_listings.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # imageUrl (string) — Required
    # Stores the HTTPS URL returned by Cloudinary after upload
    imageUrl: Mapped[str] = mapped_column(String(500), nullable=False)

    # cloudinaryPublicId — Optional
    # Stores the Cloudinary public_id so we can delete the asset on record removal.
    # Nullable because records created directly with a URL won't have one.
    cloudinaryPublicId: Mapped[str] = mapped_column(String(300), nullable=True)

    # sortOrder (int) — Default 0
    # Allows ordering of images (e.g. 0 is the primary thumbnail)
    sortOrder: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

    # createdAt — Required, Default: now()
    createdAt: Mapped[str] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )

    # Relationship back to ServiceListing
    listing: Mapped["ServiceListing"] = relationship("ServiceListing", back_populates="media")
