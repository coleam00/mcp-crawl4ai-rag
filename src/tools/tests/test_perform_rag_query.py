"""Tests for perform_rag_query tool."""

import json
import pytest
from unittest.mock import Mock, AsyncMock, patch
from types import SimpleNamespace

from crawl4ai_mcp.tools.perform_rag_query import perform_rag_query
from crawl4ai_mcp.models import SearchResult, SearchResponse, SearchType


@pytest.fixture
def mock_context():
    """Create mock MCP context."""
    context = Mock()
    
    # Create lifespan context
    lifespan_context = SimpleNamespace(
        supabase_client=Mock(),
        settings=SimpleNamespace(
            use_hybrid_search=False,
            use_reranking=False,
            default_semantic_threshold=0.5,
            default_rerank_threshold=0.3,
            cross_encoder_model="cross-encoder/ms-marco-MiniLM-L-6-v2"
        )
    )
    
    context.request_context.lifespan_context = lifespan_context
    return context


@pytest.fixture
def mock_search_service():
    """Create mock search service."""
    with patch('crawl4ai_mcp.tools.perform_rag_query.SearchService') as MockSearch:
        search_instance = Mock()
        
        # Create sample search results
        results = [
            SearchResult(
                content="First result about machine learning",
                url="https://example.com/ml",
                source="example.com",
                chunk_number=1,
                similarity_score=0.9,
                metadata={"title": "ML Guide"}
            ),
            SearchResult(
                content="Second result about deep learning",
                url="https://example.com/dl",
                source="example.com",
                chunk_number=2,
                similarity_score=0.8,
                metadata={"title": "DL Guide"}
            ),
            SearchResult(
                content="Third result about neural networks",
                url="https://example.com/nn",
                source="example.com",
                chunk_number=3,
                similarity_score=0.7,
                metadata={"title": "NN Guide"}
            )
        ]
        
        search_response = SearchResponse(
            success=True,
            results=results,
            total_results=3,
            search_type=SearchType.SEMANTIC
        )
        
        search_instance.perform_search = AsyncMock(return_value=search_response)
        MockSearch.return_value = search_instance
        
        yield search_instance


@pytest.mark.asyncio
async def test_perform_rag_query_success(mock_context, mock_search_service) -> None:
    """Test successful RAG query."""
    result = await perform_rag_query(
        mock_context,
        query="machine learning algorithms",
        source="example.com",
        match_count=3
    )
    result_data = json.loads(result)
    
    assert result_data["success"] is True
    assert result_data["query"] == "machine learning algorithms"
    assert result_data["search_type"] == "semantic"
    assert result_data["total_results"] == 3
    assert len(result_data["results"]) == 3
    assert result_data["source_filter"] == "example.com"
    assert result_data["reranking_applied"] is False
    
    # Check first result
    first_result = result_data["results"][0]
    assert first_result["content"] == "First result about machine learning"
    assert first_result["url"] == "https://example.com/ml"
    assert first_result["similarity_score"] == 0.9
    assert first_result["metadata"]["title"] == "ML Guide"
    
    # Verify search service was called
    mock_search_service.perform_search.assert_called_once()


@pytest.mark.asyncio
async def test_perform_rag_query_hybrid_search(mock_context, mock_search_service) -> None:
    """Test RAG query with hybrid search enabled."""
    # Enable hybrid search
    mock_context.request_context.lifespan_context.settings.use_hybrid_search = True
    
    # Update mock response to hybrid type
    mock_search_service.perform_search.return_value.search_type = SearchType.HYBRID
    
    result = await perform_rag_query(mock_context, query="test query")
    result_data = json.loads(result)
    
    assert result_data["success"] is True
    assert result_data["search_type"] == "hybrid"
    
    # Verify search was called with hybrid type
    call_args = mock_search_service.perform_search.call_args
    assert call_args[1]["search_type"] == SearchType.HYBRID


