"""Tests for embeddings service."""

import pytest
from unittest.mock import Mock, patch

from crawl4ai_mcp.services.embeddings import EmbeddingService


@pytest.fixture
def embedding_service(test_settings):
    """Create EmbeddingService with test settings."""
    return EmbeddingService(test_settings)


@pytest.fixture
def mock_openai_response():
    """Mock OpenAI embeddings response."""
    mock_response = Mock()
    mock_response.data = [
        Mock(embedding=[0.1] * 1536),
        Mock(embedding=[0.2] * 1536),
        Mock(embedding=[0.3] * 1536)
    ]
    return mock_response


@pytest.fixture
def mock_chat_response():
    """Mock OpenAI chat completion response."""
    mock_response = Mock()
    mock_response.choices = [
        Mock(message=Mock(content="This chunk discusses the main topic of the document."))
    ]
    return mock_response


@pytest.mark.asyncio
async def test_create_embeddings_batch_success(embedding_service, mock_openai_response) -> None:
    """Test successful batch embedding creation."""
    with patch.object(embedding_service.client.embeddings, 'create', return_value=mock_openai_response):
        texts = ["text1", "text2", "text3"]
        embeddings = await embedding_service.create_embeddings_batch(texts)
        
        assert len(embeddings) == 3
        assert len(embeddings[0]) == 1536
        assert embeddings[0][0] == 0.1
        assert embeddings[1][0] == 0.2
        assert embeddings[2][0] == 0.3


@pytest.mark.asyncio
async def test_create_embeddings_batch_empty_list(embedding_service) -> None:
    """Test embedding creation with empty list."""
    embeddings = await embedding_service.create_embeddings_batch([])
    assert embeddings == []


@pytest.mark.asyncio
async def test_create_embeddings_batch_rate_limit_retry(embedding_service) -> None:
    """Test retry logic on rate limit errors."""
    # Create custom mock response with 2 embeddings
    mock_response = Mock()
    mock_response.data = [
        Mock(embedding=[0.1] * 1536),
        Mock(embedding=[0.2] * 1536)
    ]
    
    # First call raises rate limit error, second succeeds
    with patch.object(
        embedding_service.client.embeddings,
        'create',
        side_effect=[
            Exception("rate_limit_exceeded"),
            mock_response
        ]
    ):
        texts = ["text1", "text2"]
        embeddings = await embedding_service.create_embeddings_batch(texts)
        
        assert len(embeddings) == 2
        assert embedding_service.client.embeddings.create.call_count == 2


@pytest.mark.asyncio
async def test_create_embeddings_batch_fallback_to_individual(embedding_service) -> None:
    """Test fallback to individual embeddings on batch failure."""
    # Mock individual responses
    individual_responses = [
        Mock(data=[Mock(embedding=[0.1] * 1536)]),
        Mock(data=[Mock(embedding=[0.2] * 1536)])
    ]
    
    # First 3 calls fail (retries), then individual calls succeed
    with patch.object(
        embedding_service.client.embeddings,
        'create',
        side_effect=[
            Exception("API error"),
            Exception("API error"),
            Exception("API error"),
            *individual_responses
        ]
    ):
        texts = ["text1", "text2"]
        embeddings = await embedding_service.create_embeddings_batch(texts)
        
        assert len(embeddings) == 2
        assert len(embeddings[0]) == 1536
        assert embeddings[0][0] == 0.1
        assert embeddings[1][0] == 0.2
        # Should have 3 failed batch attempts + 2 individual calls
        assert embedding_service.client.embeddings.create.call_count == 5


@pytest.mark.asyncio
async def test_create_embeddings_batch_partial_failure(embedding_service) -> None:
    """Test handling of partial failures in individual embeddings."""
    # First 3 batch attempts fail, then individual calls with one failure
    with patch.object(
        embedding_service.client.embeddings,
        'create',
        side_effect=[
            Exception("API error"),
            Exception("API error"),
            Exception("API error"),
            Mock(data=[Mock(embedding=[0.1] * 1536)]),
            Exception("Individual call failed"),
            Mock(data=[Mock(embedding=[0.3] * 1536)])
        ]
    ):
        texts = ["text1", "text2", "text3"]
        embeddings = await embedding_service.create_embeddings_batch(texts)
        
        assert len(embeddings) == 3
        assert embeddings[0][0] == 0.1
        assert embeddings[1][0] == 0.0  # Failed embedding should be zeros
        assert embeddings[2][0] == 0.3


