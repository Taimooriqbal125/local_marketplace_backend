# app/ai/services/search_service.py
"""
AI Search Service - Multi-signal semantic search for service listings.

Ranking signals:
1. Relevance (40%) - Cosine similarity between query and listing embeddings
2. Distance (30%) - PostGIS distance from user to listing (50km max)
3. Quality (20%) - Seller rating average
4. Experience (10%) - Seller completed orders count
"""
import uuid
from typing import Optional

import structlog
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.ai.providers.gemini_provider import get_gemini_provider
from app.ai.schemas.ai_schemas import AISearchResult, AISearchResponse

logger = structlog.get_logger(__name__)

# Ranking weights
WEIGHT_RELEVANCE = 0.40
WEIGHT_DISTANCE = 0.30
WEIGHT_QUALITY = 0.20
WEIGHT_EXPERIENCE = 0.10

# Thresholds
MAX_DISTANCE_KM = 50.0
SIMILARITY_THRESHOLD = 0.7
EXPERIENCE_CEILING = 100  # Orders needed to max out experience score


class AISearchService:
    """
    Multi-signal semantic search service using vector embeddings.

    Combines AI relevance with distance, quality, and experience
    to return the best matching services.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.provider = get_gemini_provider()

    async def search(
        self,
        query: str,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        city_id: Optional[uuid.UUID] = None,
        category_id: Optional[uuid.UUID] = None,
        limit: int = 5,
    ) -> AISearchResponse:
        """
        Perform multi-signal semantic search for service listings.

        Args:
            query: Natural language description of what the user needs.
            latitude: User's current latitude for distance ranking.
            longitude: User's current longitude for distance ranking.
            city_id: Optional filter by city.
            category_id: Optional filter by category.
            limit: Maximum number of results (1-20).

        Returns:
            AISearchResponse: Ranked results with composite scores.
        """
        # Step 1: Generate embedding for the query
        query_embedding = await self.provider.generate_embedding(query)

        has_location = latitude is not None and longitude is not None

        if has_location:
            results = await self._search_with_distance(
                query_embedding, latitude, longitude,
                city_id, category_id, limit
            )
        else:
            results = await self._search_without_distance(
                query_embedding, city_id, category_id, limit
            )

        # Step 3: Generate template-based explanation
        explanation = self._generate_explanation(query, results, has_location)

        return AISearchResponse(
            query=query,
            results=results,
            total_results=len(results),
            ai_explanation=explanation,
        )

    async def _search_with_distance(
        self,
        query_embedding: list[float],
        latitude: float,
        longitude: float,
        city_id: Optional[uuid.UUID],
        category_id: Optional[uuid.UUID],
        limit: int,
    ) -> list[AISearchResult]:
        """Search with distance-based ranking using PostGIS."""

        # Fetch more candidates for better ranking diversity
        candidate_limit = min(limit * 4, 50)

        sql = """
            WITH candidates AS (
                SELECT
                    se.listing_id,
                    se.content,
                    1 - (se.embedding <=> :query_embedding) as relevance_score,
                    ST_Distance(
                        sl.service_location,
                        ST_SetSRID(ST_MakePoint(:longitude, :latitude), 4326)::geography
                    ) / 1000.0 as distance_km,
                    COALESCE(p."sellerRatingAvg", 0) as rating_avg,
                    COALESCE(p."sellerRatingCount", 0) as rating_count,
                    COALESCE(p."sellerCompletedOrdersCount", 0) as completed_orders,
                    sl.title,
                    sl.description,
                    sl."priceType",
                    sl."priceAmount",
                    sl."serviceLocation",
                    c.name as category_name,
                    ci.name as city_name,
                    p.name as seller_name
                FROM service_embeddings se
                JOIN service_listings sl ON se.listing_id = sl.id
                LEFT JOIN categories c ON sl."categoryId" = c.id
                LEFT JOIN cities ci ON sl."cityId" = ci.id
                LEFT JOIN profiles p ON sl."sellerId" = p."userId"
                WHERE sl.status = 'active'
                AND se.embedding IS NOT NULL
                AND se.embedding <=> :query_embedding < :threshold
                AND sl.service_location IS NOT NULL
        """

        params = {
            "query_embedding": str(query_embedding),
            "longitude": longitude,
            "latitude": latitude,
            "threshold": SIMILARITY_THRESHOLD,
        }

        if city_id:
            sql += ' AND sl."cityId" = :city_id'
            params["city_id"] = str(city_id)

        if category_id:
            sql += ' AND sl."categoryId" = :category_id'
            params["category_id"] = str(category_id)

        # Hard cutoff at max distance
        sql += f"""
                AND ST_Distance(
                    sl.service_location,
                    ST_SetSRID(ST_MakePoint(:longitude, :latitude), 4326)::geography
                ) / 1000.0 <= {MAX_DISTANCE_KM}
            )

            SELECT *,
                (relevance_score * :w_relevance) +
                ((1 - LEAST(distance_km / :max_dist, 1.0)) * :w_distance) +
                ((LEAST(rating_avg / 5.0, 1.0)) * :w_quality) +
                (LEAST(completed_orders / :exp_ceiling, 1.0) * :w_experience)
                as composite_score
            FROM candidates
            ORDER BY composite_score DESC
            LIMIT :limit
        """

        params.update({
            "w_relevance": WEIGHT_RELEVANCE,
            "w_distance": WEIGHT_DISTANCE,
            "w_quality": WEIGHT_QUALITY,
            "w_experience": WEIGHT_EXPERIENCE,
            "max_dist": MAX_DISTANCE_KM,
            "exp_ceiling": EXPERIENCE_CEILING,
            "limit": limit,
        })

        return self._execute_search(sql, params)

    async def _search_without_distance(
        self,
        query_embedding: list[float],
        city_id: Optional[uuid.UUID],
        category_id: Optional[uuid.UUID],
        limit: int,
    ) -> list[AISearchResult]:
        """Search without distance (location not provided). Redistribute weight to relevance."""

        candidate_limit = min(limit * 4, 50)

        sql = """
            WITH candidates AS (
                SELECT
                    se.listing_id,
                    se.content,
                    1 - (se.embedding <=> :query_embedding) as relevance_score,
                    COALESCE(p."sellerRatingAvg", 0) as rating_avg,
                    COALESCE(p."sellerRatingCount", 0) as rating_count,
                    COALESCE(p."sellerCompletedOrdersCount", 0) as completed_orders,
                    sl.title,
                    sl.description,
                    sl."priceType",
                    sl."priceAmount",
                    sl."serviceLocation",
                    c.name as category_name,
                    ci.name as city_name,
                    p.name as seller_name
                FROM service_embeddings se
                JOIN service_listings sl ON se.listing_id = sl.id
                LEFT JOIN categories c ON sl."categoryId" = c.id
                LEFT JOIN cities ci ON sl."cityId" = ci.id
                LEFT JOIN profiles p ON sl."sellerId" = p."userId"
                WHERE sl.status = 'active'
                AND se.embedding IS NOT NULL
                AND se.embedding <=> :query_embedding < :threshold
        """

        params = {
            "query_embedding": str(query_embedding),
            "threshold": SIMILARITY_THRESHOLD,
        }

        if city_id:
            sql += ' AND sl."cityId" = :city_id'
            params["city_id"] = str(city_id)

        if category_id:
            sql += ' AND sl."categoryId" = :category_id'
            params["category_id"] = str(category_id)

        # Without distance, redistribute weight: relevance=0.70, quality=0.20, experience=0.10
        sql += """
            )

            SELECT *,
                (relevance_score * :w_relevance) +
                ((LEAST(rating_avg / 5.0, 1.0)) * :w_quality) +
                (LEAST(completed_orders / :exp_ceiling, 1.0) * :w_experience)
                as composite_score
            FROM candidates
            ORDER BY composite_score DESC
            LIMIT :limit
        """

        params.update({
            "w_relevance": 0.70,
            "w_quality": WEIGHT_QUALITY,
            "w_experience": WEIGHT_EXPERIENCE,
            "exp_ceiling": EXPERIENCE_CEILING,
            "limit": limit,
        })

        return self._execute_search(sql, params)

    def _execute_search(self, sql: str, params: dict) -> list[AISearchResult]:
        """Execute search query and map results to schema."""
        rows = self.db.execute(text(sql), params).fetchall()

        results = []
        for row in rows:
            distance = float(row.distance_km) if hasattr(row, "distance_km") and row.distance_km is not None else None
            results.append(
                AISearchResult(
                    listing_id=row.listing_id,
                    title=row.title,
                    description=row.description,
                    similarity_score=float(row.relevance_score),
                    composite_score=float(row.composite_score),
                    distance_km=round(distance, 2) if distance is not None else None,
                    seller_rating=float(row.rating_avg) if row.rating_avg else None,
                    seller_completed_orders=int(row.completed_orders) if row.completed_orders else None,
                    category_name=row.category_name,
                    price_amount=float(row.priceAmount) if row.priceAmount else None,
                    price_type=row.priceType,
                    city_name=row.city_name,
                    service_location=row.serviceLocation,
                    seller_name=row.seller_name,
                )
            )

        return results

    def _generate_explanation(
        self,
        query: str,
        results: list[AISearchResult],
        has_location: bool,
    ) -> str:
        """Generate a template-based explanation of search results."""
        if not results:
            return "No services found matching your description. Try rephrasing your query or broadening your search."

        top = results[0]
        parts = [f"Found {len(results)} service{'s' if len(results) != 1 else ''} matching your query."]

        # Build top result description
        detail_parts = []
        if top.category_name:
            detail_parts.append(top.category_name)
        if top.distance_km is not None:
            detail_parts.append(f"{top.distance_km}km away")
        if top.seller_rating is not None and top.seller_rating > 0:
            detail_parts.append(f"{top.seller_rating}★")
        if top.seller_completed_orders is not None and top.seller_completed_orders > 0:
            detail_parts.append(f"{top.seller_completed_orders} completed orders")

        if detail_parts:
            parts.append(f"Top result: {top.title} ({', '.join(detail_parts)}).")

        return " ".join(parts)
