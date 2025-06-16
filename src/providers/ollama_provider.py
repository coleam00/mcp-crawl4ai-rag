"""
Ollama provider implementation for local models.
"""

import aiohttp
import json
from typing import List, Dict, Any, Optional
from .base import BaseProvider, EmbeddingResponse, CompletionResponse


class OllamaProvider(BaseProvider):
    """Ollama provider implementation for local models."""
    
    def _validate_config(self) -> None:
        """Validate Ollama configuration."""
        self.base_url = self.config.get('base_url', 'http://localhost:11434')
        self.embedding_model = self.config.get('embedding_model', 'nomic-embed-text')
        self.completion_model = self.config.get('completion_model', 'llama3.2')
        
        # Ensure base_url doesn't end with slash
        if self.base_url.endswith('/'):
            self.base_url = self.base_url[:-1]
    
    async def create_embeddings(self, texts: List[str], model: Optional[str] = None) -> EmbeddingResponse:
        """Create embeddings using Ollama API."""
        if not texts:
            return EmbeddingResponse(embeddings=[])
        
        embedding_model = model or self.default_embedding_model
        embeddings = []
        
        async with aiohttp.ClientSession() as session:
            for text in texts:
                try:
                    payload = {
                        "model": embedding_model,
                        "prompt": text
                    }
                    
                    async with session.post(
                        f"{self.base_url}/api/embeddings",
                        json=payload
                    ) as response:
                        if response.status == 200:
                            result = await response.json()
                            embeddings.append(result.get('embedding', [0.0] * self.embedding_dimension))
                        else:
                            print(f"Ollama embedding error: {response.status}")
                            embeddings.append([0.0] * self.embedding_dimension)
                except Exception as e:
                    print(f"Error creating embedding with Ollama: {e}")
                    embeddings.append([0.0] * self.embedding_dimension)
        
        return EmbeddingResponse(
            embeddings=embeddings,
            model=embedding_model
        )
    
    async def create_completion(
        self, 
        messages: List[Dict[str, str]], 
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: Optional[int] = None
    ) -> CompletionResponse:
        """Create completion using Ollama API."""
        completion_model = model or self.default_completion_model
        
        # Convert messages to prompt format for Ollama
        prompt = self._messages_to_prompt(messages)
        
        payload = {
            "model": completion_model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature
            }
        }
        
        if max_tokens is not None:
            payload["options"]["num_predict"] = max_tokens
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/api/generate",
                    json=payload
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        content = result.get('response', '')
                        
                        return CompletionResponse(
                            content=content,
                            model=completion_model
                        )
                    else:
                        error_text = await response.text()
                        raise Exception(f"Ollama API error {response.status}: {error_text}")
        except Exception as e:
            print(f"Error creating completion with Ollama: {e}")
            raise
    
    def _messages_to_prompt(self, messages: List[Dict[str, str]]) -> str:
        """Convert OpenAI-style messages to a prompt string."""
        prompt_parts = []
        
        for message in messages:
            role = message.get('role', '')
            content = message.get('content', '')
            
            if role == 'system':
                prompt_parts.append(f"System: {content}")
            elif role == 'user':
                prompt_parts.append(f"Human: {content}")
            elif role == 'assistant':
                prompt_parts.append(f"Assistant: {content}")
        
        # Add the assistant prompt at the end
        prompt_parts.append("Assistant:")
        
        return "\n\n".join(prompt_parts)
    
    @property
    def embedding_dimension(self) -> int:
        """Nomic embed text has 768 dimensions."""
        # Different models have different dimensions
        dimension_map = {
            'nomic-embed-text': 768,
            'mxbai-embed-large': 1024,
            'snowflake-arctic-embed': 1024
        }
        return dimension_map.get(self.embedding_model, 768)
    
    @property
    def default_embedding_model(self) -> str:
        """Default Ollama embedding model."""
        return self.embedding_model
    
    @property
    def default_completion_model(self) -> str:
        """Default Ollama completion model."""
        return self.completion_model
    
    @property
    def provider_name(self) -> str:
        """Provider name."""
        return "ollama" 