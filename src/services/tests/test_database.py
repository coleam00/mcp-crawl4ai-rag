"""Tests for database service."""

import pytest
from unittest.mock import Mock

from crawl4ai_mcp.services.database import DatabaseService
from crawl4ai_mcp.models import SourceInfo


@pytest.fixture
def database_service(mock_supabase_client, test_settings):
    """Create DatabaseService with mocked dependencies."""
    return DatabaseService(mock_supabase_client, test_settings)


@pytest.mark.asyncio
async def test_add_documents_success(database_service, mock_supabase_client) -> None:
    """Test successful document addition."""
    # Mock the delete operation
    mock_supabase_client.table.return_value.delete.return_value.in_.return_value.execute.return_value = Mock()
    
    # Mock the insert operation
    mock_supabase_client.table.return_value.insert.return_value.execute.return_value = Mock()
    
    result = await database_service.add_documents(
        urls=["https://example.com/test"],
        chunk_numbers=[1],
        contents=["Test content"],
        embeddings=[[0.1] * 1536],
        metadatas=[{"title": "Test"}],
        url_to_full_document={"https://example.com/test": "Full document content"}
    )
    
    assert result["success"] is True
    assert result["count"] == 1
    assert result["total"] == 1


@pytest.mark.asyncio
async def test_add_documents_empty_list(database_service) -> None:
    """Test handling of empty document list."""
    result = await database_service.add_documents(
        urls=[],
        chunk_numbers=[],
        contents=[],
        embeddings=[],
        metadatas=[],
        url_to_full_document={}
    )
    
    assert result["success"] is True
    assert result["count"] == 0
    assert result["total"] == 0


@pytest.mark.asyncio
async def test_add_documents_delete_error(database_service, mock_supabase_client) -> None:
    """Test handling of delete errors."""
    # Mock delete to raise an exception
    mock_supabase_client.table.return_value.delete.return_value.in_.return_value.execute.side_effect = Exception("Delete failed")
    
    result = await database_service.add_documents(
        urls=["https://example.com/test"],
        chunk_numbers=[1],
        contents=["Test content"],
        embeddings=[[0.1] * 1536],
        metadatas=[{"title": "Test"}],
        url_to_full_document={}
    )
    
    assert result["success"] is False
    assert "Failed to delete existing records" in result["error"]
    assert result["count"] == 0


@pytest.mark.asyncio
async def test_add_code_examples_success(database_service, mock_supabase_client) -> None:
    """Test successful code example addition."""
    # Mock the delete operation
    mock_supabase_client.table.return_value.delete.return_value.eq.return_value.execute.return_value = Mock()
    
    # Mock the insert operation
    mock_supabase_client.table.return_value.insert.return_value.execute.return_value = Mock()
    
    result = await database_service.add_code_examples(
        urls=["https://example.com/test"],
        chunk_numbers=[1],
        code_examples=["```python\ndef hello():\n    print('Hello')\n```"],
        summaries=["A hello function"],
        embeddings=[[0.1] * 1536],
        metadatas=[{"language": "python"}]
    )
    
    assert result["success"] is True
    assert result["count"] == 1
    assert result["total"] == 1


@pytest.mark.asyncio
async def test_add_code_examples_empty_list(database_service) -> None:
    """Test handling of empty code examples list."""
    result = await database_service.add_code_examples(
        urls=[],
        chunk_numbers=[],
        code_examples=[],
        summaries=[],
        embeddings=[],
        metadatas=[]
    )
    
    assert result["success"] is True
    assert result["count"] == 0


@pytest.mark.asyncio
async def test_update_source_info_new_source(database_service, mock_supabase_client) -> None:
    """Test creating a new source."""
    # Mock update to return no data (source doesn't exist)
    mock_supabase_client.table.return_value.update.return_value.eq.return_value.execute.return_value = Mock(data=[])
    
    # Mock insert
    mock_supabase_client.table.return_value.insert.return_value.execute.return_value = Mock()
    
    result = await database_service.update_source_info(
        source_id="example.com",
        summary="Test source",
        word_count=100
    )
    
    assert result["success"] is True
    assert result["source_id"] == "example.com"
    
    # Verify insert was called
    mock_supabase_client.table.return_value.insert.assert_called_once()


@pytest.mark.asyncio
async def test_update_source_info_existing_source(database_service, mock_supabase_client) -> None:
    """Test updating an existing source."""
    # Mock update to return data (source exists)
    mock_supabase_client.table.return_value.update.return_value.eq.return_value.execute.return_value = Mock(data=[{"source_id": "example.com"}])
    
    result = await database_service.update_source_info(
        source_id="example.com",
        summary="Updated source",
        word_count=200
    )
    
    assert result["success"] is True
    assert result["source_id"] == "example.com"
    
    # Verify update was called
    mock_supabase_client.table.return_value.update.assert_called_once()


@pytest.mark.asyncio
async def test_update_source_info_error(database_service, mock_supabase_client) -> None:
    """Test handling of source update errors."""
    # Mock update to raise an exception
    mock_supabase_client.table.return_value.update.return_value.eq.return_value.execute.side_effect = Exception("Update failed")
    
    result = await database_service.update_source_info(
        source_id="example.com",
        summary="Test source",
        word_count=100
    )
    
    assert result["success"] is False
    assert "Update failed" in result["error"]


