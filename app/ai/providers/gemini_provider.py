# app/ai/providers/gemini_provider.py
"""
Google Gemini AI Provider - Handles embeddings via Gemini API.
Uses gemini-embedding-001 for embeddings.
"""
import asyncio
from typing import Optional

import structlog
from google import genai
from google.genai import types

from app.ai.providers.base import BaseAIProvider
from app.ai.config import ai_settings

logger = structlog.get_logger(__name__)


class GeminiProvider(BaseAIProvider):
    """
    Google Gemini AI Provider implementation.

    Uses Gemini's free tier:
    - Embeddings: gemini-embedding-001 (768 dimensions, 1,500 req/day)
    """

    def __init__(self):
        """Initialize the Gemini client."""
        self._client = genai.Client(api_key=ai_settings.gemini_api_key)
        self._embedding_model = ai_settings.embedding_model
        self._dimensions = ai_settings.embedding_dimensions

    async def generate_embedding(self, text: str) -> list[float]:
        """
        Generate an embedding vector for a single text.

        Args:
            text: The text to embed.

        Returns:
            list[float]: 768-dimensional embedding vector.

        Raises:
            Exception: If the Gemini API request fails.
        """
        try:
            result = await asyncio.to_thread(
                self._client.models.embed_content,
                model=self._embedding_model,
                contents=text,
                config=types.EmbedContentConfig(
                    output_dimensionality=self._dimensions
                ),
            )
            embedding = result.embeddings[0].values
            logger.debug(
                "Generated embedding",
                text_length=len(text),
                embedding_dim=len(embedding),
            )
            return embedding
        except Exception as e:
            logger.error("Gemini embedding error", error=str(e))
            raise

    async def generate_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embedding vectors for multiple texts in a single request.

        Args:
            texts: List of texts to embed.

        Returns:
            list[list[float]]: List of 768-dimensional embedding vectors.

        Raises:
            Exception: If the Gemini API request fails.
        """
        if not texts:
            return []

        try:
            result = await asyncio.to_thread(
                self._client.models.embed_content,
                model=self._embedding_model,
                contents=texts,
                config=types.EmbedContentConfig(
                    output_dimensionality=self._dimensions
                ),
            )
            embeddings = [emb.values for emb in result.embeddings]
            logger.info(
                "Generated batch embeddings",
                count=len(texts),
                embedding_dim=len(embeddings[0]) if embeddings else 0,
            )
            return embeddings
        except Exception as e:
            logger.error("Gemini batch embedding error", error=str(e))
            raise

    async def generate_chat_response(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 500,
    ) -> str:
        """
        Gemini doesn't have a free chat model.
        This method is not implemented - use Groq for chat if needed.
        """
        raise NotImplementedError(
            "GeminiProvider does not support chat. Use a separate chat provider."
        )


# Singleton instance for reuse across the application
_gemini_provider: Optional[GeminiProvider] = None


def get_gemini_provider() -> GeminiProvider:
    """Get or create the singleton Gemini provider instance."""
    global _gemini_provider
    if _gemini_provider is None:
        _gemini_provider = GeminiProvider()
    return _gemini_provider
