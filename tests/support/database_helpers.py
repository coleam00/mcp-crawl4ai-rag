"""
Database connection and cleanup helpers for testing.

This module provides utilities for connecting to and cleaning up
Neo4j and Supabase databases during tests.
"""

import os

from dotenv import load_dotenv
from neo4j import AsyncGraphDatabase, AsyncDriver
from supabase import Client, create_client


# Test repository configurations
TEST_REPOSITORIES = {
    "mcp_crawl4ai_rag": {
        "url": "https://github.com/coleam00/mcp-crawl4ai-rag.git",
        "name": "mcp-crawl4ai-rag",
        "description": "Test repository with Python code and documentation",
        "expected_min_files": 5,
        "expected_min_docs": 1,
        "supabase_source_pattern": "%coleam00/mcp-crawl4ai-ra%",
    },
    "hello_world": {
        "url": "https://github.com/octocat/Hello-World.git",
        "name": "Hello-World",
        "description": "Simple test repository with minimal files",
        "expected_min_files": 1,
        "expected_min_docs": 0,
        "supabase_source_pattern": "%Hello-World%",
    },
}


def load_test_environment():
    """Load environment variables for testing."""
    from pathlib import Path

    project_root = Path(__file__).resolve().parent.parent.parent
    dotenv_path = project_root / ".env"
    load_dotenv(dotenv_path, override=True)


async def get_neo4j_client() -> AsyncDriver:
    """Create a Neo4j client for testing."""
    neo4j_uri = os.getenv("NEO4J_URI")
    neo4j_user = os.getenv("NEO4J_USER")
    neo4j_password = os.getenv("NEO4J_PASSWORD")

    if not all([neo4j_uri, neo4j_user, neo4j_password]):
        raise ValueError("Missing required Neo4j environment variables")

    driver = AsyncGraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))

    async with driver.session() as session:
        await session.run("RETURN 1")

    return driver


def get_supabase_client() -> Client:
    """Create a Supabase client for testing."""
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_KEY")

    if not all([supabase_url, supabase_key]):
        raise ValueError("Missing required Supabase environment variables")

    client = create_client(supabase_url, supabase_key)
    # Test connection by querying sources table
    client.table("sources").select("source_id").limit(1).execute()
    return client


async def cleanup_neo4j_test_data(
    driver: AsyncDriver, repo_name: str = "mcp-crawl4ai-rag"
):
    """Clean up Neo4j test data for a specific repository."""
    async with driver.session() as session:
        # First, clean up any orphaned File nodes
        await session.run("""
            MATCH (f:File)
            WHERE NOT EXISTS((f)<-[:CONTAINS]-(:Repository))
            DETACH DELETE f
        """)

        # Delete all nodes related to the specific repository
        await session.run(
            """
            MATCH (r:Repository {name: $repo_name})
            OPTIONAL MATCH (r)-[:CONTAINS]->(f:File)
            OPTIONAL MATCH (f)-[:DEFINES]->(c:Class)
            OPTIONAL MATCH (c)-[:HAS_METHOD]->(m:Method)
            OPTIONAL MATCH (c)-[:HAS_ATTRIBUTE]->(a:Attribute)
            OPTIONAL MATCH (f)-[:DEFINES]->(func:Function)
            DETACH DELETE r, f, c, m, a, func
        """,
            repo_name=repo_name,
        )


def cleanup_supabase_test_data(
    client: Client, repo_pattern: str = "%coleam00/mcp-crawl4ai-ra%"
):
    """Clean up Supabase test data for a specific repository pattern."""
    try:
        # Clean up crawled_pages table
        client.table("crawled_pages").delete().like("source_id", repo_pattern).execute()

        # Clean up sources table
        client.table("sources").delete().like("source_id", repo_pattern).execute()

    except Exception:
        # Table might not exist or might be empty
        pass
