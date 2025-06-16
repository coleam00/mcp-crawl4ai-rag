"""Tests for crawling service."""

import pytest
from unittest.mock import Mock, AsyncMock, patch

from crawl4ai_mcp.services.crawling import CrawlingService
from crawl4ai_mcp.services.embeddings import EmbeddingService


@pytest.fixture
def mock_crawler():
    """Mock AsyncWebCrawler."""
    crawler = Mock()
    
    # Mock arun method
    crawler.arun = AsyncMock()
    
    # Mock arun_many method
    crawler.arun_many = AsyncMock()
    
    return crawler


@pytest.fixture
def mock_embedding_service():
    """Mock embedding service."""
    service = Mock(spec=EmbeddingService)
    service.client = Mock()
    service.client.chat = Mock()
    service.client.chat.completions = Mock()
    service.client.chat.completions.create = Mock()
    
    # Mock _run_in_executor
    async def mock_run_in_executor(func):
        return func()
    service._run_in_executor = mock_run_in_executor
    
    return service


@pytest.fixture
def crawling_service(mock_crawler, test_settings, mock_embedding_service):
    """Create CrawlingService with mocked dependencies."""
    return CrawlingService(mock_crawler, test_settings, mock_embedding_service)


class TestUrlChecking:
    """Test URL type checking methods."""
    
    def test_is_sitemap_true(self, crawling_service) -> None:
        """Test sitemap URL detection."""
        assert crawling_service.is_sitemap("https://example.com/sitemap.xml") is True
        assert crawling_service.is_sitemap("https://example.com/path/sitemap.xml") is True
        assert crawling_service.is_sitemap("https://example.com/sitemap/index.xml") is True
    
    def test_is_sitemap_false(self, crawling_service) -> None:
        """Test non-sitemap URL detection."""
        assert crawling_service.is_sitemap("https://example.com/index.html") is False
        assert crawling_service.is_sitemap("https://example.com/robots.txt") is False
    
    def test_is_txt_true(self, crawling_service) -> None:
        """Test text file URL detection."""
        assert crawling_service.is_txt("https://example.com/file.txt") is True
        assert crawling_service.is_txt("https://example.com/path/readme.txt") is True
    
    def test_is_txt_false(self, crawling_service) -> None:
        """Test non-text file URL detection."""
        assert crawling_service.is_txt("https://example.com/index.html") is False
        assert crawling_service.is_txt("https://example.com/file.pdf") is False


