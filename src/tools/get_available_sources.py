"""Tool for retrieving available sources from database."""

import json

from mcp.server.fastmcp import Context

from crawl4ai_mcp.mcp_server import mcp
from crawl4ai_mcp.services.database import DatabaseService
from crawl4ai_mcp.models import CrawlContext


@mcp.tool()
async def get_available_sources(ctx: Context) -> str:
    """
    Get a list of all available sources in the database.
    
    This tool retrieves information about all the sources that have been crawled and stored,
    including their summaries, document counts, and last update times.
    
    Args:
        ctx: The MCP server provided context
    
    Returns:
        List of available sources with their metadata
    """
    try:
        # Get context
        context: CrawlContext = ctx.request_context.lifespan_context
        supabase_client = context.supabase_client
        settings = context.settings
        
        # Initialize database service
        database_service = DatabaseService(supabase_client, settings)
        
        # Get available sources
        sources = await database_service.get_available_sources()
        
        # Convert to list of dictionaries for JSON serialization
        sources_data = []
        for source in sources:
            sources_data.append({
                "source": source.source,
                "summary": source.summary,
                "total_documents": source.total_documents,
                "total_chunks": source.total_chunks,
                "total_code_examples": source.total_code_examples,
                "word_count": source.word_count,
                "last_updated": source.last_updated.isoformat() if source.last_updated else None
            })
        
        return json.dumps({
            "success": True,
            "sources": sources_data,
            "total_sources": len(sources_data),
            "message": f"Found {len(sources_data)} available sources"
        })
        
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e),
            "sources": [],
            "total_sources": 0
        })