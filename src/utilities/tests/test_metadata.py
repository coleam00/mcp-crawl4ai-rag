"""Tests for metadata utilities."""

from datetime import datetime
from crawl4ai_mcp.utilities.metadata import create_chunk_metadata


def test_create_chunk_metadata() -> None:
    """Test creating chunk metadata with all required fields."""
    section_info = {
        "title": "Test Section",
        "level": 2,
        "topics": ["python", "testing"]
    }
    
    metadata = create_chunk_metadata(
        chunk="Test chunk content",
        source_id="example.com",
        url="https://example.com/page",
        chunk_index=5,
        crawl_type="single_page",
        section_info=section_info
    )
    
    # Check all required fields
    assert metadata["source"] == "example.com"
    assert metadata["url"] == "https://example.com/page"
    assert metadata["chunk_index"] == 5
    assert metadata["crawl_type"] == "single_page"
    assert "crawl_time" in metadata
    
    # Check section info is preserved
    assert metadata["title"] == "Test Section"
    assert metadata["level"] == 2
    assert metadata["topics"] == ["python", "testing"]
    
    # Check timestamp format
    crawl_time = metadata["crawl_time"]
    assert isinstance(crawl_time, str)
    assert "T" in crawl_time  # ISO format
    assert "+" in crawl_time or "Z" in crawl_time  # Timezone
    
    # Verify it can be parsed
    datetime.fromisoformat(crawl_time.replace('Z', '+00:00'))


def test_create_chunk_metadata_empty_section_info() -> None:
    """Test creating chunk metadata with empty section info."""
    metadata = create_chunk_metadata(
        chunk="Test content",
        source_id="test.com",
        url="https://test.com",
        chunk_index=0,
        crawl_type="recursive",
        section_info={}
    )
    
    assert metadata["source"] == "test.com"
    assert metadata["url"] == "https://test.com"
    assert metadata["chunk_index"] == 0
    assert metadata["crawl_type"] == "recursive"
    assert "crawl_time" in metadata


def test_create_chunk_metadata_preserves_existing_fields() -> None:
    """Test that existing fields in section_info are not overwritten."""
    section_info = {
        "source": "should_be_overwritten",  # This should be overwritten
        "custom_field": "preserved"
    }
    
    metadata = create_chunk_metadata(
        chunk="Content",
        source_id="newdomain.com",
        url="https://newdomain.com/doc",
        chunk_index=1,
        crawl_type="sitemap",
        section_info=section_info
    )
    
    # Standard fields should override
    assert metadata["source"] == "newdomain.com"
    
    # Custom fields should be preserved
    assert metadata["custom_field"] == "preserved"