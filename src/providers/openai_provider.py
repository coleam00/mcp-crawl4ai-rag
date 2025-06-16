"""
OpenAI provider implementation.
"""

import openai
import time
from typing import List, Dict, Any, Optional
from .base import BaseProvider, EmbeddingResponse, CompletionResponse


class OpenAIProvider(BaseProvider):
    """OpenAI provider implementation."""
    
    def _validate_config(self) -> None:
        """Validate OpenAI configuration."""
        api_key = self.config.get('api_key')
        if not api_key:
            raise ValueError("OpenAI API key is required")
        
        # Set the API key
        openai.api_key = api_key
    
    async def create_embeddings(self, texts: List[str], model: Optional[str] = None) -> EmbeddingResponse:
        """Create embeddings using OpenAI API."""
        if not texts:
            return EmbeddingResponse(embeddings=[])
        
        embedding_model = model or self.default_embedding_model
        max_retries = 3
        retry_delay = 1.0
        
        for retry in range(max_retries):
            try:
                response = openai.embeddings.create(
                    model=embedding_model,
                    input=texts
                )
                embeddings = [item.embedding for item in response.data]
                usage = getattr(response, 'usage', None)
                
                return EmbeddingResponse(
                    embeddings=embeddings,
                    usage=usage.__dict__ if usage else None,
                    model=embedding_model
                )
            except Exception as e:
                if retry < max_retries - 1:
                    print(f"Error creating batch embeddings (attempt {retry + 1}/{max_retries}): {e}")
                    print(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    print(f"Failed to create batch embeddings after {max_retries} attempts: {e}")
                    # Try individual embeddings as fallback
                    print("Attempting to create embeddings individually...")
                    embeddings = []
                    successful_count = 0
                    
                    for i, text in enumerate(texts):
                        try:
                            individual_response = openai.embeddings.create(
                                model=embedding_model,
                                input=[text]
                            )
                            embeddings.append(individual_response.data[0].embedding)
                            successful_count += 1
                        except Exception as individual_error:
                            print(f"Failed to create embedding for text {i}: {individual_error}")
                            # Add zero embedding as fallback
                            embeddings.append([0.0] * self.embedding_dimension)
                    
                    print(f"Successfully created {successful_count}/{len(texts)} embeddings individually")
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
        """Create completion using OpenAI API."""
        completion_model = model or self.default_completion_model
        
        kwargs = {
            "model": completion_model,
            "messages": messages,
            "temperature": temperature
        }
        
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        
        try:
            response = openai.chat.completions.create(**kwargs)
            
            content = response.choices[0].message.content.strip()
            usage = getattr(response, 'usage', None)
            
            return CompletionResponse(
                content=content,
                usage=usage.__dict__ if usage else None,
                model=completion_model
            )
        except Exception as e:
            print(f"Error creating completion: {e}")
            raise
    
    @property
    def embedding_dimension(self) -> int:
        """OpenAI text-embedding-3-small has 1536 dimensions."""
        return 1536
    
    @property
    def default_embedding_model(self) -> str:
        """Default OpenAI embedding model."""
        return "text-embedding-3-small"
    
    @property
    def default_completion_model(self) -> str:
        """Default OpenAI completion model."""
        return self.config.get('model_choice', 'gpt-4o-mini')
    
    @property
    def provider_name(self) -> str:
        """Provider name."""
        return "openai" 