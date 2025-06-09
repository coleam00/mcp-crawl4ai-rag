"""MCP server setup and initialization."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from crawl4ai import AsyncWebCrawler, BrowserConfig
from mcp.server.fastmcp import FastMCP
from sentence_transformers import CrossEncoder

from crawl4ai_mcp.config import get_settings
from crawl4ai_mcp.models import CrawlContext

logger = logging.getLogger(__name__)


def get_supabase_client():
    """
    Get Supabase client with configuration from settings.
    
    Returns:
        Client: Configured Supabase client instance
    """
    from supabase import create_client
    
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_service_key)


@asynccontextmanager
async def crawl4ai_lifespan(server: FastMCP) -> AsyncIterator[CrawlContext]:
    """
    Manage the Crawl4AI client lifecycle.
    
    Args:
        server: The FastMCP server instance
        
    Yields:
        CrawlContext: The context containing the Crawl4AI crawler and Supabase client
    """
    settings = get_settings()
    
    # Create browser configuration
    browser_config = BrowserConfig(
        headless=True,
        verbose=False
    )
    
    # Initialize the crawler
    crawler = AsyncWebCrawler(config=browser_config)
    await crawler.__aenter__()
    
    # Initialize Supabase client
    supabase_client = get_supabase_client()
    
    # Initialize cross-encoder model for reranking if enabled
    reranking_model = None
    if settings.use_reranking:
        try:
            reranking_model = CrossEncoder(settings.cross_encoder_model)
        except Exception as e:
            logger.warning(f"Failed to load reranking model: {e}")
            reranking_model = None
    
    # Create context
    context = CrawlContext(
        crawler=crawler,
        supabase_client=supabase_client,
        reranking_model=reranking_model,
        settings=settings
    )
    
    try:
        yield context
    finally:
        # Cleanup
        await crawler.__aexit__(None, None, None)


# Initialize FastMCP server
def create_mcp_server() -> FastMCP:
    """Create and configure the MCP server."""
    settings = get_settings()
    
    return FastMCP(
        "mcp-crawl4ai-rag",
        description="MCP server for RAG and web crawling with Crawl4AI",
        lifespan=crawl4ai_lifespan,
        host=settings.host,
        port=settings.port
    )


# Global server instance
mcp = create_mcp_server()


async def run_server() -> None:
    """Run the MCP server."""
    settings = get_settings()
    
    # Import tools here to avoid circular imports
    from crawl4ai_mcp.tools.crawl_single_page import crawl_single_page  # noqa: F401
    from crawl4ai_mcp.tools.smart_crawl_url import smart_crawl_url  # noqa: F401
    from crawl4ai_mcp.tools.get_available_sources import get_available_sources  # noqa: F401
    from crawl4ai_mcp.tools.perform_rag_query import perform_rag_query  # noqa: F401
    from crawl4ai_mcp.tools.search_code_examples import search_code_examples  # noqa: F401
    
    logger.info(f"Starting MCP server on {settings.host}:{settings.port}")
    logger.info(f"Transport: {settings.transport}")
    
    # Run based on transport
    if settings.transport == "stdio":
        await mcp.run_stdio_async()
    else:
        # SSE transport
        await mcp.run_sse_async()