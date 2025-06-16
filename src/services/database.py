"""Database service for Supabase operations."""

import logging
from typing import Any, Dict, List, Optional

from crawl4ai_mcp.config import get_settings
from crawl4ai_mcp.models import SourceInfo

logger = logging.getLogger(__name__)


class DatabaseService:
    """Service for managing database operations with Supabase."""
    
    def __init__(self, client: Any, settings: Optional[Any] = None):
        """
        Initialize database service.
        
        Args:
            client: Supabase client instance
            settings: Application settings (optional)
        """
        self.client = client
        self.settings = settings or get_settings()
    
    async def add_documents(
        self,
        urls: List[str],
        chunk_numbers: List[int],
        contents: List[str],
        embeddings: List[List[float]],
        metadatas: List[Dict[str, Any]],
        url_to_full_document: Dict[str, str],
        batch_size: int = 20
    ) -> Dict[str, Any]:
        """
        Add documents to the Supabase crawled_pages table in batches.
        
        Args:
            urls: List of URLs
            chunk_numbers: List of chunk numbers
            contents: List of document contents
            embeddings: List of embeddings for each content
            metadatas: List of document metadata
            url_to_full_document: Dictionary mapping URLs to their full document content
            batch_size: Size of each batch for insertion
            
        Returns:
            Result dictionary with success status and document count
        """
        # Get unique URLs to delete existing records
        unique_urls = list(set(urls))
        
        # Delete existing records for these URLs in a single operation
        try:
            if unique_urls:
                # Use the .in_() filter to delete all records with matching URLs
                self.client.table("crawled_pages").delete().in_("url", unique_urls).execute()
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to delete existing records: {str(e)}",
                "count": 0
            }
        
        # Process documents in batches
        total_documents = len(urls)
        documents_added = 0
        
        for i in range(0, total_documents, batch_size):
            batch_urls = urls[i:i + batch_size]
            batch_chunk_numbers = chunk_numbers[i:i + batch_size]
            batch_contents = contents[i:i + batch_size]
            batch_embeddings = embeddings[i:i + batch_size]
            batch_metadatas = metadatas[i:i + batch_size]
            
            # Extract source domains
            from urllib.parse import urlparse
            batch_sources = [urlparse(url).netloc for url in batch_urls]
            
            # Prepare batch data for insertion
            batch_data = []
            for j, (url, chunk_num, content, embedding, metadata, source) in enumerate(zip(
                batch_urls, batch_chunk_numbers, batch_contents, 
                batch_embeddings, batch_metadatas, batch_sources
            )):
                batch_data.append({
                    'url': url,
                    'chunk_number': chunk_num,
                    'content': content,
                    'embedding': embedding,
                    'metadata': metadata,
                    'source_id': source  # Fixed: table column is 'source_id' not 'source'
                })
            
            # Insert batch
            try:
                if batch_data:
                    self.client.table('crawled_pages').insert(batch_data).execute()
                    documents_added += len(batch_data)
            except Exception as e:
                logger.error(f"Error inserting batch {i//batch_size + 1}: {e}")
                continue
        
        return {
            "success": True,
            "count": documents_added,
            "total": total_documents
        }
    
    async def add_code_examples(
        self,
        urls: List[str],
        chunk_numbers: List[int],
        code_examples: List[str],
        summaries: List[str],
        embeddings: List[List[float]],
        metadatas: List[Dict[str, Any]],
        batch_size: int = 20
    ) -> Dict[str, Any]:
        """
        Add code examples to the Supabase code_examples table in batches.
        
        Args:
            urls: List of URLs
            chunk_numbers: List of chunk numbers
            code_examples: List of code example contents
            summaries: List of code example summaries
            embeddings: List of embeddings for each summary
            metadatas: List of metadata dictionaries
            batch_size: Size of each batch for insertion
            
        Returns:
            Result dictionary with success status and example count
        """
        if not urls:
            return {"success": True, "count": 0}
            
        # Delete existing records for these URLs
        unique_urls = list(set(urls))
        for url in unique_urls:
            try:
                self.client.table('code_examples').delete().eq('url', url).execute()
            except Exception as e:
                logger.error(f"Error deleting existing code examples for {url}: {e}")
        
        # Process code examples in batches
        total_examples = len(urls)
        examples_added = 0
        
        for i in range(0, total_examples, batch_size):
            batch_urls = urls[i:i + batch_size]
            batch_chunk_numbers = chunk_numbers[i:i + batch_size]
            batch_code_examples = code_examples[i:i + batch_size]
            batch_summaries = summaries[i:i + batch_size]
            batch_embeddings = embeddings[i:i + batch_size]
            batch_metadatas = metadatas[i:i + batch_size]
            
            # Extract source domains
            from urllib.parse import urlparse
            batch_sources = [urlparse(url).netloc for url in batch_urls]
            
            # Prepare batch data
            batch_data = []
            for url, chunk_num, code, summary, embedding, metadata, source in zip(
                batch_urls, batch_chunk_numbers, batch_code_examples,
                batch_summaries, batch_embeddings, batch_metadatas, batch_sources
            ):
                # Extract language from code block if available
                language = "unknown"
                if code.startswith("```"):
                    first_line = code.split('\n')[0]
                    if len(first_line) > 3:
                        language = first_line[3:].strip()
                
                # Add language to metadata
                metadata['language'] = language
                
                batch_data.append({
                    'url': url,
                    'chunk_number': chunk_num,
                    'content': code,  # Fixed: table column is 'content' not 'code'
                    'summary': summary,
                    'embedding': embedding,
                    'metadata': metadata,
                    'source_id': source  # Fixed: table column is 'source_id' not 'source'
                })
            
            # Insert batch
            try:
                if batch_data:
                    self.client.table('code_examples').insert(batch_data).execute()
                    examples_added += len(batch_data)
            except Exception as e:
                logger.error(f"Error inserting code examples batch {i//batch_size + 1}: {e}")
                continue
        
        return {
            "success": True,
            "count": examples_added,
            "total": total_examples
        }
    
    async def update_source_info(
        self,
        source_id: str,
        summary: str,
        word_count: int
    ) -> Dict[str, Any]:
        """
        Update or insert source information in the sources table.
        
        Args:
            source_id: The source ID (domain)
            summary: Summary of the source
            word_count: Total word count for the source
            
        Returns:
            Result dictionary with success status
        """
        try:
            # Try to update existing source
            result = self.client.table('sources').update({
                'summary': summary,
                'total_word_count': word_count,
                'updated_at': 'now()'
            }).eq('source_id', source_id).execute()
            
            # If no rows were updated, insert new source
            if not result.data:
                self.client.table('sources').insert({
                    'source_id': source_id,
                    'summary': summary,
                    'total_word_count': word_count
                }).execute()
                logger.info(f"Created new source: {source_id}")
            else:
                logger.info(f"Updated source: {source_id}")
                
            return {"success": True, "source_id": source_id}
            
        except Exception as e:
            logger.error(f"Error updating source info: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_available_sources(self) -> List[SourceInfo]:
        """
        Get all available sources from the database.
        
        Returns:
            List of SourceInfo objects
        """
        try:
            result = self.client.table('sources').select('*').execute()
            sources = []
            
            for data in result.data:
                # Get document and code example counts
                doc_count = self.client.table('crawled_pages')\
                    .select('*', count='exact')\
                    .eq('source_id', data['source_id'])\
                    .execute()
                
                code_count = self.client.table('code_examples')\
                    .select('*', count='exact')\
                    .eq('source_id', data['source_id'])\
                    .execute()
                
                # Get total chunks
                chunk_result = self.client.table('crawled_pages')\
                    .select('chunk_number')\
                    .eq('source_id', data['source_id'])\
                    .execute()
                
                total_chunks = len(chunk_result.data) if chunk_result.data else 0
                
                sources.append(SourceInfo(
                    source=data['source_id'],
                    total_documents=doc_count.count if hasattr(doc_count, 'count') else 0,
                    total_chunks=total_chunks,
                    total_code_examples=code_count.count if hasattr(code_count, 'count') else 0,
                    word_count=data.get('total_word_count', 0),
                    last_updated=data.get('updated_at', data.get('created_at')),
                    summary=data.get('summary')
                ))
            
            return sources
            
        except Exception as e:
            logger.error(f"Error getting available sources: {e}")
            return []
    
    
    def _generate_contextual_content(
        self,
        chunk_content: str,
        full_document: str,
        chunk_number: int
    ) -> str:
        """
        Generate contextual content for a chunk.
        
        Args:
            chunk_content: The content of the current chunk
            full_document: The full document content
            chunk_number: The chunk number
            
        Returns:
            Contextual content string
        """
        # This is a simplified version - the actual implementation
        # would be in the embeddings service
        return f"Chunk {chunk_number} of document: {chunk_content}"