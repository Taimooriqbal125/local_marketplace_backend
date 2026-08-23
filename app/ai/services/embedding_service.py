# app/ai/services/embedding_service.py
"""
Embedding Service - Handles generating and storing vector embeddings.
"""
import uuid
from typing import Optional

import structlog
from sqlalchemy import select, delete
from sqlalchemy.orm import Session

from app.models.service_listing import ServiceListing
from app.ai.models.service_embedding import ServiceEmbedding
from app.ai.providers.gemini_provider import get_gemini_provider

logger = structlog.get_logger(__name__)


class EmbeddingService:
    """
    Manages embedding generation and storage for service listings.
    
    Responsibilities:
    - Generate embeddings for service listings
    - Store embeddings in PostgreSQL via pgvector
    - Sync embeddings when listings are created/updated/deleted
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.provider = get_gemini_provider()

    def _build_embedding_content(
        self,
        title: str,
        description: Optional[str],
        category_name: Optional[str],
    ) -> str:
        """
        Build the text content used for embedding generation.
        
        Combines title, description, and category for richer semantic meaning.
        """
        parts = [title]
        if description:
            parts.append(description)
        if category_name:
            parts.append(f"Category: {category_name}")
        return " | ".join(parts)

    async def generate_embedding_for_listing(
        self,
        listing: ServiceListing,
    ) -> list[float]:
        """
        Generate an embedding vector for a single service listing.
        
        Args:
            listing: The service listing to generate embedding for.
            
        Returns:
            list[float]: 768-dimensional embedding vector.
        """
        content = self._build_embedding_content(
            title=listing.title,
            description=listing.description,
            category_name=listing.category.name if listing.category else None,
        )
        embedding = await self.provider.generate_embedding(content)
        return embedding

    async def upsert_embedding(
        self,
        listing: ServiceListing,
    ) -> ServiceEmbedding:
        """
        Create or update the embedding for a service listing.
        
        Args:
            listing: The service listing to upsert embedding for.
            
        Returns:
            ServiceEmbedding: The created/updated embedding record.
        """
        content = self._build_embedding_content(
            title=listing.title,
            description=listing.description,
            category_name=listing.category.name if listing.category else None,
        )

        # Generate embedding
        embedding_vector = await self.provider.generate_embedding(content)

        # Check if embedding already exists
        existing = self.db.execute(
            select(ServiceEmbedding).where(
                ServiceEmbedding.listing_id == listing.id
            )
        ).scalar_one_or_none()

        if existing:
            # Update existing embedding
            existing.content = content
            existing.embedding = embedding_vector
            self.db.commit()
            self.db.refresh(existing)
            logger.info(
                "Updated embedding",
                listing_id=str(listing.id),
                content_length=len(content),
            )
            return existing
        else:
            # Create new embedding
            new_embedding = ServiceEmbedding(
                listing_id=listing.id,
                content=content,
                embedding=embedding_vector,
            )
            self.db.add(new_embedding)
            self.db.commit()
            self.db.refresh(new_embedding)
            logger.info(
                "Created embedding",
                listing_id=str(listing.id),
                content_length=len(content),
            )
            return new_embedding

    async def sync_all_embeddings(self) -> dict:
        """
        Sync embeddings for all active service listings.
        
        This is useful for:
        - Initial setup
        - Re-syncing after bulk data changes
        - Fixing missing embeddings
        
        Returns:
            dict: Sync statistics (total, synced, skipped).
        """
        # Get all active listings
        listings = self.db.execute(
            select(ServiceListing).where(
                ServiceListing.status == "active"
            )
        ).scalars().all()

        total = len(listings)
        synced = 0
        skipped = 0

        for listing in listings:
            try:
                await self.upsert_embedding(listing)
                synced += 1
            except Exception as e:
                logger.error(
                    "Failed to sync embedding",
                    listing_id=str(listing.id),
                    error=str(e),
                )
                skipped += 1

        logger.info(
            "Synced all embeddings",
            total=total,
            synced=synced,
            skipped=skipped,
        )

        return {
            "total": total,
            "synced": synced,
            "skipped": skipped,
        }

    async def delete_embedding(self, listing_id: uuid.UUID) -> bool:
        """
        Delete the embedding for a service listing.
        
        Args:
            listing_id: The listing ID to delete embedding for.
            
        Returns:
            bool: True if deleted, False if not found.
        """
        result = self.db.execute(
            delete(ServiceEmbedding).where(
                ServiceEmbedding.listing_id == listing_id
            )
        )
        self.db.commit()
        deleted = result.rowcount > 0
        if deleted:
            logger.info("Deleted embedding", listing_id=str(listing_id))
        return deleted
