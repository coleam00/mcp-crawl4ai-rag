#!/usr/bin/env python3
"""Entry point for MCP Crawl4AI RAG server."""

import asyncio
import logging

# Configure logging
logger = logging.getLogger('mcp-crawl4ai-rag')
logger.setLevel(logging.INFO)

# Create handler with formatter
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)

# Add handler to logger
logger.addHandler(handler)


def main() -> None:
    """Run the MCP server."""
    from crawl4ai_mcp.mcp_server import run_server
    
    asyncio.run(run_server())


if __name__ == "__main__":
    main()