@pytest.mark.asyncio
async def test_perform_rag_query_with_reranking(mock_context, mock_search_service) -> None:
    """Test RAG query with reranking enabled."""
    # Enable reranking
    mock_context.request_context.lifespan_context.settings.use_reranking = True
    
    with patch('crawl4ai_mcp.tools.perform_rag_query.CrossEncoder') as MockCrossEncoder, \
         patch('crawl4ai_mcp.tools.perform_rag_query.Reranker') as MockReranker:
        
        # Mock cross encoder
        mock_model = Mock()
        MockCrossEncoder.return_value = mock_model
        
        # Mock reranker
        mock_reranker = Mock()
        # Reorder results (simulate reranking)
        reranked_results = [
            {
                "content": "Second result about deep learning",
                "url": "https://example.com/dl",
                "source": "example.com",
                "chunk_number": 2,
                "similarity_score": 0.8,
                "metadata": {"title": "DL Guide"},
                "rerank_score": 0.95
            },
            {
                "content": "First result about machine learning",
                "url": "https://example.com/ml",
                "source": "example.com",
                "chunk_number": 1,
                "similarity_score": 0.9,
                "metadata": {"title": "ML Guide"},
                "rerank_score": 0.85
            }
        ]
        mock_reranker.rerank_results.return_value = reranked_results
        mock_reranker.filter_by_threshold.return_value = reranked_results
        MockReranker.return_value = mock_reranker
        
        result = await perform_rag_query(mock_context, query="test query")
        result_data = json.loads(result)
        
        assert result_data["success"] is True
        assert result_data["reranking_applied"] is True
        assert len(result_data["results"]) == 2
        
        # Check reranking changed order
        assert result_data["results"][0]["content"] == "Second result about deep learning"
        assert result_data["results"][0]["rerank_score"] == 0.95
        
        # Verify reranking was performed
        mock_reranker.rerank_results.assert_called_once()
        mock_reranker.filter_by_threshold.assert_called_once()


@pytest.mark.asyncio
async def test_perform_rag_query_no_results(mock_context, mock_search_service) -> None:
    """Test RAG query with no results."""
    # Mock empty results
    mock_search_service.perform_search.return_value = SearchResponse(
        success=True,
        results=[],
        total_results=0,
        search_type=SearchType.SEMANTIC
    )
    
    result = await perform_rag_query(mock_context, query="obscure query")
    result_data = json.loads(result)
    
    assert result_data["success"] is True
    assert result_data["total_results"] == 0
    assert result_data["results"] == []
    assert "Found 0 relevant results" in result_data["message"]


@pytest.mark.asyncio
async def test_perform_rag_query_search_failure(mock_context, mock_search_service) -> None:
    """Test handling search failure."""
    # Mock search failure
    mock_search_service.perform_search.return_value = SearchResponse(
        success=False,
        results=[],
        total_results=0,
        search_type=SearchType.SEMANTIC,
        error="Search index unavailable"
    )
    
    result = await perform_rag_query(mock_context, query="test query")
    result_data = json.loads(result)
    
    assert result_data["success"] is False
    assert "Search index unavailable" in result_data["error"]
    assert result_data["results"] == []


@pytest.mark.asyncio
async def test_perform_rag_query_exception(mock_context, mock_search_service) -> None:
    """Test exception handling."""
    # Mock exception
    mock_search_service.perform_search.side_effect = Exception("Database connection failed")
    
    result = await perform_rag_query(mock_context, query="test query")
    result_data = json.loads(result)
    
    assert result_data["success"] is False
    assert "Database connection failed" in result_data["error"]
    assert result_data["query"] == "test query"
    assert result_data["results"] == []


@pytest.mark.asyncio
async def test_perform_rag_query_limit_results(mock_context, mock_search_service) -> None:
    """Test limiting results to match_count."""
    # Request only 2 results
    result = await perform_rag_query(
        mock_context,
        query="test query",
        match_count=2
    )
    result_data = json.loads(result)
    
    assert result_data["success"] is True
    assert len(result_data["results"]) == 2  # Limited to requested count
    assert result_data["total_results"] == 2