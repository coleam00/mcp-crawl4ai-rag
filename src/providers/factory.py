"""
Provider factory for creating AI provider instances.
"""

import os
from typing import Dict, Any, Optional
from .base import BaseProvider
from .openai_provider import OpenAIProvider
from .ollama_provider import OllamaProvider
from .gemini_provider import GeminiProvider
from .deepseek_provider import DeepSeekProvider
from .anthropic_provider import AnthropicProvider


def get_provider(provider_name: Optional[str] = None) -> BaseProvider:
    """
    Get an AI provider instance based on configuration.
    
    Args:
        provider_name: Optional provider name override
        
    Returns:
        Configured AI provider instance
        
    Raises:
        ValueError: If provider is not supported or required config is missing
    """
    # Get provider from parameter or environment
    provider = provider_name or os.getenv("AI_PROVIDER", "openai").lower()
    
    # Provider configuration mapping
    provider_configs = {
        "openai": _get_openai_config,
        "ollama": _get_ollama_config,
        "gemini": _get_gemini_config,
        "deepseek": _get_deepseek_config,
        "anthropic": _get_anthropic_config
    }
    
    # Provider class mapping
    provider_classes = {
        "openai": OpenAIProvider,
        "ollama": OllamaProvider,
        "gemini": GeminiProvider,
        "deepseek": DeepSeekProvider,
        "anthropic": AnthropicProvider
    }
    
    if provider not in provider_classes:
        supported = ", ".join(provider_classes.keys())
        raise ValueError(f"Unsupported provider '{provider}'. Supported providers: {supported}")
    
    # Get configuration for the provider
    config = provider_configs[provider]()
    
    # Create and return provider instance
    return provider_classes[provider](config)


def _get_openai_config() -> Dict[str, Any]:
    """Get OpenAI provider configuration."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable is required for OpenAI provider")
    
    return {
        "api_key": api_key,
        "model_choice": os.getenv("MODEL_CHOICE", "gpt-4o-mini")
    }


def _get_ollama_config() -> Dict[str, Any]:
    """Get Ollama provider configuration."""
    return {
        "base_url": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        "embedding_model": os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text"),
        "completion_model": os.getenv("OLLAMA_COMPLETION_MODEL", "llama3.2"),
        "model_choice": os.getenv("MODEL_CHOICE", "llama3.2")
    }


def _get_gemini_config() -> Dict[str, Any]:
    """Get Gemini provider configuration."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable is required for Gemini provider")
    
    return {
        "api_key": api_key,
        "model_choice": os.getenv("MODEL_CHOICE", "gemini-1.5-flash")
    }


def _get_deepseek_config() -> Dict[str, Any]:
    """Get DeepSeek provider configuration."""
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise ValueError("DEEPSEEK_API_KEY environment variable is required for DeepSeek provider")
    
    return {
        "api_key": api_key,
        "base_url": os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
        "model_choice": os.getenv("MODEL_CHOICE", "deepseek-chat")
    }


def _get_anthropic_config() -> Dict[str, Any]:
    """Get Anthropic provider configuration."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable is required for Anthropic provider")
    
    return {
        "api_key": api_key,
        "model_choice": os.getenv("MODEL_CHOICE", "claude-3-5-haiku-20241022")
    } 