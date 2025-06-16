"""Tests for smart_crawl_url tool."""

import json
import pytest
from unittest.mock import Mock, AsyncMock, patch
from types import SimpleNamespace

from crawl4ai_mcp.tools.smart_crawl_url import smart_crawl_url


@pytest.fixture
def mock_context():
    """Create mock MCP context."""
    context = Mock()
    
    # Create lifespan context
    lifespan_context = SimpleNamespace(
        crawler=Mock(),
        supabase_client=Mock(),
        settings=SimpleNamespace(
            default_chunk_size=5000,
            use_contextual_embeddings=False,
            use_agentic_rag=False
        )
    )
    
    context.request_context.lifespan_context = lifespan_context
    return context


@pytest.fixture
def mock_services():
    """Create mock services."""
    with patch('crawl4ai_mcp.tools.smart_crawl_url.EmbeddingService') as MockEmbedding, \
         patch('crawl4ai_mcp.tools.smart_crawl_url.DatabaseService') as MockDatabase, \
         patch('crawl4ai_mcp.tools.smart_crawl_url.CrawlingService') as MockCrawling, \
         patch('crawl4ai_mcp.tools.smart_crawl_url.TextProcessor') as MockTextProcessor:
        
        # Mock embedding service
        embedding_instance = Mock()
        embedding_instance.create_embedding = AsyncMock(return_value=[0.1] * 1536)
        MockEmbedding.return_value = embedding_instance
        
        # Mock database service
        database_instance = Mock()
        database_instance.update_source_info = AsyncMock(return_value={"success": True})
        database_instance.add_documents = AsyncMock(return_value={"success": True, "count": 3})
        database_instance.add_code_examples = AsyncMock(return_value={"success": True, "count": 2})
        MockDatabase.return_value = database_instance
        
        # Mock crawling service
        crawling_instance = Mock()
        crawling_instance.is_txt = Mock(return_value=False)
        crawling_instance.is_sitemap = Mock(return_value=False)
        crawling_instance.crawl_markdown_file = AsyncMock(return_value=[])
        crawling_instance.parse_sitemap = Mock(return_value=[])
        crawling_instance.crawl_batch = AsyncMock(return_value=[])
        crawling_instance.crawl_recursive_internal_links = AsyncMock(return_value=[
            {"url": "https://example.com", "markdown": "# Page 1"},
            {"url": "https://example.com/page2", "markdown": "# Page 2"}
        ])
        crawling_instance.extract_source_summary = AsyncMock(return_value="Test source summary")
        crawling_instance.extract_code_blocks = Mock(return_value=[])
        crawling_instance.generate_code_example_summary = AsyncMock(return_value="Code summary")
        MockCrawling.return_value = crawling_instance
        
        # Mock text processor
        text_processor_instance = Mock()
        text_processor_instance.smart_chunk_markdown = Mock(return_value=["Chunk 1", "Chunk 2"])
        text_processor_instance.extract_section_info = Mock(return_value={
            "headers": "# Test",
            "char_count": 100,
            "word_count": 20
        })
        text_processor_instance.generate_contextual_embedding = AsyncMock(
            return_value=("Contextual chunk", True)
        )
        MockTextProcessor.return_value = text_processor_instance
        
        yield {
            'embedding': embedding_instance,
            'database': database_instance,
            'crawling': crawling_instance,
            'text_processor': text_processor_instance
        }


@pytest.mark.asyncio
async def test_smart_crawl_recursive(mock_context, mock_services) -> None:
    """Test recursive crawling for regular URL."""
    result = await smart_crawl_url(
        mock_context, 
        "https://example.com",
        max_depth=3,
        max_concurrent=5
    )
    result_data = json.loads(result)
    
    assert result_data["success"] is True
    assert result_data["crawl_type"] == "recursive"
    assert result_data["urls_processed"] == 2
    assert result_data["total_chunks_created"] == 6  # 3 chunks per URL, 2 URLs
    assert "example.com" in result_data["sources_updated"]
    
    # Verify crawling service was called correctly
    mock_services['crawling'].crawl_recursive_internal_links.assert_called_once_with(
        ["https://example.com"], max_depth=3, max_concurrent=5
    )


