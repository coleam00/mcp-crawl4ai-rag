"""
Provider manager for handling separate embedding and LLM providers.

This manager enables using different providers for embeddings and completions,
e.g., OpenAI for embeddings and DeepSeek for completions.
"""

import os
from typing import Any, Dict, Optional, Tuple

from .anthropic_provider import AnthropicProvider
from .base import BaseProvider
from .gemini_provider import GeminiProvider
from .openai_compatible import OpenAICompatibleProvider
from .openai_provider import OpenAIProvider  # Keep for backward compatibility


class ProviderManager:
    """
    Manages separate embedding and LLM providers.

    Supports two modes:
    1. Dual-provider mode: Separate EMBEDDING_PROVIDER and LLM_PROVIDER
    2. Single-provider mode: Single AI_PROVIDER (backward compatibility)
    """

    def __init__(self):
        self.embedding_provider: BaseProvider = None
        self.llm_provider: BaseProvider = None
        self._initialize_providers()

    def _initialize_providers(self):
        """Initialize embedding and LLM providers based on configuration."""
        # Check if using dual-provider mode
        embedding_provider_name = os.getenv("EMBEDDING_PROVIDER")
        llm_provider_name = os.getenv("LLM_PROVIDER")

        if embedding_provider_name and llm_provider_name:
            # Dual-provider mode
            print(
                f"Using dual-provider mode: {embedding_provider_name} (embeddings) + {llm_provider_name} (LLM)"
            )
            self.embedding_provider = self._create_provider(embedding_provider_name, "embedding")
            self.llm_provider = self._create_provider(llm_provider_name, "llm")
        else:
            # Single-provider mode (backward compatibility)
            ai_provider = os.getenv("AI_PROVIDER", "openai").lower()
            print(f"Using single-provider mode: {ai_provider}")
            provider = self._create_provider(ai_provider, "both")
            self.embedding_provider = provider
            self.llm_provider = provider

    def _create_provider(self, provider_name: str, usage_type: str) -> BaseProvider:
        """
        Create a provider instance.

        Args:
            provider_name: Name of the provider
            usage_type: "embedding", "llm", or "both"

        Returns:
            Configured provider instance
        """
        provider_name = provider_name.lower()

        # OpenAI-compatible providers
        if provider_name in ["openai", "deepseek", "ollama", "openrouter"]:
            config = self._get_openai_compatible_config(provider_name, usage_type)
            return OpenAICompatibleProvider(config, provider_name)

        # Custom providers
        elif provider_name == "gemini":
            config = self._get_gemini_config(usage_type)
            return GeminiProvider(config)

        elif provider_name == "anthropic":
            config = self._get_anthropic_config(usage_type)
            return AnthropicProvider(config)

        else:
            supported_providers = [
                "openai",
                "deepseek",
                "ollama",
                "openrouter",
                "gemini",
                "anthropic",
            ]
            raise ValueError(
                f"Unsupported provider '{provider_name}'. Supported: {', '.join(supported_providers)}"
            )

    def _get_openai_compatible_config(self, provider_name: str, usage_type: str) -> Dict[str, Any]:
        """Get configuration for OpenAI-compatible providers."""
        config = {"provider_type": provider_name}

        if provider_name == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY environment variable is required")
            config.update(
                {
                    "api_key": api_key,
                    "base_url": None,  # Use default OpenAI base URL
                    "embedding_model": os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
                    "llm_model": os.getenv("LLM_MODEL", os.getenv("MODEL_CHOICE", "gpt-4o-mini")),
                }
            )

        elif provider_name == "deepseek":
            api_key = os.getenv("DEEPSEEK_API_KEY")
            if not api_key:
                raise ValueError("DEEPSEEK_API_KEY environment variable is required")
            config.update(
                {
                    "api_key": api_key,
                    "base_url": os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
                    "embedding_model": None,  # DeepSeek doesn't support embeddings
                    "llm_model": os.getenv("LLM_MODEL", os.getenv("MODEL_CHOICE", "deepseek-chat")),
                }
            )

        elif provider_name == "ollama":
            config.update(
                {
                    "api_key": "ollama",  # Ollama doesn't require API key
                    "base_url": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
                    "embedding_model": os.getenv(
                        "EMBEDDING_MODEL", os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text")
                    ),
                    "llm_model": os.getenv(
                        "LLM_MODEL",
                        os.getenv("OLLAMA_COMPLETION_MODEL", os.getenv("MODEL_CHOICE", "llama3.2")),
                    ),
                }
            )

        elif provider_name == "openrouter":
            api_key = os.getenv("OPENROUTER_API_KEY")
            if not api_key:
                raise ValueError("OPENROUTER_API_KEY environment variable is required")
            config.update(
                {
                    "api_key": api_key,
                    "base_url": "https://openrouter.ai/api/v1",
                    "embedding_model": None,  # Most OpenRouter models don't support embeddings
                    "llm_model": os.getenv(
                        "LLM_MODEL", os.getenv("MODEL_CHOICE", "anthropic/claude-3-5-haiku")
                    ),
                }
            )

        return config

    def _get_gemini_config(self, usage_type: str) -> Dict[str, Any]:
        """Get Gemini provider configuration."""
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is required")

        return {
            "api_key": api_key,
            "embedding_model": os.getenv("EMBEDDING_MODEL", "text-embedding-004"),
            "llm_model": os.getenv("LLM_MODEL", os.getenv("MODEL_CHOICE", "gemini-1.5-flash")),
        }

    def _get_anthropic_config(self, usage_type: str) -> Dict[str, Any]:
        """Get Anthropic provider configuration."""
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required")

        return {
            "api_key": api_key,
            "llm_model": os.getenv(
                "LLM_MODEL", os.getenv("MODEL_CHOICE", "claude-3-5-haiku-20241022")
            ),
        }

    async def create_embeddings(self, texts, model=None):
        """Create embeddings using the embedding provider."""
        return await self.embedding_provider.create_embeddings(texts, model)

    async def create_completion(self, messages, model=None, temperature=0.3, max_tokens=None):
        """Create completion using the LLM provider."""
        return await self.llm_provider.create_completion(messages, model, temperature, max_tokens)

    @property
    def embedding_dimension(self) -> int:
        """Get embedding dimension from the embedding provider."""
        return self.embedding_provider.embedding_dimension

    @property
    def provider_info(self) -> Dict[str, str]:
        """Get information about the current providers."""
        return {
            "embedding_provider": self.embedding_provider.provider_name,
            "llm_provider": self.llm_provider.provider_name,
            "embedding_model": self.embedding_provider.default_embedding_model,
            "llm_model": self.llm_provider.default_completion_model,
        }


def get_provider_manager() -> ProviderManager:
    """Get a configured provider manager instance."""
    return ProviderManager()
