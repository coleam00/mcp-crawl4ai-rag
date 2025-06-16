"""
Anthropic provider implementation.
"""

import aiohttp
import json
from typing import List, Dict, Any, Optional
from .base import BaseProvider, EmbeddingResponse, CompletionResponse


class AnthropicProvider(BaseProvider):
    """Anthropic provider implementation."""
    
    def _validate_config(self) -> None:
        """Validate Anthropic configuration."""
        api_key = self.config.get('api_key')
        if not api_key:
            raise ValueError("Anthropic API key is required")
        
        self.api_key = api_key
        self.base_url = "https://api.anthropic.com/v1"
    
    async def create_embeddings(self, texts: List[str], model: Optional[str] = None) -> EmbeddingResponse:
        """
        Create embeddings using Anthropic API.
        Note: Anthropic doesn't have embedding models, so we use a fallback approach.
        """
        if not texts:
            return EmbeddingResponse(embeddings=[])
        
        # Anthropic doesn't have embedding models yet
        print("Warning: Anthropic doesn't support embeddings. Using zero embeddings as fallback.")
        embeddings = [[0.0] * self.embedding_dimension for _ in texts]
        
        return EmbeddingResponse(
            embeddings=embeddings,
            model="anthropic-fallback"
        )
    
    async def create_completion(
        self, 
        messages: List[Dict[str, str]], 
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: Optional[int] = None
    ) -> CompletionResponse:
        """Create completion using Anthropic API."""
        completion_model = model or self.default_completion_model
        
        # Convert messages to Anthropic format
        system_message = ""
        conversation_messages = []
        
        for message in messages:
            role = message.get('role', '')
            content = message.get('content', '')
            
            if role == 'system':
                system_message = content
            elif role == 'user':
                conversation_messages.append({"role": "user", "content": content})
            elif role == 'assistant':
                conversation_messages.append({"role": "assistant", "content": content})
        
        payload = {
            "model": completion_model,
            "messages": conversation_messages,
            "temperature": temperature,
            "max_tokens": max_tokens or 1024
        }
        
        if system_message:
            payload["system"] = system_message
        
        headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/messages",
                    json=payload,
                    headers=headers
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        content_blocks = result.get('content', [])
                        if content_blocks:
                            content = content_blocks[0].get('text', '')
                            usage = result.get('usage', None)
                            
                            return CompletionResponse(
                                content=content,
                                usage=usage,
                                model=completion_model
                            )
                        else:
                            raise Exception("No content in Anthropic response")
                    else:
                        error_text = await response.text()
                        raise Exception(f"Anthropic API error {response.status}: {error_text}")
        except Exception as e:
            print(f"Error creating completion with Anthropic: {e}")
            raise
    
    @property
    def embedding_dimension(self) -> int:
        """Anthropic doesn't have embedding models, using standard dimension."""
        return 1536
    
    @property
    def default_embedding_model(self) -> str:
        """Anthropic doesn't have embedding models."""
        return "anthropic-fallback"
    
    @property
    def default_completion_model(self) -> str:
        """Default Anthropic completion model."""
        return self.config.get('model_choice', 'claude-3-5-haiku-20241022')
    
    @property
    def provider_name(self) -> str:
        """Provider name."""
        return "anthropic" 