# app/ai/providers/base.py
"""
Abstract base class for AI providers.
Defines the interface that all AI providers must implement.
"""
from abc import ABC, abstractmethod
from typing import Optional


class BaseAIProvider(ABC):
    """
    Abstract base class for AI providers.
    
    All AI providers (Groq, OpenAI, etc.) must implement these methods.
    This allows us to swap providers without changing the rest of the codebase.
    """

    @abstractmethod
    async def generate_embedding(self, text: str) -> list[float]:
        """
        Generate an embedding vector for the given text.
        
        Args:
            text: The text to generate embedding for.
            
        Returns:
            list[float]: The embedding vector.
        """
        pass

    @abstractmethod
    async def generate_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embedding vectors for multiple texts in batch.
        
        Args:
            texts: List of texts to generate embeddings for.
            
        Returns:
            list[list[float]]: List of embedding vectors.
        """
        pass

    @abstractmethod
    async def generate_chat_response(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 500,
    ) -> str:
        """
        Generate a chat response using the LLM.
        
        Args:
            prompt: The user prompt/query.
            system_prompt: Optional system instruction.
            max_tokens: Maximum tokens in response.
            
        Returns:
            str: The generated response text.
        """
        pass