class TestSitemapParsing:
    """Test sitemap parsing."""
    
    @patch('requests.get')
    def test_parse_sitemap_success(self, mock_get, crawling_service) -> None:
        """Test successful sitemap parsing."""
        # Mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b"""<?xml version="1.0" encoding="UTF-8"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
            <url><loc>https://example.com/page1</loc></url>
            <url><loc>https://example.com/page2</loc></url>
        </urlset>"""
        mock_get.return_value = mock_response
        
        urls = crawling_service.parse_sitemap("https://example.com/sitemap.xml")
        
        assert len(urls) == 2
        assert "https://example.com/page1" in urls
        assert "https://example.com/page2" in urls
    
    @patch('requests.get')
    def test_parse_sitemap_failure(self, mock_get, crawling_service) -> None:
        """Test sitemap parsing with failed request."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        
        urls = crawling_service.parse_sitemap("https://example.com/sitemap.xml")
        assert urls == []
    
    @patch('requests.get')
    def test_parse_sitemap_invalid_xml(self, mock_get, crawling_service) -> None:
        """Test sitemap parsing with invalid XML."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b"Invalid XML content"
        mock_get.return_value = mock_response
        
        urls = crawling_service.parse_sitemap("https://example.com/sitemap.xml")
        assert urls == []


class TestCrawling:
    """Test crawling methods."""
    
    @pytest.mark.asyncio
    async def test_crawl_markdown_file_success(self, crawling_service, mock_crawler) -> None:
        """Test successful markdown file crawling."""
        # Mock result
        mock_result = Mock()
        mock_result.success = True
        mock_result.markdown = "# Test Content"
        mock_crawler.arun.return_value = mock_result
        
        results = await crawling_service.crawl_markdown_file("https://example.com/file.txt")
        
        assert len(results) == 1
        assert results[0]['url'] == "https://example.com/file.txt"
        assert results[0]['markdown'] == "# Test Content"
        
        # Verify crawler was called
        mock_crawler.arun.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_crawl_markdown_file_failure(self, crawling_service, mock_crawler) -> None:
        """Test failed markdown file crawling."""
        # Mock result
        mock_result = Mock()
        mock_result.success = False
        mock_result.error_message = "Failed to fetch"
        mock_crawler.arun.return_value = mock_result
        
        results = await crawling_service.crawl_markdown_file("https://example.com/file.txt")
        
        assert results == []
    
    @pytest.mark.asyncio
    async def test_crawl_batch(self, crawling_service, mock_crawler) -> None:
        """Test batch crawling."""
        # Mock results
        mock_results = [
            Mock(success=True, url="https://example.com/1", markdown="Content 1"),
            Mock(success=True, url="https://example.com/2", markdown="Content 2"),
            Mock(success=False, url="https://example.com/3", markdown=None)
        ]
        mock_crawler.arun_many.return_value = mock_results
        
        urls = ["https://example.com/1", "https://example.com/2", "https://example.com/3"]
        results = await crawling_service.crawl_batch(urls, max_concurrent=5)
        
        assert len(results) == 2  # Only successful results
        assert results[0]['url'] == "https://example.com/1"
        assert results[0]['markdown'] == "Content 1"
        assert results[1]['url'] == "https://example.com/2"
        assert results[1]['markdown'] == "Content 2"
    
    @pytest.mark.asyncio
    async def test_crawl_recursive_internal_links(self, crawling_service, mock_crawler) -> None:
        """Test recursive internal link crawling."""
        # Mock first level results
        first_level = [
            Mock(
                success=True,
                url="https://example.com/page1",
                markdown="Page 1",
                links={"internal": [{"href": "https://example.com/page2"}]}
            )
        ]
        
        # Mock second level results
        second_level = [
            Mock(
                success=True,
                url="https://example.com/page2",
                markdown="Page 2",
                links={"internal": []}
            )
        ]
        
        mock_crawler.arun_many.side_effect = [first_level, second_level]
        
        results = await crawling_service.crawl_recursive_internal_links(
            ["https://example.com/page1"],
            max_depth=2
        )
        
        assert len(results) == 2
        assert results[0]['url'] == "https://example.com/page1"
        assert results[1]['url'] == "https://example.com/page2"


class TestCodeExtraction:
    """Test code extraction and processing."""
    
    def test_extract_code_blocks_simple(self, crawling_service) -> None:
        """Test extracting simple code blocks."""
        markdown = """
Some text before

```python
def hello():
    # This is a long enough code block
    print("Hello, world!")
    # Adding more lines to meet minimum length
    for i in range(100):
        print(f"Line {i}")
    # More code here
    result = []
    for j in range(50):
        result.append(j * 2)
    return result
```

Some text after
"""
        
        # Adjust min_length for testing
        code_blocks = crawling_service.extract_code_blocks(markdown, min_length=50)
        
        assert len(code_blocks) == 1
        assert code_blocks[0]['language'] == 'python'
        assert 'def hello():' in code_blocks[0]['code']
        assert 'Some text before' in code_blocks[0]['context_before']
        assert 'Some text after' in code_blocks[0]['context_after']
    
    def test_extract_code_blocks_no_language(self, crawling_service) -> None:
        """Test extracting code blocks without language specifier."""
        markdown = """Some text before

```
This is a code block without language
It should still be extracted if long enough
Adding more content to meet minimum length requirement
Line 4
Line 5
Line 6
Line 7
Line 8
Line 9
Line 10
```

