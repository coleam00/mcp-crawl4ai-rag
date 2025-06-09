"""Metadata utilities for crawled documents."""

from datetime import datetime, timezone
from typing import Dict, Any


def create_chunk_metadata(
    chunk: str,
    source_id: str,
    url: str,
    chunk_index: int,
    crawl_type: str,
    section_info: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Create standardized metadata for a document chunk.
    
    Args:
        chunk: The text chunk content
        source_id: The source identifier (usually domain)
        url: The full URL of the document
        chunk_index: The index of this chunk in the document
        crawl_type: Type of crawl (e.g., 'single_page', 'sitemap', 'recursive')
        section_info: Additional section information extracted from the chunk
        
    Returns:
        Dictionary containing all metadata for the chunk
    """
    metadata = section_info.copy()
    
    # Add standard fields
    metadata.update({
        "source": source_id,
        "url": url,
        "chunk_index": chunk_index,
        "crawl_type": crawl_type,
        "crawl_time": datetime.now(timezone.utc).isoformat()
    })
    
    return metadata