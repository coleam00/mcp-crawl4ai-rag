"""
MCP client helpers for testing.

This module provides utilities for connecting to and interacting with
the MCP server during tests using the official MCP library.
"""

import asyncio
import json
from typing import Any, Dict, Optional
from datetime import timedelta

from mcp.client.sse import sse_client
from mcp.client.session import ClientSession


# MCP server configuration
MCP_SERVER_CONFIG = {
    "default_host": "localhost",
    "default_port": "8051",
    "health_check_timeout": 30,
    "tool_call_timeout": 300,
    "sse_endpoint": "/sse",
}


class MCPTestClient:
    """Test client for interacting with the MCP server via HTTP/SSE."""

    def __init__(self, server_url: str = None):
        """
        Initialize MCP test client.

        Args:
            server_url: URL of the MCP server. If None, uses default localhost:8051/sse
        """
        self.server_url = server_url or self._build_server_url()
        self.session: Optional[ClientSession] = None
        self._client_context = None
        self._available_tools = []

    def _build_server_url(self) -> str:
        """Build the server URL from configuration."""
        host = MCP_SERVER_CONFIG["default_host"]
        port = MCP_SERVER_CONFIG["default_port"]
        endpoint = MCP_SERVER_CONFIG["sse_endpoint"]
        return f"http://{host}:{port}{endpoint}"

    async def __aenter__(self):
        """Async context manager entry."""
        await self._connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._client_context:
            await self._client_context.__aexit__(exc_type, exc_val, exc_tb)

    async def _connect(self):
        """Connect to the MCP server."""
        client_context = None
        try:
            # Connect to the MCP server via SSE
            client_context = sse_client(self.server_url)

            # Get the streams from the client
            read_stream, write_stream = await client_context.__aenter__()

            # Create and initialize the session
            self.session = ClientSession(
                read_stream=read_stream,
                write_stream=write_stream,
                read_timeout_seconds=timedelta(
                    seconds=MCP_SERVER_CONFIG["tool_call_timeout"]
                ),
            )

            # Initialize the session
            await self.session.__aenter__()
            await self.session.initialize()

            # Get available tools
            tools_result = await self.session.list_tools()
            self._available_tools = [tool.name for tool in tools_result.tools]
            
            # Only set the client context after everything succeeds
            self._client_context = client_context

        except Exception as e:
            # Clean up the client context if it was successfully created
            if client_context:
                try:
                    await client_context.__aexit__(type(e), e, e.__traceback__)
                except Exception:
                    # Ignore cleanup errors to avoid masking the original exception
                    pass
            raise RuntimeError(
                f"Failed to connect to MCP server at {self.server_url}: {e}"
            ) from e

    async def call_tool(
        self, tool_name: str, arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Call an MCP tool and return the result.

        Args:
            tool_name: Name of the tool to call
            arguments: Arguments to pass to the tool

        Returns:
            Tool result as a dictionary

        Raises:
            RuntimeError: If not connected or tool call fails
        """
        if not self.session:
            raise RuntimeError(
                "Not connected to MCP server. Use as async context manager."
            )

        if tool_name not in self._available_tools:
            raise RuntimeError(
                f"Tool '{tool_name}' not found. Available tools: {self._available_tools}"
            )

        try:
            # Call the tool through the MCP session
            result = await self.session.call_tool(tool_name, arguments)

            # Process the result based on content type
            if hasattr(result, "content") and result.content:
                # Handle text content
                text_content = []
                for content in result.content:
                    if hasattr(content, "text"):
                        text_content.append(content.text)

                if text_content:
                    # Try to parse as JSON if it looks like JSON
                    combined_text = "\n".join(text_content)
                    try:
                        return json.loads(combined_text)
                    except json.JSONDecodeError:
                        return {"text": combined_text}

            # Check for structured content
            if hasattr(result, "structuredContent") and result.structuredContent:
                return result.structuredContent

            # Fallback to raw result
            return {"raw_result": str(result)}

        except Exception as e:
            raise RuntimeError(f"Tool call failed: {e}") from e

    async def list_tools(self) -> list:
        """List available tools from the MCP server."""
        if not self.session:
            raise RuntimeError(
                "Not connected to MCP server. Use as async context manager."
            )

        return self._available_tools.copy()

    async def health_check(self) -> bool:
        """Check if the MCP server is reachable and responsive."""
        try:
            async with MCPTestClient(self.server_url) as client:
                tools = await client.list_tools()
                return len(tools) > 0
        except Exception:
            return False


async def wait_for_mcp_server(max_attempts: int = 30, delay: float = 1.0) -> bool:
    """
    Wait for MCP server to be ready via HTTP/SSE connection.

    Args:
        max_attempts: Maximum number of connection attempts
        delay: Delay between attempts in seconds

    Returns:
        True if server is ready, False if timeout
    """
    client = MCPTestClient()

    for attempt in range(max_attempts):
        if await client.health_check():
            return True

        if attempt < max_attempts - 1:  # Don't sleep on the last attempt
            await asyncio.sleep(delay)

    return False
