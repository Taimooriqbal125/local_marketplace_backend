# app/ai/routes/ai_routes.py
"""
AI Routes — API endpoints for AI-powered features.
"""
import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.ai.schemas.ai_schemas import (
    AISearchRequest,
    AISearchResponse,
    AISyncResponse,
)
from app.ai.services.embedding_service import EmbeddingService
from app.ai.services.search_service import AISearchService

logger = structlog.get_logger(__name__)

router = APIRouter(
    prefix="/ai",
    tags=["AI"],
)


@router.post(
    "/search",
    response_model=AISearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Semantic search for services",
    description=(
        "Describe your problem in natural language and find relevant services. "
        "Uses AI embeddings to understand your needs and rank results by relevance."
    ),
)
async def search_services(
    request: AISearchRequest,
    db: Session = Depends(get_db),
) -> AISearchResponse:
    """
    Semantic search for service listings.
    
    Example queries:
    - "My roof is leaking and I need someone to fix it"
    - "I need a plumber for bathroom renovation"
    - "Looking for a tutor to help with math homework"
    
    The AI understands the meaning behind your query, not just keywords.
    """
    try:
        search_service = AISearchService(db)
        results = await search_service.search(
            query=request.query,
            latitude=request.latitude,
            longitude=request.longitude,
            city_id=request.city_id,
            category_id=request.category_id,
            limit=request.limit,
        )
        return results
    except Exception as e:
        logger.error("AI search failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(e)}",
        )


@router.post(
    "/sync",
    response_model=AISyncResponse,
    status_code=status.HTTP_200_OK,
    summary="Sync embeddings for all listings",
    description=(
        "Generate or update embeddings for all active service listings. "
        "Run this after initial setup or when listings are updated."
    ),
)
async def sync_embeddings(
    db: Session = Depends(get_db),
) -> AISyncResponse:
    """
    Sync embeddings for all active service listings.
    
    This endpoint:
    - Generates embeddings for new listings
    - Updates embeddings for modified listings
    - Returns statistics about the sync operation
    """
    try:
        embedding_service = EmbeddingService(db)
        result = await embedding_service.sync_all_embeddings()
        return AISyncResponse(
            total_listings=result["total"],
            synced_count=result["synced"],
            skipped_count=result["skipped"],
            message=f"Sync complete: {result['synced']} updated, {result['skipped']} skipped",
        )
    except Exception as e:
        logger.error("Embedding sync failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Sync failed: {str(e)}",
        )