@pytest.mark.asyncio
async def test_get_available_sources(database_service, mock_supabase_client) -> None:
    """Test getting available sources."""
    # Mock sources table response
    mock_sources_data = [
        {
            "source_id": "example.com",
            "summary": "Example website",
            "total_word_count": 1000,
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-02T00:00:00Z"
        }
    ]
    
    # Create separate mocks for each table operation
    sources_table_mock = Mock()
    sources_table_mock.select.return_value.execute.return_value = Mock(data=mock_sources_data)
    
    crawled_pages_table_mock = Mock()
    # For count query
    count_result = Mock()
    count_result.count = 10
    crawled_pages_table_mock.select.return_value.eq.return_value.execute.return_value = count_result
    
    code_examples_table_mock = Mock()
    # For count query
    code_count_result = Mock()
    code_count_result.count = 5
    code_examples_table_mock.select.return_value.eq.return_value.execute.return_value = code_count_result
    
    # Setup table method to return different mocks
    call_count = 0
    def table_side_effect(table_name):
        nonlocal call_count
        call_count += 1
        
        if table_name == 'sources':
            return sources_table_mock
        elif table_name == 'crawled_pages':
            if call_count in [2, 5]:  # Document count calls
                return crawled_pages_table_mock
            else:  # Chunk data call
                chunks_mock = Mock()
                chunks_mock.select.return_value.eq.return_value.execute.return_value = Mock(
                    data=[{"chunk_number": 1}, {"chunk_number": 2}, {"chunk_number": 3}]
                )
                return chunks_mock
        elif table_name == 'code_examples':
            return code_examples_table_mock
            
        return Mock()
    
    mock_supabase_client.table.side_effect = table_side_effect
    
    sources = await database_service.get_available_sources()
    
    assert len(sources) == 1
    assert isinstance(sources[0], SourceInfo)
    assert sources[0].source == "example.com"
    assert sources[0].summary == "Example website"
    assert sources[0].word_count == 1000
    assert sources[0].total_documents == 10
    assert sources[0].total_code_examples == 5
    assert sources[0].total_chunks == 3


@pytest.mark.asyncio
async def test_get_available_sources_error(database_service, mock_supabase_client) -> None:
    """Test handling of errors when getting sources."""
    # Mock to raise an exception
    mock_supabase_client.table.return_value.select.return_value.execute.side_effect = Exception("Query failed")
    
    sources = await database_service.get_available_sources()
    
    assert sources == []


@pytest.mark.asyncio
async def test_get_available_sources_column_names(database_service, mock_supabase_client) -> None:
    """Test that get_available_sources uses correct column names (source_id not source)."""
    # Mock sources data
    mock_sources_data = [
        {
            'source_id': 'test.com',
            'display_name': 'Test Site',
            'summary': 'Test source summary',
            'created_at': '2024-01-01T00:00:00Z',
            'updated_at': '2024-01-02T00:00:00Z',
            'content_types': ['html'],
            'total_word_count': 2000
        }
    ]
    
    # Set up sources table mock
    sources_table_mock = Mock()
    sources_table_mock.select.return_value.execute.return_value = Mock(data=mock_sources_data)
    
    # Mock for tracking eq() calls on crawled_pages table
    crawled_pages_eq_calls = []
    crawled_pages_mock = Mock()
    
    def track_crawled_pages_eq(field, value):
        crawled_pages_eq_calls.append((field, value))
        return crawled_pages_mock
    
    crawled_pages_mock.select.return_value.eq.side_effect = track_crawled_pages_eq
    crawled_pages_mock.execute.return_value = Mock(data=[], count=15)
    
    # Mock for tracking eq() calls on code_examples table
    code_examples_eq_calls = []
    code_examples_mock = Mock()
    
    def track_code_examples_eq(field, value):
        code_examples_eq_calls.append((field, value))
        return code_examples_mock
    
    code_examples_mock.select.return_value.eq.side_effect = track_code_examples_eq
    code_examples_mock.execute.return_value = Mock(data=[], count=8)
    
    # Mock for chunks query
    chunks_mock = Mock()
    chunks_mock.select.return_value.eq.return_value.execute.return_value = Mock(
        data=[{"chunk_number": 1}, {"chunk_number": 2}, {"chunk_number": 3}, {"chunk_number": 4}]
    )
    
    # Counter to track table calls
    call_count = 0
    
    def table_side_effect(table_name):
        nonlocal call_count
        call_count += 1
        
        if table_name == 'sources':
            return sources_table_mock
        elif table_name == 'crawled_pages':
            if call_count in [2, 5]:  # Document count and chunks calls
                return crawled_pages_mock
            else:  # Chunk data call
                return chunks_mock
        elif table_name == 'code_examples':
            return code_examples_mock
        
        return Mock()
    
    mock_supabase_client.table.side_effect = table_side_effect
    
    # Execute
    sources = await database_service.get_available_sources()
    
    # Verify the eq() calls used source_id, not source
    assert len(crawled_pages_eq_calls) == 1
    assert crawled_pages_eq_calls[0][0] == 'source_id'
    assert crawled_pages_eq_calls[0][1] == 'test.com'
    
    assert len(code_examples_eq_calls) == 1
    assert code_examples_eq_calls[0][0] == 'source_id'
    assert code_examples_eq_calls[0][1] == 'test.com'
    
    # Verify result
    assert len(sources) == 1
    assert sources[0].source == 'test.com'  # Note: SourceInfo model uses 'source' not 'source_id'
    assert sources[0].total_documents == 15
    assert sources[0].total_code_examples == 8
    assert sources[0].total_chunks == 4


@pytest.mark.asyncio
async def test_generate_contextual_content(database_service) -> None:
    """Test contextual content generation."""
    content = database_service._generate_contextual_content(
        chunk_content="This is chunk content",
        full_document="This is the full document with more content",
        chunk_number=2
    )
    
    assert "Chunk 2" in content
    assert "This is chunk content" in content