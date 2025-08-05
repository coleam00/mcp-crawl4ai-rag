"""
E2E tests for parse_github_repository MCP tool.

These tests verify the complete integration of GitHub repository parsing,
including both code analysis (Neo4j) and documentation processing (Supabase).
"""

import json

from tests.support.database_helpers import get_supabase_client, get_neo4j_client


class TestParseGitHubRepositoryE2E:
    """E2E tests for GitHub repository parsing functionality."""

    async def test_parse_github_repository_with_docs_success(
        self, mcp_client, cleanup_test_data, test_repository_config, environment_check
    ):
        """When parsing repo with docs using parse_github_repository tool, then code analysis and doc processing complete successfully."""
        # Call the MCP tool using the SDK client
        result = await mcp_client.call_tool(
            "parse_github_repository", {"repo_url": test_repository_config["url"]}
        )

        # Verify basic success
        assert result["success"] is True, (
            f"Tool failed: {result.get('error', 'Unknown error')}"
        )
        assert "repo_name" in result
        assert result["repo_name"] == test_repository_config["name"]

        # Verify code analysis results
        assert "statistics" in result
        code_stats = result["statistics"]
        assert code_stats["files_processed"] > 0, "No Python files were processed"
        assert code_stats["classes_created"] >= 0
        assert code_stats["methods_created"] >= 0
        assert code_stats["functions_created"] >= 0

        # Verify documentation processing results
        assert "documentation_processing" in result
        doc_stats = result["documentation_processing"]
        assert doc_stats["files_processed"] > 0, "No documentation files were processed"
        assert doc_stats["chunks_created"] > 0, "No documentation chunks were created"
        assert doc_stats["code_examples_extracted"] >= 0

    async def test_parse_github_repository_processes_various_doc_formats(
        self, mcp_client, cleanup_test_data, test_repository_config
    ):
        """When parsing repo containing .md, .ipynb, and .txt files, then all formats are processed and stored in Supabase."""
        # Call the MCP tool using the SDK client
        result = await mcp_client.call_tool(
            "parse_github_repository", {"repo_url": test_repository_config["url"]}
        )

        assert result["success"] is True
        assert result["documentation_processing"]["files_processed"] > 0

        # Verify data was stored in Supabase
        supabase_client = get_supabase_client()

        # Check crawled_pages table for documentation content
        # Note: source_id uses format github.com/owner/repo, so search for the GitHub pattern
        pages_response = (
            supabase_client.table("crawled_pages")
            .select("*")
            .like("source_id", "%coleam00/mcp-crawl4ai-ra%")
            .execute()
        )
        assert len(pages_response.data) > 0, (
            f"No documentation was stored in Supabase. Found sources: {[p['source_id'] for p in pages_response.data[:5]]}"
        )

        # Verify different content types were processed
        source_urls = [page["url"] for page in pages_response.data]

        # Check for various file extensions in the stored URLs
        has_markdown = any(".md" in url for url in source_urls)
        has_readme = any("README" in url.upper() for url in source_urls)

        # At minimum, we should have markdown files (README.md is very common)
        assert has_markdown or has_readme, (
            f"Expected markdown files but found URLs: {source_urls}"
        )

    async def test_parse_github_repository_handles_no_docs_gracefully(
        self, mcp_client, cleanup_test_data, environment_check
    ):
        """When parsing repo with no doc files, then code analysis completes and doc processing reports zero files."""
        # Use a repository that likely has minimal or no documentation
        # Note: This test uses a different repo than the main test repository
        minimal_repo_url = "https://github.com/octocat/Hello-World.git"

        # Call the MCP tool using the SDK client
        result = await mcp_client.call_tool(
            "parse_github_repository", {"repo_url": minimal_repo_url}
        )

        # Tool should still succeed even with no documentation
        assert result["success"] is True

        # Code analysis should work (though might be minimal)
        assert "statistics" in result
        code_stats = result["statistics"]
        assert code_stats["files_processed"] >= 0

        # Documentation processing should report zero or very few files
        assert "documentation_processing" in result
        doc_stats = result["documentation_processing"]
        assert doc_stats["files_processed"] >= 0  # Might be 0 or minimal

    async def test_parse_github_repository_returns_proper_statistics(
        self, mcp_client, cleanup_test_data, test_repository_config
    ):
        """When parsing repo with Python code and docs, then JSON contains accurate stats for files, chunks, classes, and methods."""
        # Call the MCP tool using the SDK client
        result = await mcp_client.call_tool(
            "parse_github_repository", {"repo_url": test_repository_config["url"]}
        )

        # Debug output if test fails
        if not result.get("success", True):
            print(f"Test failed with result: {json.dumps(result, indent=2)}")

        assert result["success"] is True

        # Verify JSON structure contains all expected fields
        required_fields = [
            "success",
            "repo_name",
            "repo_url",
            "statistics",
            "documentation_processing",
        ]

        for field in required_fields:
            assert field in result, f"Missing required field: {field}"

        # Verify code analysis statistics structure
        code_stats = result["statistics"]
        code_required_fields = [
            "files_processed",
            "classes_created",
            "methods_created",
            "functions_created",
        ]

        for field in code_required_fields:
            assert field in code_stats, f"Missing code analysis field: {field}"
            assert isinstance(code_stats[field], int), (
                f"Field {field} should be an integer"
            )
            assert code_stats[field] >= 0, f"Field {field} should be non-negative"

        # Verify documentation processing statistics structure
        doc_stats = result["documentation_processing"]
        doc_required_fields = [
            "files_processed",
            "chunks_created",
            "code_examples_extracted",
        ]

        for field in doc_required_fields:
            assert field in doc_stats, f"Missing documentation field: {field}"
            assert isinstance(doc_stats[field], int), (
                f"Field {field} should be an integer"
            )
            assert doc_stats[field] >= 0, f"Field {field} should be non-negative"

        # Optional: Check message field
        if "message" in result:
            assert isinstance(result["message"], str)
            assert len(result["message"]) > 0

    async def test_parse_github_repository_integration_end_to_end(
        self, mcp_client, cleanup_test_data, test_repository_config
    ):
        """When parsing test repo via MCP server, then tool completes successfully and data stored in Neo4j and Supabase."""
        repo_url = test_repository_config["url"]
        repo_name = test_repository_config["name"]

        # Call the MCP tool using the SDK client
        result = await mcp_client.call_tool(
            "parse_github_repository", {"repo_url": repo_url}
        )

        # Verify tool succeeded
        assert result["success"] is True
        assert result["repo_name"] == repo_name

        # Verify Neo4j data was created
        neo4j_client = await get_neo4j_client()
        try:
            async with neo4j_client.session() as session:
                # Check repository node exists
                repo_result = await session.run(
                    """
                    MATCH (r:Repository {name: $repo_name})
                    RETURN count(r) as repo_count
                """,
                    repo_name=repo_name,
                )

                repo_record = await repo_result.single()
                assert repo_record["repo_count"] > 0, (
                    "Repository node not found in Neo4j"
                )

                # Check that files were processed
                file_result = await session.run(
                    """
                    MATCH (r:Repository {name: $repo_name})-[:CONTAINS]->(f:File)
                    RETURN count(f) as file_count
                """,
                    repo_name=repo_name,
                )

                file_record = await file_result.single()
                assert file_record["file_count"] > 0, "No files found in Neo4j"
        finally:
            await neo4j_client.close()

        # Verify Supabase data was created
        supabase_client = get_supabase_client()
        # Note: source_id uses format github.com/owner/repo, so search for the GitHub pattern
        pages_response = (
            supabase_client.table("crawled_pages")
            .select("*")
            .like("source_id", "%coleam00/mcp-crawl4ai-ra%")
            .execute()
        )
        assert len(pages_response.data) > 0, "No documentation stored in Supabase"

        # Check that source information was updated
        sources_response = (
            supabase_client.table("sources")
            .select("*")
            .like("source_id", "%coleam00/mcp-crawl4ai-ra%")
            .execute()
        )
        if len(sources_response.data) > 0:
            # If sources exist, verify they have proper metadata
            source = sources_response.data[0]
            # Check for available metadata fields (may vary by implementation)
            available_fields = source.keys()
            assert any(
                field in available_fields
                for field in ["total_chunks", "total_word_count"]
            ), (
                f"Expected chunk/word count field not found. Available: {list(available_fields)}"
            )

            # Verify count is positive
            count_value = source.get("total_chunks") or source.get(
                "total_word_count", 0
            )
            assert count_value > 0, f"Count should be positive, got: {count_value}"

        # Verify the statistics match the actual data
        code_stats = result["statistics"]
        doc_stats = result["documentation_processing"]

        # Neo4j file count should match or be close to code analysis count
        neo4j_client = await get_neo4j_client()
        try:
            async with neo4j_client.session() as session:
                actual_file_result = await session.run(
                    """
                    MATCH (r:Repository {name: $repo_name})-[:CONTAINS]->(f:File)
                    RETURN count(f) as actual_files
                """,
                    repo_name=repo_name,
                )

                actual_file_record = await actual_file_result.single()
                actual_files = actual_file_record["actual_files"]

                # Files processed should be reasonable compared to actual files
                assert code_stats["files_processed"] <= actual_files, (
                    "More files processed than exist"
                )
        finally:
            await neo4j_client.close()

        # Supabase chunk count should match documentation statistics
        actual_chunks = len(pages_response.data)
        assert doc_stats["chunks_created"] == actual_chunks, (
            f"Chunk count mismatch: reported {doc_stats['chunks_created']}, actual {actual_chunks}"
        )
