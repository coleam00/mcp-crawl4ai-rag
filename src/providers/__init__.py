"""
AI Provider abstraction layer for Crawl4AI MCP server.

This package provides a unified interface for multiple AI providers including:
- OpenAI
- Ollama (local models)
- Google Gemini
- DeepSeek
- Anthropic

Each provider implements the same interface for embeddings and completions.
"""

from .anthropic_provider import AnthropicProvider
from .base import BaseProvider, CompletionResponse, EmbeddingResponse
from .deepseek_provider import DeepSeekProvider
from .factory import get_provider
from .gemini_provider import GeminiProvider
from .manager import ProviderManager, get_provider_manager
from .ollama_provider import OllamaProvider
from .openai_compatible import OpenAICompatibleProvider
from .openai_provider import OpenAIProvider

__all__ = [
    "BaseProvider",
    "EmbeddingResponse",
    "CompletionResponse",
    "OpenAIProvider",
    "OllamaProvider",
    "GeminiProvider",
    "DeepSeekProvider",
    "AnthropicProvider",
    "OpenAICompatibleProvider",
    "ProviderManager",
    "get_provider_manager",
    "get_provider",
]