@pytest.mark.asyncio
async def test_smart_crawl_txt_file(mock_context, mock_services) -> None:
    """Test crawling a txt file."""
    # Mock txt file detection
    mock_services['crawling'].is_txt.return_value = True
    mock_services['crawling'].crawl_markdown_file.return_value = [
        {"url": "https://example.com/file.txt", "markdown": "Text content"}
    ]
    
    result = await smart_crawl_url(mock_context, "https://example.com/file.txt")
    result_data = json.loads(result)
    
    assert result_data["success"] is True
    assert result_data["crawl_type"] == "txt file"
    assert result_data["urls_processed"] == 1
    
    # Verify txt file crawling was used
    mock_services['crawling'].is_txt.assert_called_with("https://example.com/file.txt")
    mock_services['crawling'].crawl_markdown_file.assert_called_once()


@pytest.mark.asyncio
async def test_smart_crawl_sitemap(mock_context, mock_services) -> None:
    """Test crawling a sitemap."""
    # Mock sitemap detection
    mock_services['crawling'].is_txt.return_value = False
    mock_services['crawling'].is_sitemap.return_value = True
    mock_services['crawling'].parse_sitemap.return_value = [
        "https://example.com/page1",
        "https://example.com/page2"
    ]
    mock_services['crawling'].crawl_batch.return_value = [
        {"url": "https://example.com/page1", "markdown": "Page 1"},
        {"url": "https://example.com/page2", "markdown": "Page 2"}
    ]
    
    result = await smart_crawl_url(mock_context, "https://example.com/sitemap.xml")
    result_data = json.loads(result)
    
    assert result_data["success"] is True
    assert result_data["crawl_type"] == "sitemap"
    assert result_data["urls_processed"] == 2
    
    # Verify sitemap crawling was used
    mock_services['crawling'].is_sitemap.assert_called_with("https://example.com/sitemap.xml")
    mock_services['crawling'].parse_sitemap.assert_called_once()
    mock_services['crawling'].crawl_batch.assert_called_once()


@pytest.mark.asyncio
async def test_smart_crawl_custom_chunk_size(mock_context, mock_services) -> None:
    """Test using custom chunk size."""
    result = await smart_crawl_url(
        mock_context, 
        "https://example.com",
        chunk_size=3000
    )
    result_data = json.loads(result)
    
    assert result_data["success"] is True
    
    # Verify custom chunk size was used
    calls = mock_services['text_processor'].smart_chunk_markdown.call_args_list
    for call in calls:
        # Check keyword arguments
        assert call.kwargs.get('chunk_size') == 3000 or call.args[1] == 3000


@pytest.mark.asyncio
async def test_smart_crawl_with_code_extraction(mock_context, mock_services) -> None:
    """Test crawling with code extraction enabled."""
    # Enable code extraction
    mock_context.request_context.lifespan_context.settings.use_agentic_rag = True
    
    # Mock code blocks
    mock_services['crawling'].extract_code_blocks.return_value = [
        {
            'code': 'def test(): pass',
            'language': 'python',
            'context_before': 'Before',
            'context_after': 'After'
        }
    ]
    
    result = await smart_crawl_url(mock_context, "https://example.com")
    result_data = json.loads(result)
    
    assert result_data["success"] is True
    # Each URL has 1 code block, database stores 2 results (one per URL with a code block)
    # But the mock returns count=2 each time it's called, so total is 4
    assert result_data["total_code_examples"] == 4  # 2 calls returning count=2 each
    
    # Verify code extraction was performed
    assert mock_services['crawling'].extract_code_blocks.call_count == 2


@pytest.mark.asyncio
async def test_smart_crawl_no_results(mock_context, mock_services) -> None:
    """Test handling when no content is crawled."""
    # Mock empty results
    mock_services['crawling'].crawl_recursive_internal_links.return_value = []
    
    result = await smart_crawl_url(mock_context, "https://example.com")
    result_data = json.loads(result)
    
    assert result_data["success"] is False
    assert "No content was successfully crawled" in result_data["error"]
    assert result_data["crawl_type"] == "recursive"


@pytest.mark.asyncio
async def test_smart_crawl_exception_handling(mock_context, mock_services) -> None:
    """Test exception handling."""
    # Mock exception
    mock_services['crawling'].crawl_recursive_internal_links.side_effect = Exception("Network error")
    
    result = await smart_crawl_url(mock_context, "https://example.com")
    result_data = json.loads(result)
    
    assert result_data["success"] is False
    assert "Network error" in result_data["error"]
    assert result_data["url"] == "https://example.com"


