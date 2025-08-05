"""
Simple E2E test to verify environment setup.
"""

import pytest
import os

from tests.support.database_helpers import get_supabase_client, get_neo4j_client


class TestEnvironmentSetup:
    """Basic environment setup tests."""

    def test_environment_variables_present(self):
        """When checking required env vars, then all are present."""
        required_vars = [
            "USE_KNOWLEDGE_GRAPH",
            "NEO4J_URI",
            "NEO4J_USER",
            "NEO4J_PASSWORD",
            "SUPABASE_URL",
            "SUPABASE_SERVICE_KEY",
            "OPENAI_API_KEY",
        ]

        missing_vars = [var for var in required_vars if not os.getenv(var)]
        assert not missing_vars, (
            f"Missing required environment variables: {missing_vars}"
        )

        assert os.getenv("USE_KNOWLEDGE_GRAPH") == "true", (
            "Knowledge graph should be enabled"
        )

    @pytest.mark.asyncio
    async def test_neo4j_connection(self):
        """When connecting to Neo4j, then connection succeeds."""
        neo4j_client = await get_neo4j_client()
        try:
            async with neo4j_client.session() as session:
                result = await session.run("RETURN 1 as test")
                record = await result.single()
                assert record["test"] == 1
        finally:
            await neo4j_client.close()

    def test_supabase_connection(self):
        """When connecting to Supabase, then connection succeeds."""
        # Get Supabase client and test connection
        supabase_client = get_supabase_client()

        # Simple query to verify connection
        result = supabase_client.table("sources").select("source_id").limit(1).execute()
        # Should not raise an exception
        assert isinstance(result.data, list)
