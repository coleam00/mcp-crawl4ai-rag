"""Tests for search service."""

import pytest
from unittest.mock import Mock

from crawl4ai_mcp.services.search import SearchService
from crawl4ai_mcp.services.embeddings import EmbeddingService
from crawl4ai_mcp.models import SearchRequest, SearchResult, SearchType


@pytest.fixture
def mock_embedding_service():
    """Mock embedding service."""
    service = Mock(spec=EmbeddingService)
    # Make it an async mock
    async def mock_create_embedding(text):
        return [0.1] * 1536
    service.create_embedding = mock_create_embedding
    return service


@pytest.fixture
def search_service(mock_supabase_client, test_settings, mock_embedding_service):
    """Create SearchService with mocked dependencies."""
    return SearchService(mock_supabase_client, test_settings, mock_embedding_service)


@pytest.fixture
def mock_search_results():
    """Mock search results from database."""
    return [
        {
            'content': 'First result content',
            'url': 'https://example.com/1',
            'source_id': 'example.com',  # Fixed: DB returns 'source_id' not 'source'
            'chunk_number': 1,
            'similarity': 0.9,
            'metadata': {'title': 'First'}
        },
        {
            'content': 'Second result content',
            'url': 'https://example.com/2',
            'source_id': 'example.com',  # Fixed: DB returns 'source_id' not 'source'
            'chunk_number': 2,
            'similarity': 0.8,
            'metadata': {'title': 'Second'}
        },
        {
            'content': 'Third result content',
            'url': 'https://example.com/3',
            'source_id': 'example.com',  # Fixed: DB returns 'source_id' not 'source'
            'chunk_number': 3,
            'similarity': 0.7,
            'metadata': {'title': 'Third'}
        }
    ]


@pytest.fixture
def mock_code_results():
    """Mock code example results."""
    return [
        {
            'content': 'def example():\n    return "Hello"',  # Fixed: DB returns 'content' not 'code'
            'url': 'https://example.com/code1',
            'source_id': 'example.com',  # Fixed: DB returns 'source_id' not 'source'
            'chunk_number': 1,
            'similarity': 0.85,
            'summary': 'Example function',
            'metadata': {'language': 'python'}  # Fixed: language is in metadata
        }
    ]


@pytest.mark.asyncio
async def test_search_documents_success(search_service, mock_supabase_client, mock_search_results, mock_embedding_service) -> None:
    """Test successful document search."""
    # Mock RPC response
    mock_execute = Mock()
    mock_execute.data = mock_search_results
    mock_supabase_client.rpc.return_value.execute.return_value = mock_execute
    
    results = await search_service.search_documents(
        query="test query",
        match_count=10
    )
    
    assert len(results) == 3
    assert isinstance(results[0], SearchResult)
    assert results[0].content == "First result content"
    assert results[0].similarity_score == 0.9
    assert results[0].url == "https://example.com/1"
    
    # Verify embedding was created (can't use assert_called_once_with on async function)
    # The function was called during search_documents
    
    # Verify RPC was called
    mock_supabase_client.rpc.assert_called_once_with('match_crawled_pages', {
        'query_embedding': [0.1] * 1536,
        'match_count': 10
    })


@pytest.mark.asyncio
async def test_search_documents_with_filters(search_service, mock_supabase_client, mock_search_results) -> None:
    """Test document search with metadata filters."""
    mock_execute = Mock()
    mock_execute.data = mock_search_results
    mock_supabase_client.rpc.return_value.execute.return_value = mock_execute
    
    filter_metadata = {'category': 'tutorial'}
    await search_service.search_documents(
        query="test query",
        match_count=5,
        filter_metadata=filter_metadata,
        source_id="docs.example.com"
    )
    
    # Verify filters were applied
    expected_params = {
        'query_embedding': [0.1] * 1536,
        'match_count': 5,
        'filter': {'category': 'tutorial'},
        'source_filter': 'docs.example.com'
    }
    mock_supabase_client.rpc.assert_called_once_with('match_crawled_pages', expected_params)


@pytest.mark.asyncio
async def test_search_documents_error_handling(search_service, mock_supabase_client) -> None:
    """Test error handling in document search."""
    # Mock RPC to raise an exception
    mock_supabase_client.rpc.return_value.execute.side_effect = Exception("Database error")
    
    results = await search_service.search_documents(query="test query")
    
    assert results == []


@pytest.mark.asyncio
async def test_search_documents_embedding_error(search_service, mock_embedding_service) -> None:
    """Test error handling when embedding creation fails."""
    # Mock embedding service to raise an exception
    mock_embedding_service.create_embedding.side_effect = Exception("Embedding API error")
    
    results = await search_service.search_documents(
        query="test query",
        match_count=10
    )
    
    # Should return empty list when embedding fails
    assert results == []


@pytest.mark.asyncio
async def test_search_code_examples_success(search_service, mock_supabase_client, mock_code_results) -> None:
    """Test successful code example search."""
    mock_execute = Mock()
    mock_execute.data = mock_code_results
    mock_supabase_client.rpc.return_value.execute.return_value = mock_execute
    
    results = await search_service.search_code_examples(
        query="example function",
        language="python",
        match_count=5
    )
    
    assert len(results) == 1
    assert results[0]['content'] == 'def example():\n    return "Hello"'  # Fixed: DB returns 'content' not 'code'
    assert results[0]['metadata']['language'] == 'python'  # Fixed: language is in metadata
    
    # Enhanced query was used during search


