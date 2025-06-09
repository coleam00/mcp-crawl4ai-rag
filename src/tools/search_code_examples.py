"""Tool for searching code examples."""

import json
from sentence_transformers import CrossEncoder

from mcp.server.fastmcp import Context

from crawl4ai_mcp.mcp_server import mcp
from crawl4ai_mcp.services.search import SearchService
from crawl4ai_mcp.utilities.reranking import Reranker
from crawl4ai_mcp.models import CrawlContext


@mcp.tool()
async def search_code_examples(
    ctx: Context,
    query: str,
    source_id: str = None,
    match_count: int = 5
) -> str:
    """
    Search for code examples in the stored content.
    
    This tool searches through code examples that were extracted during crawling.
    It uses semantic search to find relevant code snippets based on the query.
    Results can be filtered by source and are reranked for relevance if enabled.
    
    Args:
        ctx: The MCP server provided context
        query: The search query describing what kind of code you're looking for
        source_id: Optional source ID to filter results (e.g., 'github.com')
        match_count: Maximum number of results to return (default: 5)
    
    Returns:
        Code examples matching the query with their summaries and metadata
    """
    try:
        # Get context
        context: CrawlContext = ctx.request_context.lifespan_context
        supabase_client = context.supabase_client
        settings = context.settings
        
        # Check if code extraction is enabled
        if not settings.use_agentic_rag:
            return json.dumps({
                "success": False,
                "error": "Code example extraction is not enabled. Set USE_AGENTIC_RAG=true to enable it.",
                "results": []
            })
        
        # Initialize services
        search_service = SearchService(supabase_client, settings)
        
        # Search for code examples
        results = await search_service.search_code_examples(
            query=query,
            language=None,  # Could be extracted from query in future
            match_count=match_count * 2,  # Get more for reranking
            source_id=source_id
        )
        
        if not results:
            return json.dumps({
                "success": True,
                "query": query,
                "results": [],
                "total_results": 0,
                "message": "No code examples found matching the query"
            })
        
        # Apply reranking if enabled
        if settings.use_reranking and results:
            # Initialize reranker
            model = CrossEncoder(settings.cross_encoder_model)
            reranker = Reranker(model=model, settings=settings)
            
            # Prepare results for reranking - use summary as content
            for result in results:
                result["content"] = result.get("summary", result.get("code", ""))
            
            # Rerank results
            reranked = reranker.rerank_results(query, results, content_key="content")
            
            # Filter by threshold
            reranked = reranker.filter_by_threshold(
                reranked, 
                threshold=settings.default_rerank_threshold
            )
            
            # Use reranked results
            results = reranked
        
        # Format results
        formatted_results = []
        for result in results[:match_count]:  # Limit to requested count
            formatted_result = {
                "code": result.get("code", ""),
                "language": result.get("language", "unknown"),
                "summary": result.get("summary", ""),
                "url": result.get("url", ""),
                "source": result.get("source", ""),
                "chunk_number": result.get("chunk_number", 0),
                "similarity_score": result.get("similarity", 0.0),
                "metadata": result.get("metadata", {})
            }
            
            # Add rerank score if available
            if "rerank_score" in result:
                formatted_result["rerank_score"] = result["rerank_score"]
            
            formatted_results.append(formatted_result)
        
        return json.dumps({
            "success": True,
            "query": query,
            "results": formatted_results,
            "total_results": len(formatted_results),
            "source_filter": source_id,
            "reranking_applied": settings.use_reranking,
            "message": f"Found {len(formatted_results)} code examples"
        })
        
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e),
            "query": query,
            "results": []
        })