@pytest.mark.asyncio
async def test_create_embedding_success(embedding_service) -> None:
    """Test single embedding creation."""
    mock_response = Mock()
    mock_response.data = [Mock(embedding=[0.5] * 1536)]
    
    with patch.object(embedding_service.client.embeddings, 'create', return_value=mock_response):
        embedding = await embedding_service.create_embedding("test text")
        
        assert len(embedding) == 1536
        assert embedding[0] == 0.5


@pytest.mark.asyncio
async def test_create_embedding_failure(embedding_service) -> None:
    """Test single embedding creation failure."""
    with patch.object(embedding_service.client.embeddings, 'create', side_effect=Exception("API error")):
        embedding = await embedding_service.create_embedding("test text")
        
        assert len(embedding) == 1536
        assert all(val == 0.0 for val in embedding)


@pytest.mark.asyncio
async def test_generate_contextual_embedding_success(embedding_service, mock_chat_response) -> None:
    """Test successful contextual embedding generation."""
    with patch.object(embedding_service.client.chat.completions, 'create', return_value=mock_chat_response):
        full_doc = "This is a document about Python programming..."
        chunk = "Functions in Python are defined using the def keyword."
        
        contextual_text, was_contextualized = await embedding_service.generate_contextual_embedding(
            full_doc, chunk
        )
        
        assert was_contextualized is True
        assert "This chunk discusses the main topic of the document." in contextual_text
        assert chunk in contextual_text
        assert "---" in contextual_text


@pytest.mark.asyncio
async def test_generate_contextual_embedding_failure(embedding_service) -> None:
    """Test contextual embedding generation failure."""
    with patch.object(
        embedding_service.client.chat.completions,
        'create',
        side_effect=Exception("API error")
    ):
        full_doc = "This is a document about Python programming..."
        chunk = "Functions in Python are defined using the def keyword."
        
        contextual_text, was_contextualized = await embedding_service.generate_contextual_embedding(
            full_doc, chunk
        )
        
        assert was_contextualized is False
        assert contextual_text == chunk  # Should return original chunk on failure


@pytest.mark.asyncio
async def test_process_chunks_with_context_success(embedding_service, mock_chat_response) -> None:
    """Test processing multiple chunks with context."""
    with patch.object(embedding_service.client.chat.completions, 'create', return_value=mock_chat_response):
        chunks = [
            ("url1", "chunk1", "full_doc1"),
            ("url2", "chunk2", "full_doc2"),
            ("url3", "chunk3", "full_doc3")
        ]
        
        results = await embedding_service.process_chunks_with_context(chunks)
        
        assert len(results) == 3
        for contextual_text, was_contextualized in results:
            assert was_contextualized is True
            assert "This chunk discusses the main topic of the document." in contextual_text


@pytest.mark.asyncio
async def test_process_chunks_with_context_mixed_results(embedding_service, mock_chat_response) -> None:
    """Test processing chunks with mixed success/failure."""
    # First and third succeed, second fails
    with patch.object(
        embedding_service.client.chat.completions,
        'create',
        side_effect=[mock_chat_response, Exception("API error"), mock_chat_response]
    ):
        chunks = [
            ("url1", "chunk1", "full_doc1"),
            ("url2", "chunk2", "full_doc2"),
            ("url3", "chunk3", "full_doc3")
        ]
        
        results = await embedding_service.process_chunks_with_context(chunks)
        
        assert len(results) == 3
        # First chunk succeeded
        assert results[0][1] is True
        assert "This chunk discusses the main topic of the document." in results[0][0]
        # Second chunk failed
        assert results[1][1] is False
        assert results[1][0] == "chunk2"
        # Third chunk succeeded
        assert results[2][1] is True


def test_process_chunk_with_context_sync(embedding_service, mock_chat_response) -> None:
    """Test synchronous wrapper for chunk processing."""
    with patch.object(embedding_service.client.chat.completions, 'create', return_value=mock_chat_response):
        args = ("url", "chunk content", "full document")
        contextual_text, was_contextualized = embedding_service.process_chunk_with_context(args)
        
        assert was_contextualized is True
        assert "chunk content" in contextual_text


@pytest.mark.asyncio
async def test_long_document_truncation(embedding_service, mock_chat_response) -> None:
    """Test that long documents are truncated properly."""
    with patch.object(embedding_service.client.chat.completions, 'create', return_value=mock_chat_response) as mock_create:
        # Create a very long document
        full_doc = "x" * 30000
        chunk = "test chunk"
        
        await embedding_service.generate_contextual_embedding(full_doc, chunk)
        
        # Check that the prompt was created with truncated document
        call_args = mock_create.call_args
        messages = call_args[1]['messages']
        user_message = messages[1]['content']
        
        # Document should be truncated to 25000 characters
        assert len(user_message) < 26000  # Some overhead for prompt template