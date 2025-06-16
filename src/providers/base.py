"""
Base provider interface for AI services.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Union


@dataclass
class EmbeddingResponse:
    """Response from embedding creation."""
    embeddings: List[List[float]]
    usage: Optional[Dict[str, Any]] = None
    model: Optional[str] = None


@dataclass
class CompletionResponse:
    """Response from completion generation."""
    content: str
    usage: Optional[Dict[str, Any]] = None
    model: Optional[str] = None


class BaseProvider(ABC):
    """Base class for AI providers."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the provider with configuration.
        
        Args:
            config: Provider-specific configuration dictionary
        """
        self.config = config
        self._validate_config()
    
    @abstractmethod
    def _validate_config(self) -> None:
        """Validate provider configuration."""
        pass
    
    @abstractmethod
    async def create_embeddings(self, texts: List[str], model: Optional[str] = None) -> EmbeddingResponse:
        """
        Create embeddings for a list of texts.
        
        Args:
            texts: List of texts to embed
            model: Optional model name override
            
        Returns:
            EmbeddingResponse containing embeddings and metadata
        """
        pass
    
    @abstractmethod
    async def create_completion(
        self, 
        messages: List[Dict[str, str]], 
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: Optional[int] = None
    ) -> CompletionResponse:
        """
        Create a completion from messages.
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
            model: Optional model name override
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            
        Returns:
            CompletionResponse containing generated content and metadata
        """
        pass
    
    @property
    @abstractmethod
    def embedding_dimension(self) -> int:
        """Get the dimension of embeddings from this provider."""
        pass
    
    @property
    @abstractmethod
    def default_embedding_model(self) -> str:
        """Get the default embedding model for this provider."""
        pass
    
    @property
    @abstractmethod
    def default_completion_model(self) -> str:
        """Get the default completion model for this provider."""
        pass
    
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Get the name of this provider."""
        pass 