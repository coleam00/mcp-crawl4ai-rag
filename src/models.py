"""Pydantic models for data validation and type safety."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, HttpUrl, field_validator, ConfigDict


class CrawlType(str, Enum):
    """Types of crawling operations."""
    SINGLE_PAGE = "single_page"
    SITEMAP = "sitemap"
    TXT_FILE = "txt_file"
    RECURSIVE = "recursive"


class SearchType(str, Enum):
    """Types of search operations."""
    SEMANTIC = "semantic"
    HYBRID = "hybrid"
    CODE = "code"


# Request Models
class CrawlRequest(BaseModel):
    """Request model for crawling operations."""
    url: HttpUrl
    max_depth: int = Field(default=3, ge=1, le=10)
    max_concurrent: int = Field(default=10, ge=1, le=50)
    chunk_size: int = Field(default=5000, ge=100, le=10000)
    overlap: int = Field(default=200, ge=0, le=1000)
    extract_code_examples: Optional[bool] = None
    
    @field_validator("overlap")
    def validate_overlap(cls, v: int, info) -> int:
        """Ensure overlap is less than chunk size."""
        chunk_size = info.data.get("chunk_size", 5000)
        if v >= chunk_size:
            raise ValueError("Overlap must be less than chunk size")
        return v


class SearchRequest(BaseModel):
    """Request model for search operations."""
    query: str = Field(min_length=1, max_length=1000)
    source: Optional[str] = None
    num_results: int = Field(default=5, ge=1, le=20)
    semantic_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    use_reranking: Optional[bool] = None
    use_hybrid_search: Optional[bool] = None


class CodeSearchRequest(BaseModel):
    """Request model for code search operations."""
    query: str = Field(min_length=1, max_length=500)
    language: Optional[str] = None
    source: Optional[str] = None
    num_results: int = Field(default=5, ge=1, le=20)


# Response Models
class CrawlResult(BaseModel):
    """Result model for crawling operations."""
    success: bool
    url: str
    crawl_type: CrawlType
    pages_crawled: int = 0
    chunks_stored: int = 0
    code_examples_stored: int = 0
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SearchResult(BaseModel):
    """Result model for a single search result."""
    content: str
    url: str
    source: str
    chunk_number: int
    similarity_score: float
    rerank_score: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SearchResponse(BaseModel):
    """Response model for search operations."""
    success: bool
    results: List[SearchResult]
    total_results: int
    search_type: SearchType
    error: Optional[str] = None


class CodeExample(BaseModel):
    """Model for code examples."""
    code: str
    language: str
    context: str
    summary: str
    url: str
    source: str
    created_at: Optional[datetime] = None


class RAGResponse(BaseModel):
    """Response model for RAG queries."""
    success: bool
    answer: str
    sources: List[Dict[str, Any]]
    search_type: SearchType
    total_sources: int
    error: Optional[str] = None


class SourceInfo(BaseModel):
    """Model for source information."""
    source: str
    total_documents: int
    total_chunks: int
    total_code_examples: int
    word_count: int
    last_updated: datetime
    summary: Optional[str] = None


# Data Models
class Document(BaseModel):
    """Model for document chunks."""
    url: str
    content: str
    chunk_number: int
    total_chunks: int
    word_count: int
    source: str
    section_title: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    embedding: Optional[List[float]] = None
    contextual_content: Optional[str] = None


class CrawlContext(BaseModel):
    """Context for crawling operations (replaces dataclass)."""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    crawler: Any  # AsyncWebCrawler - using Any to avoid circular imports
    supabase_client: Any  # Client - using Any to avoid circular imports
    reranking_model: Optional[Any] = None  # CrossEncoder
    settings: Optional[Any] = None  # Settings - using Any to avoid circular imports


# Batch Operation Models
class BatchCrawlRequest(BaseModel):
    """Request model for batch crawling operations."""
    urls: List[HttpUrl]
    max_concurrent: int = Field(default=10, ge=1, le=50)
    chunk_size: int = Field(default=5000, ge=100, le=10000)
    overlap: int = Field(default=200, ge=0, le=1000)
    extract_code_examples: Optional[bool] = None


class BatchCrawlResult(BaseModel):
    """Result model for batch crawling operations."""
    success: bool
    total_urls: int
    successful_urls: int
    failed_urls: int
    total_chunks_stored: int
    total_code_examples_stored: int
    results: List[CrawlResult]
    error: Optional[str] = None