"""Text processing utilities for chunking, context generation, and content extraction."""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from crawl4ai_mcp.config import get_settings
from crawl4ai_mcp.services.embeddings import EmbeddingService

logger = logging.getLogger(__name__)


class TextProcessor:
    """Utility class for text processing operations."""
    
    def __init__(self, settings: Optional[Any] = None, embedding_service: Optional[EmbeddingService] = None):
        """
        Initialize text processor.
        
        Args:
            settings: Application settings (optional)
            embedding_service: Embedding service instance (optional)
        """
        self.settings = settings or get_settings()
        self.embedding_service = embedding_service or EmbeddingService(self.settings)
    
    def smart_chunk_markdown(self, text: str, chunk_size: int = 5000) -> List[str]:
        """
        Split text into chunks, respecting code blocks and paragraphs.
        
        Args:
            text: Text to chunk
            chunk_size: Target size for each chunk
            
        Returns:
            List of text chunks
        """
        chunks = []
        start = 0
        text_length = len(text)

        while start < text_length:
            # Calculate end position
            end = start + chunk_size

            # If we're at the end of the text, just take what's left
            if end >= text_length:
                chunks.append(text[start:].strip())
                break

            # Try to find a code block boundary first (```)
            chunk = text[start:end]
            code_block = chunk.rfind('```')
            if code_block != -1 and code_block > chunk_size * 0.3:
                end = start + code_block

            # If no code block, try to break at a paragraph
            elif '\n\n' in chunk:
                # Find the last paragraph break
                last_break = chunk.rfind('\n\n')
                if last_break > chunk_size * 0.3:  # Only break if we're past 30% of chunk_size
                    end = start + last_break

            # If no paragraph break, try to break at a sentence
            elif '. ' in chunk:
                # Find the last sentence break
                last_period = chunk.rfind('. ')
                if last_period > chunk_size * 0.3:  # Only break if we're past 30% of chunk_size
                    end = start + last_period + 1

            # Extract chunk and clean it up
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            # Move start position for next chunk
            start = end

        return chunks
    
    def extract_section_info(self, chunk: str) -> Dict[str, Any]:
        """
        Extracts headers and stats from a chunk.
        
        Args:
            chunk: Markdown chunk
            
        Returns:
            Dictionary with headers and stats
        """
        headers = re.findall(r'^(#+)\s+(.+)$', chunk, re.MULTILINE)
        header_str = '; '.join([f'{h[0]} {h[1]}' for h in headers]) if headers else ''

        return {
            "headers": header_str,
            "char_count": len(chunk),
            "word_count": len(chunk.split())
        }
    
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
Please give a short succinct context to situate this chunk within the overall document for the purposes of improving search retrieval of the chunk. Answer only with the succinct context and nothing else."""

            # Use embedding service's OpenAI client
            response = await self.embedding_service._run_in_executor(
                lambda: self.embedding_service.client.chat.completions.create(
                    model=self.settings.model_choice,
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant that provides concise contextual information."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3,
                    max_tokens=200
                )
            )
            
            # Extract the generated context
            context = response.choices[0].message.content.strip()
            
            # Combine the context with the original chunk
            contextual_text = f"{context}\n---\n{chunk}"
            
            return contextual_text, True
        
        except Exception as e:
            logger.error(f"Error generating contextual embedding: {e}. Using original chunk instead.")
            return chunk, False
    
    async def process_chunk_with_context(
        self, 
        url: str,
        content: str,
        full_document: str
    ) -> Tuple[str, bool]:
        """
        Process a single chunk with contextual embedding.
        This is an async wrapper for generate_contextual_embedding.
        
        Args:
            url: URL of the document (not used in processing but kept for compatibility)
            content: The chunk content
            full_document: The full document text
            
        Returns:
            Tuple containing:
            - The contextual text that situates the chunk within the document
            - Boolean indicating if contextual embedding was performed
        """
        return await self.generate_contextual_embedding(full_document, content)
    
    async def process_code_example(
        self,
        code: str,
        context_before: str,
        context_after: str
    ) -> str:
        """
        Process a single code example to generate its summary.
        This is an async wrapper that calls the crawling service's generate_code_example_summary.
        
        Args:
            code: The code example
            context_before: Context before the code
            context_after: Context after the code
            
        Returns:
            The generated summary
        """
        # Import here to avoid circular dependency
        from crawl4ai_mcp.services.crawling import CrawlingService
        
        # Create a temporary crawling service instance
        crawling_service = CrawlingService(
            crawler=None,  # Not needed for summary generation
            settings=self.settings,
            embedding_service=self.embedding_service
        )
        
        return await crawling_service.generate_code_example_summary(
            code, context_before, context_after
        )