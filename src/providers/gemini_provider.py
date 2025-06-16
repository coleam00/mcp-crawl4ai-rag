"""
Google Gemini provider implementation.
"""

import aiohttp
import json
from typing import List, Dict, Any, Optional
from .base import BaseProvider, EmbeddingResponse, CompletionResponse


class GeminiProvider(BaseProvider):
    """Google Gemini provider implementation."""
    
    def _validate_config(self) -> None:
        """Validate Gemini configuration."""
        api_key = self.config.get('api_key')
        if not api_key:
            raise ValueError("Google Gemini API key is required")
        
        self.api_key = api_key
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"
    
    async def create_embeddings(self, texts: List[str], model: Optional[str] = None) -> EmbeddingResponse:
        """Create embeddings using Gemini API."""
        if not texts:
            return EmbeddingResponse(embeddings=[])
        
        embedding_model = model or self.default_embedding_model
        embeddings = []
        
        async with aiohttp.ClientSession() as session:
            for text in texts:
                try:
                    url = f"{self.base_url}/models/{embedding_model}:embedContent"
                    payload = {
                        "content": {
                            "parts": [{"text": text}]
                        }
                    }
                    
                    async with session.post(
                        url,
                        json=payload,
                        params={"key": self.api_key}
                    ) as response:
                        if response.status == 200:
                            result = await response.json()
                            embedding = result.get('embedding', {}).get('values', [0.0] * self.embedding_dimension)
                            embeddings.append(embedding)
                        else:
                            error_text = await response.text()
                            print(f"Gemini embedding error {response.status}: {error_text}")
                            embeddings.append([0.0] * self.embedding_dimension)
                except Exception as e:
                    print(f"Error creating embedding with Gemini: {e}")
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
        """Create completion using Gemini API."""
        completion_model = model or self.default_completion_model
        
        # Convert messages to Gemini format
        contents = self._messages_to_gemini_format(messages)
        
        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature
            }
        }
        
        if max_tokens is not None:
            payload["generationConfig"]["maxOutputTokens"] = max_tokens
        
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/models/{completion_model}:generateContent"
                async with session.post(
                    url,
                    json=payload,
                    params={"key": self.api_key}
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        candidates = result.get('candidates', [])
                        if candidates:
                            content = candidates[0].get('content', {}).get('parts', [{}])[0].get('text', '')
                            
                            return CompletionResponse(
                                content=content,
                                model=completion_model
                            )
                        else:
                            raise Exception("No candidates in Gemini response")
                    else:
                        error_text = await response.text()
                        raise Exception(f"Gemini API error {response.status}: {error_text}")
        except Exception as e:
            print(f"Error creating completion with Gemini: {e}")
            raise
    
    def _messages_to_gemini_format(self, messages: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """Convert OpenAI-style messages to Gemini format."""
        contents = []
        
        for message in messages:
            role = message.get('role', '')
            content = message.get('content', '')
            
            # Map roles
            if role == 'system':
                # System messages can be included as user messages in Gemini
                contents.append({
                    "role": "user",
                    "parts": [{"text": f"[System] {content}"}]
                })
            elif role == 'user':
                contents.append({
                    "role": "user",
                    "parts": [{"text": content}]
                })
            elif role == 'assistant':
                contents.append({
                    "role": "model",
                    "parts": [{"text": content}]
                })
        
        return contents
    
    @property
    def embedding_dimension(self) -> int:
        """Gemini text-embedding-004 has 768 dimensions."""
        return 768
    
    @property
    def default_embedding_model(self) -> str:
        """Default Gemini embedding model."""
        return "text-embedding-004"
    
    @property
    def default_completion_model(self) -> str:
        """Default Gemini completion model."""
        return self.config.get('model_choice', 'gemini-1.5-flash')
    
    @property
    def provider_name(self) -> str:
        """Provider name."""
        return "gemini" 