Some text after"""
        
        code_blocks = crawling_service.extract_code_blocks(markdown, min_length=10)
        
        assert len(code_blocks) == 1
        assert code_blocks[0]['language'] == ''
        assert 'This is a code block' in code_blocks[0]['code']
    
    def test_extract_code_blocks_skip_short(self, crawling_service) -> None:
        """Test that short code blocks are skipped."""
        markdown = """Some introduction text

```python
short_code = True
```

Some text between code blocks

```python
def long_function():
    # This is a much longer code block that should be extracted
    # Adding many lines to exceed minimum length
    for i in range(100):
        print(f"Processing item {i}")
        if i % 2 == 0:
            print("Even number")
        else:
            print("Odd number")
    
    # More processing
    results = []
    for j in range(50):
        results.append(j ** 2)
    
    return results
```

Some closing text"""
        
        code_blocks = crawling_service.extract_code_blocks(markdown, min_length=100)
        
        assert len(code_blocks) == 1
        assert 'long_function' in code_blocks[0]['code']
        assert 'short_code' not in code_blocks[0]['code']
    
    @pytest.mark.asyncio
    async def test_generate_code_example_summary(self, crawling_service, mock_embedding_service) -> None:
        """Test code example summary generation."""
        # Mock OpenAI response
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="This code demonstrates a hello world function."))]
        mock_embedding_service.client.chat.completions.create.return_value = mock_response
        
        summary = await crawling_service.generate_code_example_summary(
            code="def hello(): print('hello')",
            context_before="Here's an example:",
            context_after="That's the basic function."
        )
        
        assert summary == "This code demonstrates a hello world function."
    
    @pytest.mark.asyncio
    async def test_generate_code_example_summary_error(self, crawling_service, mock_embedding_service) -> None:
        """Test code example summary generation with error."""
        # Mock error
        mock_embedding_service.client.chat.completions.create.side_effect = Exception("API error")
        
        summary = await crawling_service.generate_code_example_summary(
            code="def hello(): pass",
            context_before="",
            context_after=""
        )
        
        assert summary == "Code example for demonstration purposes."


class TestSourceSummary:
    """Test source summary extraction."""
    
    @pytest.mark.asyncio
    async def test_extract_source_summary_success(self, crawling_service, mock_embedding_service) -> None:
        """Test successful source summary extraction."""
        # Mock OpenAI response
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="This is a test library for unit testing."))]
        mock_embedding_service.client.chat.completions.create.return_value = mock_response
        
        summary = await crawling_service.extract_source_summary(
            source_id="test-lib",
            content="This is the documentation for test-lib..."
        )
        
        assert summary == "This is a test library for unit testing."
    
    @pytest.mark.asyncio
    async def test_extract_source_summary_empty_content(self, crawling_service) -> None:
        """Test source summary with empty content."""
        summary = await crawling_service.extract_source_summary(
            source_id="test-lib",
            content=""
        )
        
        assert summary == "Content from test-lib"
    
    @pytest.mark.asyncio
    async def test_extract_source_summary_long_result(self, crawling_service, mock_embedding_service) -> None:
        """Test source summary with long result that needs truncation."""
        # Mock OpenAI response with long text
        long_text = "A" * 600
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content=long_text))]
        mock_embedding_service.client.chat.completions.create.return_value = mock_response
        
        summary = await crawling_service.extract_source_summary(
            source_id="test-lib",
            content="Documentation content",
            max_length=500
        )
        
        assert len(summary) == 503  # 500 + "..."
        assert summary.endswith("...")
    
    @pytest.mark.asyncio
    async def test_extract_source_summary_error(self, crawling_service, mock_embedding_service) -> None:
        """Test source summary extraction with error."""
        # Mock error
        mock_embedding_service.client.chat.completions.create.side_effect = Exception("API error")
        
        summary = await crawling_service.extract_source_summary(
            source_id="test-lib",
            content="Some content"
        )
        
        assert summary == "Content from test-lib"