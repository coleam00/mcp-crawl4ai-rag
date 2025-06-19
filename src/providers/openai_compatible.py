"""
OpenAI-compatible provider implementation.

This provider uses the OpenAI client library to work with any service that offers
OpenAI-compatible APIs, including:
- OpenAI
- DeepSeek
- Ollama (with OpenAI compatibility mode)
- OpenRouter
- Together AI
- And many others
"""

import time
from typing import Any, Dict, List, Optional

import openai

from .base import BaseProvider, CompletionResponse, EmbeddingResponse


class OpenAICompatibleProvider(BaseProvider):
    """OpenAI-compatible provider implementation using the OpenAI client library."""

    def __init__(self, config: Dict[str, Any], provider_type: str):
        """
        Initialize the OpenAI-compatible provider.

        Args:
            config: Provider configuration
            provider_type: Type of provider (openai, deepseek, ollama, openrouter)
        """
        self.provider_type = provider_type
        super().__init__(config)

    def _validate_config(self) -> None:
        """Validate OpenAI-compatible provider configuration."""
        api_key = self.config.get("api_key")
        if not api_key:
            raise ValueError(f"{self.provider_type.upper()} API key is required")

        # Initialize OpenAI client with custom base URL if provided
        base_url = self.config.get("base_url")

        if base_url:
            self.client = openai.OpenAI(api_key=api_key, base_url=base_url)
        else:
            # Use default OpenAI configuration
            self.client = openai.OpenAI(api_key=api_key)

        # Store model configurations
        self.embedding_model = self.config.get("embedding_model")
        self.llm_model = self.config.get("llm_model")

    async def create_embeddings(
        self, texts: List[str], model: Optional[str] = None
    ) -> EmbeddingResponse:
        """Create embeddings using OpenAI-compatible API."""
        if not texts:
            return EmbeddingResponse(embeddings=[])

        # Check if this provider supports embeddings
        embedding_model = model or self.embedding_model
        if not embedding_model:
            print(
                f"Warning: {self.provider_type} doesn't support embeddings. Using zero embeddings as fallback."
            )
            embeddings = [[0.0] * self.embedding_dimension for _ in texts]
            return EmbeddingResponse(embeddings=embeddings, model=f"{self.provider_type}-fallback")

        max_retries = 3
        retry_delay = 1.0

        for retry in range(max_retries):
            try:
                response = self.client.embeddings.create(model=embedding_model, input=texts)
                embeddings = [item.embedding for item in response.data]
                usage = getattr(response, "usage", None)

                return EmbeddingResponse(
                    embeddings=embeddings,
                    usage=usage.__dict__ if usage else None,
                    model=embedding_model,
                )
            except Exception as e:
                if retry < max_retries - 1:
                    print(
                        f"Error creating batch embeddings "
                        f"(attempt {retry + 1}/{max_retries}): {e}"
                    )
                    print(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    print(
                        f"Failed to create batch embeddings " f"after {max_retries} attempts: {e}"
                    )
                    # Try individual embeddings as fallback
                    print("Attempting to create embeddings individually...")
                    embeddings = []
                    successful_count = 0

                    for i, text in enumerate(texts):
                        try:
                            individual_response = self.client.embeddings.create(
                                model=embedding_model, input=[text]
                            )
                            embeddings.append(individual_response.data[0].embedding)
                            successful_count += 1
                        except Exception as individual_error:
                            print(f"Failed to create embedding for text {i}: {individual_error}")
                            # Add zero embedding as fallback
                            embeddings.append([0.0] * self.embedding_dimension)

                    print(
                        f"Successfully created {successful_count}/{len(texts)} embeddings individually"
                    )
                    return EmbeddingResponse(embeddings=embeddings, model=embedding_model)

    async def create_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: Optional[int] = None,
    ) -> CompletionResponse:
        """Create completion using OpenAI-compatible API."""
        completion_model = model or self.llm_model

        kwargs = {"model": completion_model, "messages": messages, "temperature": temperature}

        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens

        try:
            response = self.client.chat.completions.create(**kwargs)

            content = response.choices[0].message.content.strip()
            usage = getattr(response, "usage", None)

            return CompletionResponse(
                content=content, usage=usage.__dict__ if usage else None, model=completion_model
            )
        except Exception as e:
            print(f"Error creating completion with {self.provider_type}: {e}")
            raise

    @property
    def embedding_dimension(self) -> int:
        """Get embedding dimension based on provider and model."""
        if self.provider_type == "openai":
            # OpenAI embedding dimensions
            model_dimensions = {
                "text-embedding-3-small": 1536,
                "text-embedding-3-large": 3072,
                "text-embedding-ada-002": 1536,
            }
            return model_dimensions.get(self.embedding_model, 1536)

        elif self.provider_type == "ollama":
            # Ollama embedding dimensions (based on model)
            model_dimensions = {
                "nomic-embed-text": 768,
                "mxbai-embed-large": 1024,
                "snowflake-arctic-embed": 1024,
                "all-minilm": 384,
            }
            return model_dimensions.get(self.embedding_model, 768)

        elif self.provider_type == "deepseek":
            # DeepSeek doesn't have embeddings, but return standard dimension
            return 1536

        elif self.provider_type == "openrouter":
            # OpenRouter typically doesn't have embeddings, return standard dimension
            return 1536

        else:
            # Default dimension
            return 1536

    @property
    def default_embedding_model(self) -> str:
        """Get default embedding model for this provider."""
        return self.embedding_model or f"{self.provider_type}-fallback"

    @property
    def default_completion_model(self) -> str:
        """Get default completion model for this provider."""
        return self.llm_model or "gpt-3.5-turbo"

    @property
    def provider_name(self) -> str:
        """Get the provider name."""
        return self.provider_type