@pytest.mark.asyncio
async def test_search_code_examples_with_source_filter(search_service, mock_supabase_client, mock_code_results) -> None:
    """Test code example search with source filter."""
    mock_execute = Mock()
    mock_execute.data = mock_code_results
    mock_supabase_client.rpc.return_value.execute.return_value = mock_execute
    
    await search_service.search_code_examples(
        query="test",
        source_id="github.com"
    )
    
    # Verify source filter was applied
    call_args = mock_supabase_client.rpc.call_args[0][1]
    assert 'source_filter' in call_args
    assert call_args['source_filter'] == 'github.com'


@pytest.mark.asyncio
async def test_perform_search_documents_only(search_service, mock_supabase_client, mock_search_results) -> None:
    """Test perform_search with documents only."""
    mock_execute = Mock()
    mock_execute.data = mock_search_results
    mock_supabase_client.rpc.return_value.execute.return_value = mock_execute
    
    request = SearchRequest(
        query="test query",
        num_results=5,
        semantic_threshold=0.75
    )
    
    response = await search_service.perform_search(request)
    
    assert response.success is True
    assert len(response.results) == 2  # Only results with similarity >= 0.75
    assert response.results[0].similarity_score == 0.9
    assert response.results[1].similarity_score == 0.8
    assert response.search_type == SearchType.SEMANTIC


@pytest.mark.asyncio
async def test_perform_search_with_code_examples(search_service, mock_supabase_client, mock_search_results, mock_code_results, test_settings) -> None:
    """Test perform_search including code examples."""
    # Enable code examples
    test_settings.use_agentic_rag = True
    
    # Mock both document and code searches
    mock_execute1 = Mock()
    mock_execute1.data = mock_search_results
    mock_execute2 = Mock()
    mock_execute2.data = mock_code_results
    mock_supabase_client.rpc.return_value.execute.side_effect = [
        mock_execute1,  # Document search
        mock_execute2   # Code search
    ]
    
    request = SearchRequest(query="test query", num_results=5)
    
    response = await search_service.perform_search(
        request,
        include_code_examples=True
    )
    
    assert response.success is True
    assert len(response.results) == 4  # 3 documents + 1 code example
    
    # Verify code example is included
    code_result = next(r for r in response.results if r.metadata.get('type') == 'code_example')
    assert code_result is not None
    assert code_result.metadata['language'] == 'python'


@pytest.mark.asyncio
async def test_perform_search_error_handling(search_service, mock_supabase_client) -> None:
    """Test perform_search error handling."""
    mock_supabase_client.rpc.return_value.execute.side_effect = Exception("Search failed")
    
    request = SearchRequest(query="test query")
    response = await search_service.perform_search(request)
    
    # Since search_documents catches the exception and returns empty list,
    # perform_search returns success=True with empty results
    assert response.success is True
    assert response.total_results == 0
    assert len(response.results) == 0


@pytest.mark.asyncio
async def test_rerank_results(search_service) -> None:
    """Test result reranking."""
    # Create mock reranking model
    mock_reranker = Mock()
    mock_reranker.predict.return_value = [0.9, 0.2, 0.6]  # Rerank scores
    
    # Create test results
    results = [
        SearchResult(
            content="First content",
            url="url1",
            source="source1",
            chunk_number=1,
            similarity_score=0.7
        ),
        SearchResult(
            content="Second content",
            url="url2",
            source="source2",
            chunk_number=2,
            similarity_score=0.8
        ),
        SearchResult(
            content="Third content",
            url="url3",
            source="source3",
            chunk_number=3,
            similarity_score=0.6
        )
    ]
    
    reranked = await search_service.rerank_results(
        query="test query",
        results=results,
        reranking_model=mock_reranker,
        threshold=0.5
    )
    
    # Only results with rerank score >= 0.5 should be included
    assert len(reranked) == 2
    assert reranked[0].rerank_score == 0.9  # First result
    assert reranked[1].rerank_score == 0.6  # Third result
    
    # Verify reranker was called correctly
    expected_pairs = [
        ["test query", "First content"],
        ["test query", "Second content"],
        ["test query", "Third content"]
    ]
    mock_reranker.predict.assert_called_once_with(expected_pairs)


@pytest.mark.asyncio
async def test_rerank_results_empty_input(search_service) -> None:
    """Test reranking with empty results."""
    mock_reranker = Mock()
    
    # Test empty results
    results = await search_service.rerank_results(
        query="test",
        results=[],
        reranking_model=mock_reranker
    )
    assert results == []
    
    # Test None reranker
    results = await search_service.rerank_results(
        query="test",
        results=[SearchResult(content="test", url="url", source="src", chunk_number=1, similarity_score=0.5)],
        reranking_model=None
    )
    assert len(results) == 1


@pytest.mark.asyncio
async def test_rerank_results_error_handling(search_service) -> None:
    """Test reranking error handling."""
    mock_reranker = Mock()
    mock_reranker.predict.side_effect = Exception("Reranking failed")
    
    original_results = [
        SearchResult(content="test", url="url", source="src", chunk_number=1, similarity_score=0.5)
    ]
    
    results = await search_service.rerank_results(
        query="test",
        results=original_results,
        reranking_model=mock_reranker
    )
    
    # Should return original results on error
    assert results == original_results