"""
Provider manager for handling multiple AI providers and embeddings.
"""

import os
from typing import Any, Dict, Optional, Tuple

from .anthropic_provider import AnthropicProvider
from .base import BaseProvider
from .factory import get_provider
from .gemini_provider import GeminiProvider
from .openai_compatible import OpenAICompatibleProvider


class ProviderManager:
    """
    Manages separate embedding and LLM providers.

    Supports two modes:
    1. Dual-provider mode: Separate EMBEDDING_PROVIDER and LLM_PROVIDER
    2. Single-provider mode: Single AI_PROVIDER (backward compatibility)
    """

    def __init__(self, config: Dict[str, str]):
        """Initialize the provider manager with configuration."""
        self.config = config
        self.embedding_provider = None
        self.llm_provider = None
        self._setup_providers()

    def _setup_providers(self):
        """Set up embedding and LLM providers based on configuration."""
        # Check if dual-provider mode is configured
        embedding_provider_name = self.config.get("EMBEDDING_PROVIDER")
        llm_provider_name = self.config.get("LLM_PROVIDER")

        if embedding_provider_name and llm_provider_name:
            # Dual-provider mode
            self.embedding_provider = self._create_provider(embedding_provider_name, "embedding")
            self.llm_provider = self._create_provider(llm_provider_name, "llm")
        elif self.config.get("AI_PROVIDER"):
            # Single-provider mode (backward compatibility)
            single_provider_name = self.config["AI_PROVIDER"]
            single_provider = self._create_provider(single_provider_name, "both")
            self.embedding_provider = single_provider
            self.llm_provider = single_provider
        else:
            # Default to OpenAI-compatible provider
            default_provider = self._create_provider("openai", "both")
            self.embedding_provider = default_provider
            self.llm_provider = default_provider

    def _create_provider(self, provider_name: str, mode: str) -> BaseProvider:
        """Create a provider instance based on name and mode."""
        provider_name = provider_name.lower()

        if provider_name in ["openai", "deepseek", "ollama", "openrouter"]:
            return OpenAICompatibleProvider(self.config, provider_name)
        if provider_name == "gemini":
            return GeminiProvider(self.config)
        if provider_name == "anthropic":
            return AnthropicProvider(self.config)

        raise ValueError(f"Unknown provider: {provider_name}")

    async def create_embeddings(self, texts, model=None):
        """Create embeddings using the embedding provider."""
        if self.embedding_provider is None:
            raise RuntimeError("Embedding provider not initialized")
        return await self.embedding_provider.create_embeddings(texts, model)

    async def create_completion(self, messages, model=None, temperature=0.3, max_tokens=None):
        """Create completion using the LLM provider."""
        if self.llm_provider is None:
            raise RuntimeError("LLM provider not initialized")
        return await self.llm_provider.create_completion(messages, model, temperature, max_tokens)

    @property
    def provider_info(self) -> Dict[str, str]:
        """Get information about the configured providers."""
        return {
            "embedding_provider": (
                self.embedding_provider.provider_name if self.embedding_provider else "none"
            ),
            "llm_provider": (self.llm_provider.provider_name if self.llm_provider else "none"),
            "embedding_model": (
                self.embedding_provider.default_embedding_model
                if self.embedding_provider
                else "none"
            ),
            "llm_model": (
                self.llm_provider.default_completion_model if self.llm_provider else "none"
            ),
        }


def get_provider_manager() -> ProviderManager:
    """
    Factory function to create a ProviderManager instance.

    Returns:
        ProviderManager: Configured provider manager instance
    """
    config = {
        # Dual-provider configuration
        "EMBEDDING_PROVIDER": os.getenv("EMBEDDING_PROVIDER"),
        "EMBEDDING_MODEL": os.getenv("EMBEDDING_MODEL"),
        "LLM_PROVIDER": os.getenv("LLM_PROVIDER"),
        "LLM_MODEL": os.getenv("LLM_MODEL"),
        # Single-provider configuration (backward compatibility)
        "AI_PROVIDER": os.getenv("AI_PROVIDER"),
        "AI_MODEL": os.getenv("AI_MODEL"),
        # API keys and configurations
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
        "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY"),
        "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY"),
        "DEEPSEEK_API_KEY": os.getenv("DEEPSEEK_API_KEY"),
        "OLLAMA_BASE_URL": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        "OPENROUTER_API_KEY": os.getenv("OPENROUTER_API_KEY"),
    }

    return ProviderManager(config)
