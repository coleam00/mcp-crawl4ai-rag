"""Embeddings service for creating text embeddings using OpenAI."""

import asyncio
import logging
from typing import Any, Callable, List, Optional, Tuple

import openai

from crawl4ai_mcp.config import get_settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service for managing text embeddings using OpenAI API."""
    
    def __init__(self, settings: Optional[Any] = None):
        """
        Initialize embedding service.
        
        Args:
            settings: Application settings (optional)
        """
        self.settings = settings or get_settings()
        self.client = openai.OpenAI(api_key=self.settings.openai_api_key)
        self.max_retries = 3
        self.retry_delay = 1.0
    
    async def _run_in_executor(self, func: Callable[[], Any]) -> Any:
        """
        Run a synchronous function in a thread pool executor.
        
        Args:
            func: Synchronous function to execute
            
        Returns:
            Result from the function execution
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, func)
    
    async def create_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Create embeddings for multiple texts in a single API call.
        
        Args:
            texts: List of texts to create embeddings for
            
        Returns:
            List of embeddings (each embedding is a list of floats)
        """
        if not texts:
            return []
        
        for retry in range(self.max_retries):
            try:
                # Run synchronous OpenAI call in thread pool
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: self.client.embeddings.create(
                        model=self.settings.embedding_model,
                        input=texts
                    )
                )
                
                # Extract embeddings from response
                embeddings = [item.embedding for item in response.data]
                return embeddings
                
            except Exception as e:
                if "rate_limit_exceeded" in str(e).lower() and retry < self.max_retries - 1:
                    wait_time = self.retry_delay * (2 ** retry)
                    logger.warning(f"Rate limit hit. Waiting {wait_time} seconds...")
                    await asyncio.sleep(wait_time)
                    continue
                    
                # If error is not rate limit or last retry, handle batch failure
                if retry == self.max_retries - 1:
                    logger.error(f"Failed to create batch embeddings after {self.max_retries} retries. Creating individual embeddings...")
                    
                    # Fall back to individual embeddings
                    embeddings = []
                    for i, text in enumerate(texts):
                        try:
                            loop = asyncio.get_event_loop()
                            individual_response = await loop.run_in_executor(
                                None,
                                lambda t=text: self.client.embeddings.create(
                                    model=self.settings.embedding_model,
                                    input=[t]
                                )
                            )
                            embeddings.append(individual_response.data[0].embedding)
                            
                            # Add small delay between individual requests
                            if i < len(texts) - 1:
                                await asyncio.sleep(0.1)
                                
                        except Exception as ind_e:
                            logger.error(f"Error creating embedding for text {i}: {ind_e}")
                            # Return zero embedding for failed texts
                            embeddings.append([0.0] * self.settings.embedding_dimensions)
                    
                    return embeddings
        
        # Should not reach here, but return empty embeddings if we do
        return [[0.0] * self.settings.embedding_dimensions for _ in texts]
    
    async def create_embedding(self, text: str) -> List[float]:
        """
        Create an embedding for a single text using OpenAI's API.
        
        Args:
            text: Text to create an embedding for
            
        Returns:
            List of floats representing the embedding
        """
        try:
            embeddings = await self.create_embeddings_batch([text])
            return embeddings[0] if embeddings else [0.0] * self.settings.embedding_dimensions
        except Exception as e:
            logger.error(f"Error creating embedding: {e}")
            # Return zero embedding if there's an error
            return [0.0] * self.settings.embedding_dimensions
    
    async def generate_contextual_embedding(
        self,
        full_document: str,
        chunk: str
    ) -> Tuple[str, bool]:
        """
        Generate contextual information for a chunk within a document to improve retrieval.
        
        Args:
            full_document: The complete document text
            chunk: The specific chunk of text to generate context for
            
        Returns:
            Tuple containing:
            - The contextual text that situates the chunk within the document
            - Boolean indicating if contextual embedding was performed
        """
        try:
            # Create the prompt for generating contextual information
            prompt = f"""<document> 
{full_document[:25000]} 
</document>
Here is the chunk we want to situate within the whole document 
<chunk> 
{chunk} 
</chunk> 
Please give a short succinct context to situate this chunk within the whole document for the purposes of improving search retrieval of the chunk. Answer only with the succinct context and nothing else."""

            # Call the OpenAI API to generate contextual information
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.chat.completions.create(
                    model=self.settings.model_choice,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a helpful assistant that provides concise contextual information."
                        },
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0,
                    max_tokens=200
                )
            )
            
            context = response.choices[0].message.content
            contextual_text = f"{context}\n---\n{chunk}"
            
            return contextual_text, True
            
        except Exception as e:
            logger.error(f"Error generating contextual embedding: {e}. Using original chunk instead.")
            return chunk, False
    
    async def process_chunks_with_context(
        self,
        chunks: List[Tuple[str, str, str]],
        max_workers: int = 10
    ) -> List[Tuple[str, bool]]:
        """
        Process multiple chunks with contextual embedding in parallel.
        
        Args:
            chunks: List of tuples containing (url, content, full_document)
            max_workers: Maximum number of concurrent workers
            
        Returns:
            List of tuples containing (contextual_text, was_contextualized)
        """
        results = []
        
        # Process chunks concurrently
        tasks = []
        for url, content, full_document in chunks:
            task = self.generate_contextual_embedding(full_document, content)
            tasks.append(task)
        
        # Gather results
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle any exceptions in results
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Error processing chunk {i}: {result}")
                # Use original chunk if contextualization failed
                processed_results.append((chunks[i][1], False))
            else:
                processed_results.append(result)
        
        return processed_results
    
    def process_chunk_with_context(self, args: Tuple[str, str, str]) -> Tuple[str, bool]:
        """
        Process a single chunk with contextual embedding (synchronous wrapper).
        
        Args:
            args: Tuple containing (url, content, full_document)
            
        Returns:
            Tuple containing (contextual_text, was_contextualized)
        """
        url, content, full_document = args
        # Create an event loop if needed for synchronous context
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(
            self.generate_contextual_embedding(full_document, content)
        )