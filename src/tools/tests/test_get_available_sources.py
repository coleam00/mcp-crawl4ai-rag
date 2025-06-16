"""Tests for get_available_sources tool."""

import json
import pytest
from unittest.mock import Mock, AsyncMock, patch
from types import SimpleNamespace

from datetime import datetime
from crawl4ai_mcp.tools.get_available_sources import get_available_sources
from crawl4ai_mcp.models import SourceInfo


@pytest.fixture
def mock_context():
    """Create mock MCP context."""
    context = Mock()
    
    # Create lifespan context
    lifespan_context = SimpleNamespace(
        supabase_client=Mock(),
        settings=SimpleNamespace()
    )
    
    context.request_context.lifespan_context = lifespan_context
    return context


@pytest.fixture
def mock_database_service():
    """Create mock database service."""
    with patch('crawl4ai_mcp.tools.get_available_sources.DatabaseService') as MockDatabase:
        database_instance = Mock()
        
        # Mock source data
        sources = [
            SourceInfo(
                source="example.com",
                summary="Example website for testing",
                total_documents=10,
                total_chunks=25,
                total_code_examples=5,
                word_count=5000,
                last_updated="2024-01-01T00:00:00Z"
            ),
            SourceInfo(
                source="docs.python.org",
                summary="Python documentation",
                total_documents=50,
                total_chunks=150,
                total_code_examples=30,
                word_count=25000,
                last_updated="2024-01-02T00:00:00Z"
            )
        ]
        
        database_instance.get_available_sources = AsyncMock(return_value=sources)
        MockDatabase.return_value = database_instance
        
        yield database_instance


@pytest.mark.asyncio
async def test_get_available_sources_success(mock_context, mock_database_service) -> None:
    """Test successful retrieval of available sources."""
    result = await get_available_sources(mock_context)
    result_data = json.loads(result)
    
    # Debug print to see what's returned
    if not result_data.get("success"):
        print(f"Error in result: {result_data}")
    
    assert result_data["success"] is True
    assert result_data["total_sources"] == 2
    assert len(result_data["sources"]) == 2
    
    # Check first source
    first_source = result_data["sources"][0]
    assert first_source["source"] == "example.com"
    assert first_source["summary"] == "Example website for testing"
    assert first_source["total_documents"] == 10
    assert first_source["total_chunks"] == 25
    assert first_source["total_code_examples"] == 5
    assert first_source["word_count"] == 5000
    assert first_source["last_updated"] == "2024-01-01T00:00:00+00:00"
    
    # Check second source
    second_source = result_data["sources"][1]
    assert second_source["source"] == "docs.python.org"
    assert second_source["summary"] == "Python documentation"
    assert second_source["total_documents"] == 50
    
    # Verify service was called
    mock_database_service.get_available_sources.assert_called_once()


@pytest.mark.asyncio
async def test_get_available_sources_empty(mock_context, mock_database_service) -> None:
    """Test when no sources are available."""
    # Mock empty sources
    mock_database_service.get_available_sources.return_value = []
    
    result = await get_available_sources(mock_context)
    result_data = json.loads(result)
    
    assert result_data["success"] is True
    assert result_data["total_sources"] == 0
    assert result_data["sources"] == []
    assert "Found 0 available sources" in result_data["message"]


@pytest.mark.asyncio
async def test_get_available_sources_exception(mock_context, mock_database_service) -> None:
    """Test exception handling."""
    # Mock exception
    mock_database_service.get_available_sources.side_effect = Exception("Database error")
    
    result = await get_available_sources(mock_context)
    result_data = json.loads(result)
    
    assert result_data["success"] is False
    assert "Database error" in result_data["error"]
    assert result_data["sources"] == []
    assert result_data["total_sources"] == 0


@pytest.mark.asyncio
async def test_get_available_sources_partial_data(mock_context, mock_database_service) -> None:
    """Test handling sources with missing optional fields."""
    # Mock source with minimal data
    sources = [
        SourceInfo(
            source="minimal.com",
            summary=None,  # No summary
            total_documents=0,
            total_chunks=0,
            total_code_examples=0,
            word_count=0,
            last_updated=datetime.now()  # Valid datetime required
        )
    ]
    
    mock_database_service.get_available_sources.return_value = sources
    
    result = await get_available_sources(mock_context)
    result_data = json.loads(result)
    
    assert result_data["success"] is True
    assert result_data["total_sources"] == 1
    
    source = result_data["sources"][0]
    assert source["source"] == "minimal.com"
    assert source["summary"] is None
    assert source["total_documents"] == 0
    assert source["last_updated"] is not None  # Should have a datetime string