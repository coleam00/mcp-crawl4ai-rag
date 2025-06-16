"""Tests for search_code_examples tool."""

import json
import pytest
from unittest.mock import Mock, AsyncMock, patch
from types import SimpleNamespace

from crawl4ai_mcp.tools.search_code_examples import search_code_examples


@pytest.fixture
def mock_context():
    """Create mock MCP context."""
    context = Mock()
    
    # Create lifespan context
    lifespan_context = SimpleNamespace(
        supabase_client=Mock(),
        settings=SimpleNamespace(
            use_agentic_rag=True,
            use_reranking=False,
            default_rerank_threshold=0.3,
            cross_encoder_model="cross-encoder/ms-marco-MiniLM-L-6-v2"
        )
    )
    
    context.request_context.lifespan_context = lifespan_context
    return context


@pytest.fixture
def mock_search_service():
    """Create mock search service."""
    with patch('crawl4ai_mcp.tools.search_code_examples.SearchService') as MockSearch:
        search_instance = Mock()
        
        # Create sample code example results
        code_results = [
            {
                "code": "```python\ndef hello_world():\n    print('Hello, world!')\n```",
                "language": "python",
                "summary": "A simple hello world function in Python",
                "url": "https://example.com/tutorial",
                "source": "example.com",
                "chunk_number": 1,
                "similarity": 0.9,
                "metadata": {"page": "tutorial"}
            },
            {
                "code": "```javascript\nfunction greet(name) {\n    console.log(`Hello, ${name}!`);\n}\n```",
                "language": "javascript",
                "summary": "A greeting function with parameter",
                "url": "https://example.com/examples",
                "source": "example.com",
                "chunk_number": 2,
                "similarity": 0.8,
                "metadata": {"page": "examples"}
            },
            {
                "code": "```python\nclass Greeter:\n    def __init__(self, name):\n        self.name = name\n```",
                "language": "python",
                "summary": "A Greeter class implementation",
                "url": "https://example.com/oop",
                "source": "example.com",
                "chunk_number": 3,
                "similarity": 0.7,
                "metadata": {"page": "oop"}
            }
        ]
        
        search_instance.search_code_examples = AsyncMock(return_value=code_results)
        MockSearch.return_value = search_instance
        
        yield search_instance


@pytest.mark.asyncio
async def test_search_code_examples_success(mock_context, mock_search_service) -> None:
    """Test successful code example search."""
    result = await search_code_examples(
        mock_context,
        query="hello world function",
        source_id="example.com",
        match_count=3
    )
    result_data = json.loads(result)
    
    assert result_data["success"] is True
    assert result_data["query"] == "hello world function"
    assert result_data["total_results"] == 3
    assert len(result_data["results"]) == 3
    assert result_data["source_filter"] == "example.com"
    assert result_data["reranking_applied"] is False
    
    # Check first result
    first_result = result_data["results"][0]
    assert "def hello_world():" in first_result["code"]
    assert first_result["language"] == "python"
    assert first_result["summary"] == "A simple hello world function in Python"
    assert first_result["similarity_score"] == 0.9
    
    # Verify search service was called
    mock_search_service.search_code_examples.assert_called_once_with(
        query="hello world function",
        language=None,
        match_count=6,  # 2x requested for reranking
        source_id="example.com"
    )


@pytest.mark.asyncio
async def test_search_code_examples_disabled(mock_context) -> None:
    """Test when code extraction is disabled."""
    # Disable code extraction
    mock_context.request_context.lifespan_context.settings.use_agentic_rag = False
    
    result = await search_code_examples(mock_context, query="test query")
    result_data = json.loads(result)
    
    assert result_data["success"] is False
    assert "Code example extraction is not enabled" in result_data["error"]
    assert result_data["results"] == []


