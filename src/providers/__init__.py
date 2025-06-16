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

from .base import BaseProvider, EmbeddingResponse, CompletionResponse
from .openai_provider import OpenAIProvider
from .ollama_provider import OllamaProvider
from .gemini_provider import GeminiProvider
from .deepseek_provider import DeepSeekProvider
from .anthropic_provider import AnthropicProvider
from .factory import get_provider

__all__ = [
    'BaseProvider',
    'EmbeddingResponse', 
    'CompletionResponse',
    'OpenAIProvider',
    'OllamaProvider', 
    'GeminiProvider',
    'DeepSeekProvider',
    'AnthropicProvider',
    'get_provider'
] 