"""Search service for document and code example retrieval."""

import logging
from typing import Any, Dict, List, Optional

from crawl4ai_mcp.config import get_settings
from crawl4ai_mcp.models import SearchRequest, SearchResult, SearchResponse, SearchType
from crawl4ai_mcp.services.embeddings import EmbeddingService

logger = logging.getLogger(__name__)


class SearchService:
    """Service for searching documents and code examples."""
    
    def __init__(self, client: Any, settings: Optional[Any] = None, embedding_service: Optional[EmbeddingService] = None):
        """
        Initialize search service.
        
        Args:
            client: Supabase client instance
            settings: Application settings (optional)
            embedding_service: Embedding service instance (optional)
        """
        self.client = client
        self.settings = settings or get_settings()
        self.embedding_service = embedding_service or EmbeddingService(self.settings)
    
    async def search_documents(
        self,
        query: str,
        match_count: int = 10,
        filter_metadata: Optional[Dict[str, Any]] = None,
        source_id: Optional[str] = None,
        use_hybrid_search: Optional[bool] = None
    ) -> List[SearchResult]:
        """
        Search for documents using vector similarity.
        
        Args:
            query: Search query text
            match_count: Maximum number of results to return
            filter_metadata: Optional metadata filter
            source_id: Optional source ID to filter results
            use_hybrid_search: Whether to use hybrid search (overrides settings)
            
        Returns:
            List of SearchResult objects
        """
        try:
            # Create embedding for the query
            query_embedding = await self.embedding_service.create_embedding(query)
        except Exception as e:
            logger.error(f"Error creating query embedding: {e}")
            return []
        
        # Build RPC parameters
        params = {
            'query_embedding': query_embedding,
            'match_count': match_count
        }
        
        # Add metadata filter if provided
        if filter_metadata:
            params['filter'] = filter_metadata
        
        # Add source filter if provided
        if source_id:
            params['source_filter'] = source_id
        
        # Execute the search
        try:
            result = self.client.rpc('match_crawled_pages', params).execute()
            
            # Convert results to SearchResult objects
            search_results = []
            for doc in result.data:
                search_results.append(SearchResult(
                    content=doc.get('content', ''),
                    url=doc.get('url', ''),
                    source=doc.get('source_id', ''),  # Fixed: DB returns source_id
                    chunk_number=doc.get('chunk_number', 0),
                    similarity_score=doc.get('similarity', 0.0),
                    metadata=doc.get('metadata', {})
                ))
            
            return search_results
            
        except Exception as e:
            logger.error(f"Error searching documents: {e}")
            return []
    
    async def search_code_examples(
        self,
        query: str,
        language: Optional[str] = None,
        match_count: int = 10,
        filter_metadata: Optional[Dict[str, Any]] = None,
        source_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for code examples using vector similarity.
        
        Args:
            query: Search query text
            language: Optional programming language filter
            match_count: Maximum number of results to return
            filter_metadata: Optional metadata filter
            source_id: Optional source ID to filter results
            
        Returns:
            List of matching code examples
        """
        # Enhance query for better code example matching
        enhanced_query = f"Code example for {query}"
        if language:
            enhanced_query += f" in {language}"
        enhanced_query += f"\n\nSummary: Example code showing {query}"
        
        try:
            # Create embedding for the enhanced query
            query_embedding = await self.embedding_service.create_embedding(enhanced_query)
        except Exception as e:
            logger.error(f"Error creating code example query embedding: {e}")
            return []
        
        # Build RPC parameters
        params = {
            'query_embedding': query_embedding,
            'match_count': match_count
        }
        
        # Add metadata filter if provided
        if filter_metadata:
            params['filter'] = filter_metadata
        
        # Add source filter if provided
        if source_id:
            params['source_filter'] = source_id
        
        # Add language filter if provided
        if language:
            if not filter_metadata:
                filter_metadata = {}
            filter_metadata['language'] = language
            params['filter'] = filter_metadata
        
        # Execute the search
        try:
            result = self.client.rpc('match_code_examples', params).execute()
            return result.data
        except Exception as e:
            logger.error(f"Error searching code examples: {e}")
            return []
    
    async def perform_search(
        self,
        request: SearchRequest,
        search_type: SearchType = SearchType.SEMANTIC,
        include_code_examples: bool = False
    ) -> SearchResponse:
        """
        Perform a search based on request parameters.
        
        Args:
            request: SearchRequest object with search parameters
            search_type: Type of search to perform
            include_code_examples: Whether to include code examples in results
            
        Returns:
            SearchResponse object with results
        """
        try:
            # Search documents
            results = await self.search_documents(
                query=request.query,
                match_count=request.num_results,
                filter_metadata=None,  # Source filtering is handled by source_id parameter
                source_id=request.source,
                use_hybrid_search=(search_type == SearchType.HYBRID)
            )
            
            # Filter by semantic threshold if specified
            if request.semantic_threshold > 0:
                results = [
                    r for r in results 
                    if r.similarity_score >= request.semantic_threshold
                ]
            
            # Search code examples if requested
            code_results = []
            if include_code_examples and self.settings.use_agentic_rag:
                code_data = await self.search_code_examples(
                    query=request.query,
                    match_count=request.num_results,
                    source_id=request.source
                )
                
                # Convert code examples to SearchResult objects
                for code_ex in code_data:
                    code_results.append(SearchResult(
                        content=code_ex.get('content', ''),  # Fixed: DB returns content not code
                        url=code_ex.get('url', ''),
                        source=code_ex.get('source_id', ''),  # Fixed: DB returns source_id
                        chunk_number=code_ex.get('chunk_number', 0),
                        similarity_score=code_ex.get('similarity', 0.0),
                        metadata={
                            'type': 'code_example',
                            'language': code_ex.get('metadata', {}).get('language', 'unknown'),  # Language is in metadata
                            'summary': code_ex.get('summary', ''),
                            **code_ex.get('metadata', {})
                        }
                    ))
            
            # Combine results
            all_results = results + code_results
            
            # Sort by similarity score
            all_results.sort(key=lambda x: x.similarity_score, reverse=True)
            
            # Limit to requested number
            all_results = all_results[:request.num_results]
            
            return SearchResponse(
                success=True,
                results=all_results,
                total_results=len(all_results),
                search_type=search_type
            )
            
        except Exception as e:
            return SearchResponse(
                success=False,
                results=[],
                total_results=0,
                search_type=search_type,
                error=str(e)
            )
    
    async def rerank_results(
        self,
        query: str,
        results: List[SearchResult],
        reranking_model: Any,
        threshold: float = 0.3
    ) -> List[SearchResult]:
        """
        Rerank search results using a cross-encoder model.
        
        Args:
            query: Original search query
            results: List of search results to rerank
            reranking_model: Cross-encoder model for reranking
            threshold: Minimum score threshold for reranked results
            
        Returns:
            Reranked and filtered list of SearchResult objects
        """
        if not results or not reranking_model:
            return results
        
        try:
            # Prepare pairs for reranking
            pairs = [[query, result.content] for result in results]
            
            # Get reranking scores
            scores = reranking_model.predict(pairs)
            
            # Update results with rerank scores
            for i, (result, score) in enumerate(zip(results, scores)):
                result.rerank_score = float(score)
            
            # Filter by threshold
            reranked_results = [
                r for r in results 
                if r.rerank_score is not None and r.rerank_score >= threshold
            ]
            
            # Sort by rerank score
            reranked_results.sort(key=lambda x: x.rerank_score or 0, reverse=True)
            
            return reranked_results
            
        except Exception as e:
            logger.error(f"Error during reranking: {e}")
            # Return original results if reranking fails
            return results