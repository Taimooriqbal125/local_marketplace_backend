# app/ai/schemas/ai_schemas.py
"""
AI Schemas - Pydantic models for AI search requests and responses.
"""
import uuid
from typing import Optional

from pydantic import Field

from app.schemas.base import BaseSchema


class AISearchRequest(BaseSchema):
    """Request schema for AI-powered semantic search."""

    query: str = Field(
        ...,
        min_length=3,
        max_length=500,
        description="Natural language description of what you're looking for",
        examples=["My roof is leaking and I need someone to fix it"],
    )
    latitude: Optional[float] = Field(
        default=None,
        ge=-90,
        le=90,
        description="User's current latitude for distance-based ranking",
    )
    longitude: Optional[float] = Field(
        default=None,
        ge=-180,
        le=180,
        description="User's current longitude for distance-based ranking",
    )
    city_id: Optional[uuid.UUID] = Field(
        default=None,
        description="Filter results by city",
    )
    category_id: Optional[uuid.UUID] = Field(
        default=None,
        description="Filter results by category",
    )
    limit: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum number of results to return",
    )


class AISearchResult(BaseSchema):
    """A single search result with multi-signal ranking."""

    listing_id: uuid.UUID = Field(
        description="Unique identifier of the service listing",
    )
    title: str = Field(
        description="Service listing title",
    )
    description: Optional[str] = Field(
        default=None,
        description="Service listing description",
    )
    similarity_score: float = Field(
        description="AI relevance score (0.0 to 1.0, higher = more relevant)",
    )
    composite_score: float = Field(
        description="Final weighted ranking score (0.0 to 1.0, higher = better match)",
    )
    distance_km: Optional[float] = Field(
        default=None,
        description="Distance from user in kilometers (null if location not provided)",
    )
    seller_rating: Optional[float] = Field(
        default=None,
        description="Seller's average rating (0.0 to 5.0)",
    )
    seller_completed_orders: Optional[int] = Field(
        default=None,
        description="Number of orders the seller has completed",
    )
    category_name: Optional[str] = Field(
        default=None,
        description="Name of the service category",
    )
    price_amount: Optional[float] = Field(
        default=None,
        description="Service price",
    )
    price_type: Optional[str] = Field(
        default=None,
        description="Price type (fixed, hourly, daily)",
    )
    city_name: Optional[str] = Field(
        default=None,
        description="City where the service is available",
    )
    service_location: Optional[str] = Field(
        default=None,
        description="Service location/address",
    )
    seller_name: Optional[str] = Field(
        default=None,
        description="Name of the service provider",
    )


class AISearchResponse(BaseSchema):
    """Response schema for AI-powered semantic search."""

    query: str = Field(
        description="The original search query",
    )
    results: list[AISearchResult] = Field(
        description="Ranked list of relevant services",
    )
    total_results: int = Field(
        description="Total number of results found",
    )
    ai_explanation: Optional[str] = Field(
        default=None,
        description="Explanation of why these results match the query",
    )


class AISyncResponse(BaseSchema):
    """Response schema for embedding sync operation."""

    total_listings: int = Field(
        description="Total number of active listings",
    )
    synced_count: int = Field(
        description="Number of listings synced/updated",
    )
    skipped_count: int = Field(
        description="Number of listings skipped (already up to date)",
    )
    message: str = Field(
        description="Status message",
    )
