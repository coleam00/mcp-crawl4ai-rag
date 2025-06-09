"""Shared pytest fixtures for all tests."""

import pytest
from typing import Any, AsyncIterator
from unittest.mock import Mock, AsyncMock


@pytest.fixture
def test_settings() -> Any:
    """Provide test settings without requiring environment variables."""
    from types import SimpleNamespace
    
    return SimpleNamespace(
        openai_api_key="test-api-key",
        supabase_url="https://test.supabase.co",
        supabase_service_key="test-service-key",
        model_choice="gpt-4o-mini",
        use_contextual_embeddings=False,
        use_hybrid_search=False,
        use_reranking=False,
        use_agentic_rag=False,
        host="0.0.0.0",
        port=8051,
        transport="sse",
        embedding_model="text-embedding-3-small",
        embedding_dimensions=1536,
        cross_encoder_model="cross-encoder/ms-marco-MiniLM-L-6-v2",
        default_max_depth=3,
        default_max_concurrent=10,
        default_chunk_size=5000,
        default_overlap=200,
        default_num_results=5,
        default_semantic_threshold=0.5,
        default_rerank_threshold=0.3,
    )


@pytest.fixture
def mock_supabase_client() -> Mock:
    """Mock Supabase client for testing."""
    client = Mock()
    
    # Mock table operations
    table_mock = Mock()
    table_mock.insert = Mock(return_value=Mock(execute=Mock()))
    table_mock.select = Mock(return_value=Mock(execute=Mock()))
    table_mock.update = Mock(return_value=Mock(execute=Mock()))
    table_mock.delete = Mock(return_value=Mock(execute=Mock()))
    table_mock.rpc = Mock(return_value=Mock(execute=Mock()))
    client.table = Mock(return_value=table_mock)
    
    # Mock RPC operations
    client.rpc = Mock(return_value=Mock(execute=Mock()))
    
    return client


@pytest.fixture
def mock_openai_client() -> Mock:
    """Mock OpenAI client for testing."""
    client = Mock()
    
    # Mock embeddings
    client.embeddings = Mock()
    client.embeddings.create = AsyncMock(return_value=Mock(
        data=[Mock(embedding=[0.1] * 1536)]
    ))
    
    # Mock chat completions
    client.chat = Mock()
    client.chat.completions = Mock()
    client.chat.completions.create = AsyncMock(return_value=Mock(
        choices=[Mock(message=Mock(content="Test response"))]
    ))
    
    return client


@pytest.fixture
def mock_crawler() -> Mock:
    """Mock Crawl4AI crawler for testing."""
    crawler = Mock()
    crawler.arun = AsyncMock(return_value=Mock(
        success=True,
        markdown="# Test Content",
        cleaned_html="<h1>Test Content</h1>",
        extracted_content="Test Content",
        media={"images": [], "videos": [], "audios": []},
        links={"internal": [], "external": []},
        metadata={},
        screenshot=None,
        error_message=None
    ))
    crawler.close = AsyncMock()
    return crawler


@pytest.fixture
def sample_document() -> dict[str, Any]:
    """Sample document for testing."""
    return {
        "url": "https://example.com/test",
        "content": "This is test content for unit testing.",
        "chunk_number": 1,
        "total_chunks": 1,
        "word_count": 7,
        "source": "example.com",
        "metadata": {
            "title": "Test Page",
            "description": "A test page for unit testing"
        }
    }


@pytest.fixture
def sample_code_example() -> dict[str, Any]:
    """Sample code example for testing."""
    return {
        "code": "def hello():\n    print('Hello, world!')",
        "language": "python",
        "context": "A simple hello world function",
        "summary": "Prints hello world",
        "url": "https://example.com/code",
        "source": "example.com"
    }


@pytest.fixture
async def async_iterator(items: list[Any]) -> AsyncIterator[Any]:
    """Create an async iterator from a list of items."""
    for item in items:
        yield item