@pytest.mark.asyncio
async def test_smart_crawl_partial_failure(mock_context, mock_services) -> None:
    """Test handling partial failures during processing."""
    # Mock one successful and one failing result
    mock_services['crawling'].crawl_recursive_internal_links.return_value = [
        {"url": "https://example.com", "markdown": "# Page 1"},
        {"url": "https://example.com/page2", "markdown": "# Page 2"}
    ]
    
    # Make the second URL processing fail
    call_count = 0
    def chunk_side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return ["Chunk 1", "Chunk 2"]
        else:
            raise Exception("Processing error")
    
    mock_services['text_processor'].smart_chunk_markdown.side_effect = chunk_side_effect
    
    result = await smart_crawl_url(mock_context, "https://example.com")
    result_data = json.loads(result)
    
    # Should still succeed with partial results
    assert result_data["success"] is True
    assert result_data["urls_processed"] == 1  # Only first URL succeeded
    assert result_data["total_chunks_created"] == 3  # Only chunks from first URL


@pytest.mark.asyncio
async def test_metadata_timestamp_format(mock_context, mock_services) -> None:
    """Test that metadata contains properly formatted timestamp."""
    # Mock crawl result
    mock_services['crawling'].crawl_recursive_internal_links.return_value = [
        {"url": "https://example.com", "markdown": "Test content"}
    ]
    
    # Track the metadata passed to add_documents
    captured_metadata = []
    async def capture_add_documents(**kwargs):
        captured_metadata.extend(kwargs.get('metadatas', []))
        return {"success": True, "count": len(kwargs.get('contents', []))}
    
    mock_services['database'].add_documents = capture_add_documents
    
    result = await smart_crawl_url(mock_context, "https://example.com")
    result_data = json.loads(result)
    
    assert result_data["success"] is True
    assert len(captured_metadata) > 0
    
    # Check each metadata entry
    for metadata in captured_metadata:
        # Verify required fields exist
        assert "crawl_time" in metadata
        assert "crawl_type" in metadata
        assert "source" in metadata
        assert "url" in metadata
        assert "chunk_index" in metadata
        
        # Verify timestamp format (ISO format with timezone)
        crawl_time = metadata["crawl_time"]
        assert isinstance(crawl_time, str)
        assert "T" in crawl_time  # ISO format separator
        assert "+" in crawl_time or "Z" in crawl_time  # Timezone indicator
        
        # Verify it can be parsed as a datetime
        from datetime import datetime
        datetime.fromisoformat(crawl_time.replace('Z', '+00:00'))


@pytest.mark.asyncio
async def test_sitemap_with_empty_url_list(mock_context, mock_services) -> None:
    """Test handling of sitemap that returns no URLs."""
    # Mock sitemap detection
    mock_services['crawling'].is_txt.return_value = False
    mock_services['crawling'].is_sitemap.return_value = True
    mock_services['crawling'].parse_sitemap.return_value = []  # No URLs found
    
    result = await smart_crawl_url(mock_context, "https://example.com/sitemap.xml")
    result_data = json.loads(result)
    
    assert result_data["success"] is False
    assert "No content was successfully crawled" in result_data["error"]
    assert result_data["crawl_type"] == "sitemap"
    
    # Verify sitemap was parsed but crawl_batch was not called
    mock_services['crawling'].parse_sitemap.assert_called_once()
    mock_services['crawling'].crawl_batch.assert_not_called()


@pytest.mark.asyncio
async def test_sitemap_crawl_batch_failure(mock_context, mock_services) -> None:
    """Test handling when crawl_batch returns empty results for sitemap."""
    # Mock sitemap detection
    mock_services['crawling'].is_txt.return_value = False
    mock_services['crawling'].is_sitemap.return_value = True
    mock_services['crawling'].parse_sitemap.return_value = [
        "https://example.com/page1",
        "https://example.com/page2"
    ]
    mock_services['crawling'].crawl_batch.return_value = []  # All URLs failed
    
    result = await smart_crawl_url(mock_context, "https://example.com/sitemap.xml")
    result_data = json.loads(result)
    
    assert result_data["success"] is False
    assert "No content was successfully crawled" in result_data["error"]
    assert result_data["crawl_type"] == "sitemap"
    
    # Verify crawl_batch was called with the parsed URLs
    mock_services['crawling'].crawl_batch.assert_called_once_with(
        ["https://example.com/page1", "https://example.com/page2"],
        max_concurrent=10
    )