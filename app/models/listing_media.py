import uuid
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, Integer, ForeignKey, text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin

if TYPE_CHECKING:
    from .service_listing import ServiceListing


class ListingMedia(Base, TimestampMixin):
    """
    Model representing media files (images or video metadata) associated with a ServiceListing.
    Includes Cloudinary references for asset management.

    Attributes:
        id (uuid.UUID): Primary key.
        listingId (uuid.UUID): ID of the listing this media belongs to.
        imageUrl (str): Full URL of the asset (pointing to Cloudinary or S3).
        cloudinaryPublicId (str): Cloudinary asset identifier for deletion/transformation.
        sortOrder (int): Position in the gallery (0 for primary thumbnail).
        created_at (datetime): From TimestampMixin.
        updated_at (datetime): From TimestampMixin.
    """

    __tablename__ = "listing_media"

    __table_args__ = (
        UniqueConstraint("listingId", "imageUrl", name="uq_listing_media_listing_image"),
    )

    # Primary Key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
        doc="Unique identifier for the media record."
    )

    # Foreign Link
    listingId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("service_listings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Reference to the parent ServiceListing."
    )

    # Media Content
    imageUrl: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        doc="Public HTTPS URL for the image or video asset."
    )
    cloudinaryPublicId: Mapped[Optional[str]] = mapped_column(
        String(300),
        nullable=True,
        doc="Cloudinary identifier used for server-side asset management."
    )

    # Ordering
    sortOrder: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
        doc="Display order relative to other media in the same listing."
    )

    # Relationship back to ServiceListing
    listing: Mapped["ServiceListing"] = relationship(
        "ServiceListing",
        back_populates="media",
        doc="The listing this media is associated with."
    )

    def __repr__(self) -> str:
        return f"<ListingMedia(id={self.id}, listingId={self.listingId}, sortOrder={self.sortOrder})>"