@pytest.mark.asyncio
async def test_search_code_examples_with_reranking(mock_context, mock_search_service) -> None:
    """Test code search with reranking enabled."""
    # Enable reranking
    mock_context.request_context.lifespan_context.settings.use_reranking = True
    
    with patch('crawl4ai_mcp.tools.search_code_examples.CrossEncoder') as MockCrossEncoder, \
         patch('crawl4ai_mcp.tools.search_code_examples.Reranker') as MockReranker:
        
        # Mock cross encoder
        mock_model = Mock()
        MockCrossEncoder.return_value = mock_model
        
        # Mock reranker - reorder results
        mock_reranker = Mock()
        reranked_results = [
            {
                "code": "```javascript\nfunction greet(name) {\n    console.log(`Hello, ${name}!`);\n}\n```",
                "language": "javascript",
                "summary": "A greeting function with parameter",
                "content": "A greeting function with parameter",  # Added by tool
                "url": "https://example.com/examples",
                "source": "example.com",
                "chunk_number": 2,
                "similarity": 0.8,
                "metadata": {"page": "examples"},
                "rerank_score": 0.95
            },
            {
                "code": "```python\ndef hello_world():\n    print('Hello, world!')\n```",
                "language": "python",
                "summary": "A simple hello world function in Python",
                "content": "A simple hello world function in Python",  # Added by tool
                "url": "https://example.com/tutorial",
                "source": "example.com",
                "chunk_number": 1,
                "similarity": 0.9,
                "metadata": {"page": "tutorial"},
                "rerank_score": 0.85
            }
        ]
        mock_reranker.rerank_results.return_value = reranked_results
        mock_reranker.filter_by_threshold.return_value = reranked_results
        MockReranker.return_value = mock_reranker
        
        result = await search_code_examples(mock_context, query="greeting function")
        result_data = json.loads(result)
        
        assert result_data["success"] is True
        assert result_data["reranking_applied"] is True
        assert len(result_data["results"]) == 2
        
        # Check reranking changed order (JavaScript first now)
        assert result_data["results"][0]["language"] == "javascript"
        assert result_data["results"][0]["rerank_score"] == 0.95
        
        # Verify reranking was performed
        mock_reranker.rerank_results.assert_called_once()
        mock_reranker.filter_by_threshold.assert_called_once()


@pytest.mark.asyncio
async def test_search_code_examples_no_results(mock_context, mock_search_service) -> None:
    """Test when no code examples are found."""
    # Mock empty results
    mock_search_service.search_code_examples.return_value = []
    
    result = await search_code_examples(mock_context, query="obscure code pattern")
    result_data = json.loads(result)
    
    assert result_data["success"] is True
    assert result_data["total_results"] == 0
    assert result_data["results"] == []
    assert "No code examples found" in result_data["message"]


@pytest.mark.asyncio
async def test_search_code_examples_limit_results(mock_context, mock_search_service) -> None:
    """Test limiting results to match_count."""
    # Request only 2 results
    result = await search_code_examples(
        mock_context,
        query="test query",
        match_count=2
    )
    result_data = json.loads(result)
    
    assert result_data["success"] is True
    assert len(result_data["results"]) == 2  # Limited to requested count
    assert result_data["total_results"] == 2


@pytest.mark.asyncio
async def test_search_code_examples_exception(mock_context, mock_search_service) -> None:
    """Test exception handling."""
    # Mock exception
    mock_search_service.search_code_examples.side_effect = Exception("Search index error")
    
    result = await search_code_examples(mock_context, query="test query")
    result_data = json.loads(result)
    
    assert result_data["success"] is False
    assert "Search index error" in result_data["error"]
    assert result_data["query"] == "test query"
    assert result_data["results"] == []


@pytest.mark.asyncio
async def test_search_code_examples_without_source_filter(mock_context, mock_search_service) -> None:
    """Test searching without source filter."""
    result = await search_code_examples(
        mock_context,
        query="hello world",
        source_id=None,  # No source filter
        match_count=5
    )
    result_data = json.loads(result)
    
    assert result_data["success"] is True
    assert result_data["source_filter"] is None
    
    # Verify search was called without source filter
    mock_search_service.search_code_examples.assert_called_once_with(
        query="hello world",
        language=None,
        match_count=10,
        source_id=None
    )