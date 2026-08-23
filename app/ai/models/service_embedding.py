# app/ai/models/service_embedding.py
"""
Service Embedding Model - Stores vector embeddings for service listings.
Used for semantic search via pgvector.
"""
import uuid
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, Text, ForeignKey, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

from app.db.base_class import Base, TimestampMixin
from app.ai.config import ai_settings

if TYPE_CHECKING:
    from app.models.service_listing import ServiceListing


class ServiceEmbedding(Base, TimestampMixin):
    """
    Stores vector embeddings for service listings.
    
    Each embedding is generated from a combination of:
    - Service title
    - Service description
    - Category name
    
    This allows semantic search where users can describe their problem
    and find relevant services.
    """

    __tablename__ = "service_embeddings"
    __table_args__ = (
        UniqueConstraint("listing_id", name="uq_service_embeddings_listing_id"),
    )

    # Primary Key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )

    # Foreign Key to ServiceListing
    listing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("service_listings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # The combined text used to generate the embedding
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="Combined text (title + description + category) used for embedding",
    )

    # The embedding vector (768 dimensions for nomic-embed-text-v1.5)
    embedding: Mapped[Optional[list]] = mapped_column(
        Vector(ai_settings.embedding_dimensions),
        nullable=True,
        doc="768-dimensional embedding vector",
    )

    # Relationship to ServiceListing
    listing: Mapped["ServiceListing"] = relationship(
        "ServiceListing",
        lazy="joined",
    )

    def __repr__(self) -> str:
        return (
            f"<ServiceEmbedding(id={self.id}, listing_id={self.listing_id}, "
            f"content_length={len(self.content) if self.content else 0})>"
        )
