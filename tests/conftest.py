"""
Root conftest.py for all test configurations.

This module provides shared fixtures and configurations for both unit and E2E tests.
"""

import asyncio
import os
import pytest
import pytest_asyncio

from tests.support.database_helpers import (
    load_test_environment,
    get_neo4j_client,
    get_supabase_client,
    cleanup_neo4j_test_data,
    cleanup_supabase_test_data,
    TEST_REPOSITORIES,
)
from tests.support.mcp_client import MCPTestClient


# Environment variable requirements
REQUIRED_ENV_VARS = [
    "USE_KNOWLEDGE_GRAPH",
    "NEO4J_URI",
    "NEO4J_USER",
    "NEO4J_PASSWORD",
    "SUPABASE_URL",
    "SUPABASE_SERVICE_KEY",
    "OPENAI_API_KEY",
]


# Load environment for all tests
load_test_environment()


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()

    yield loop

    loop.close()


@pytest.fixture(scope="session")
def test_repository_config():
    """Test repository configuration."""
    return TEST_REPOSITORIES["mcp_crawl4ai_rag"]


@pytest.fixture(scope="session")
def minimal_repository_config():
    """Minimal test repository configuration."""
    return TEST_REPOSITORIES["hello_world"]


@pytest.fixture(scope="function")
def environment_check():
    """Verify required environment variables are present."""
    missing_vars = [var for var in REQUIRED_ENV_VARS if not os.getenv(var)]

    if missing_vars:
        pytest.skip(f"Missing required environment variables: {missing_vars}")

    if os.getenv("USE_KNOWLEDGE_GRAPH") != "true":
        pytest.skip("Knowledge graph not enabled")


@pytest_asyncio.fixture(scope="function")
async def mcp_client():
    """MCP client connected to the running dev server."""
    client = MCPTestClient()

    try:
        await client._connect()
        yield client
    except Exception as e:
        # Only skip if we can't connect initially
        pytest.skip(f"MCP server not available: {e}")
    finally:
        # Manual cleanup without triggering skip
        try:
            if hasattr(client, "session") and client.session:
                await client.session.__aexit__(None, None, None)
        except Exception:
            pass
        try:
            if hasattr(client, "_client_context") and client._client_context:
                await client._client_context.__aexit__(None, None, None)
        except Exception:
            pass


@pytest_asyncio.fixture(scope="function")
async def cleanup_test_data(test_repository_config):
    """Clean up test data before and after tests."""
    repo_name = test_repository_config["name"]
    supabase_pattern = test_repository_config["supabase_source_pattern"]

    async def cleanup():
        neo4j_client = await get_neo4j_client()
        try:
            await cleanup_neo4j_test_data(neo4j_client, repo_name)
        finally:
            await neo4j_client.close()

        supabase_client = get_supabase_client()
        cleanup_supabase_test_data(supabase_client, supabase_pattern)

    # Clean up before test
    await cleanup()

    # Yield control to test
    yield cleanup

    # Clean up after test
    await cleanup()
