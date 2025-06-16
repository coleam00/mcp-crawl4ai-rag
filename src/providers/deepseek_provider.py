"""
DeepSeek provider implementation.
"""

import aiohttp
import json
from typing import List, Dict, Any, Optional
from .base import BaseProvider, EmbeddingResponse, CompletionResponse


class DeepSeekProvider(BaseProvider):
    """DeepSeek provider implementation."""
    
    def _validate_config(self) -> None:
        """Validate DeepSeek configuration."""
        api_key = self.config.get('api_key')
        if not api_key:
            raise ValueError("DeepSeek API key is required")
        
        self.api_key = api_key
        self.base_url = self.config.get('base_url', 'https://api.deepseek.com/v1')
        
        # Ensure base_url doesn't end with slash
        if self.base_url.endswith('/'):
            self.base_url = self.base_url[:-1]
    
    async def create_embeddings(self, texts: List[str], model: Optional[str] = None) -> EmbeddingResponse:
        """
        Create embeddings using DeepSeek API.
        Note: DeepSeek doesn't have a native embedding API, so we use OpenAI-compatible format
        or fall back to a basic text similarity approach.
        """
        if not texts:
            return EmbeddingResponse(embeddings=[])
        
        # For now, since DeepSeek doesn't have embedding models,
        # we'll use a simple approach or recommend using another provider for embeddings
        print("Warning: DeepSeek doesn't support embeddings. Using zero embeddings as fallback.")
        embeddings = [[0.0] * self.embedding_dimension for _ in texts]
        
        return EmbeddingResponse(
            embeddings=embeddings,
            model="deepseek-fallback"
        )
    
    async def create_completion(
        self, 
        messages: List[Dict[str, str]], 
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: Optional[int] = None
    ) -> CompletionResponse:
        """Create completion using DeepSeek API."""
        completion_model = model or self.default_completion_model
        
        payload = {
            "model": completion_model,
            "messages": messages,
            "temperature": temperature,
            "stream": False
        }
        
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=headers
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        choices = result.get('choices', [])
                        if choices:
                            content = choices[0].get('message', {}).get('content', '')
                            usage = result.get('usage', None)
                            
                            return CompletionResponse(
                                content=content,
                                usage=usage,
                                model=completion_model
                            )
                        else:
                            raise Exception("No choices in DeepSeek response")
                    else:
                        error_text = await response.text()
                        raise Exception(f"DeepSeek API error {response.status}: {error_text}")
        except Exception as e:
            print(f"Error creating completion with DeepSeek: {e}")
            raise
    
    @property
    def embedding_dimension(self) -> int:
        """DeepSeek doesn't have embedding models, using standard dimension."""
        return 1536
    
    @property
    def default_embedding_model(self) -> str:
        """DeepSeek doesn't have embedding models."""
        return "deepseek-fallback"
    
    @property
    def default_completion_model(self) -> str:
        """Default DeepSeek completion model."""
        return self.config.get('model_choice', 'deepseek-chat')
    
    @property
    def provider_name(self) -> str:
        """Provider name."""
        return "deepseek" 