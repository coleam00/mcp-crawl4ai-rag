"""Tool for smart crawling with URL type detection."""

import json
import logging
from urllib.parse import urlparse

from mcp.server.fastmcp import Context

from crawl4ai_mcp.mcp_server import mcp
from crawl4ai_mcp.services.database import DatabaseService
from crawl4ai_mcp.services.embeddings import EmbeddingService
from crawl4ai_mcp.services.crawling import CrawlingService
from crawl4ai_mcp.utilities.metadata import create_chunk_metadata
from crawl4ai_mcp.utilities.text_processing import TextProcessor
from crawl4ai_mcp.models import CrawlContext

logger = logging.getLogger(__name__)


@mcp.tool()
async def smart_crawl_url(
    ctx: Context, 
    url: str, 
    max_depth: int = 3, 
    max_concurrent: int = 10,
    chunk_size: int = 5000
) -> str:
    """
    Intelligently crawl a URL based on its type (sitemap, txt file, or webpage).
    
    This tool automatically detects the URL type and applies the appropriate crawling strategy:
    - For sitemaps: Crawls all URLs listed in the sitemap
    - For txt files: Crawls the file as markdown
    - For regular pages: Recursively crawls internal links up to max_depth
    
    The crawled content is automatically chunked and stored in Supabase with embeddings.
    
    Args:
        ctx: The MCP server provided context
        url: The URL to crawl (can be a sitemap, txt file, or regular webpage)
        max_depth: Maximum recursion depth for regular URLs (default: 3)
        max_concurrent: Maximum concurrent browser sessions (default: 10)
        chunk_size: Maximum size of each content chunk (default: 5000)
    
    Returns:
        Summary of the crawling operation
    """
    try:
        # Get context and services
        context: CrawlContext = ctx.request_context.lifespan_context
        crawler = context.crawler
        supabase_client = context.supabase_client
        settings = context.settings
        
        # Initialize services
        embedding_service = EmbeddingService(settings)
        database_service = DatabaseService(supabase_client, settings)
        crawling_service = CrawlingService(crawler, settings, embedding_service)
        text_processor = TextProcessor(settings, embedding_service)
        
        # Override chunk size if specified
        if chunk_size != 5000:
            actual_chunk_size = chunk_size
        else:
            actual_chunk_size = settings.default_chunk_size
        
        # Determine URL type and crawl accordingly
        all_results = []
        
        if crawling_service.is_txt(url):
            # Crawl as markdown file
            all_results = await crawling_service.crawl_markdown_file(url)
            crawl_type = "txt file"
            
        elif crawling_service.is_sitemap(url):
            # Parse sitemap and crawl all URLs
            logger.info(f"Detected sitemap URL: {url}")
            urls_from_sitemap = crawling_service.parse_sitemap(url)
            logger.info(f"Found {len(urls_from_sitemap)} URLs in sitemap")
            
            if urls_from_sitemap:
                logger.info(f"Starting batch crawl of {len(urls_from_sitemap)} URLs")
                all_results = await crawling_service.crawl_batch(
                    urls_from_sitemap, 
                    max_concurrent=max_concurrent
                )
                logger.info(f"Batch crawl completed. Got {len(all_results)} results")
            else:
                logger.warning("No URLs found in sitemap")
            crawl_type = "sitemap"
            
        else:
            # Crawl recursively following internal links
            all_results = await crawling_service.crawl_recursive_internal_links(
                [url], 
                max_depth=max_depth, 
                max_concurrent=max_concurrent
            )
            crawl_type = "recursive"
        
        if not all_results:
            return json.dumps({
                "success": False,
                "error": "No content was successfully crawled",
                "crawl_type": crawl_type
            })
        
        # Process and store all results
        total_chunks_created = 0
        total_code_examples = 0
        processed_urls = []
        source_ids = set()
        
        # First, collect all unique source IDs
        for result in all_results:
            source_id = urlparse(result['url']).netloc
            source_ids.add(source_id)
        
        # Update source info for each unique source BEFORE processing documents
        for source_id in source_ids:
            # Get all content for this source
            source_content = "\n\n".join([
                r['markdown'] for r in all_results 
                if urlparse(r['url']).netloc == source_id
            ])
            
            # Calculate total word count
            total_word_count = len(source_content.split())
            
            # Generate summary
            source_summary = await crawling_service.extract_source_summary(
                source_id, source_content[:10000]
            )
            
            await database_service.update_source_info(
                source_id=source_id,
                summary=source_summary,
                word_count=total_word_count
            )
        
        for result in all_results:
            try:
                result_url = result['url']
                markdown_content = result['markdown']
                
                # Extract source_id
                source_id = urlparse(result_url).netloc
                
                # Chunk the content
                chunks = text_processor.smart_chunk_markdown(
                    markdown_content, 
                    chunk_size=actual_chunk_size
                )
                
                if not chunks:
                    continue
                
                # Prepare data for storage
                urls = []
                chunk_numbers = []
                contents = []
                embeddings = []
                metadatas = []
                url_to_full_document = {result_url: markdown_content}
                
                # Process each chunk
                for i, chunk in enumerate(chunks):
                    urls.append(result_url)
                    chunk_numbers.append(i + 1)
                    contents.append(chunk)
                    
                    # Generate embedding
                    if settings.use_contextual_embeddings:
                        contextual_content, _ = await text_processor.generate_contextual_embedding(
                            markdown_content, chunk
                        )
                        embedding = await embedding_service.create_embedding(contextual_content)
                    else:
                        embedding = await embedding_service.create_embedding(chunk)
                    
                    embeddings.append(embedding)
                    
                    # Extract metadata
                    section_info = text_processor.extract_section_info(chunk)
                    metadata = create_chunk_metadata(
                        chunk=chunk,
                        source_id=source_id,
                        url=result_url,
                        chunk_index=i,
                        crawl_type=crawl_type,
                        section_info=section_info
                    )
                    metadatas.append(metadata)
                
                # Add documents to database
                doc_result = await database_service.add_documents(
                    urls=urls,
                    chunk_numbers=chunk_numbers,
                    contents=contents,
                    embeddings=embeddings,
                    metadatas=metadatas,
                    url_to_full_document=url_to_full_document
                )
                
                total_chunks_created += doc_result.get('count', 0)
                
                # Extract and store code examples if enabled
                if settings.use_agentic_rag:
                    code_blocks = crawling_service.extract_code_blocks(markdown_content)
                    
                    if code_blocks:
                        # Process code examples
                        code_urls = []
                        code_chunk_numbers = []
                        code_examples = []
                        code_summaries = []
                        code_embeddings = []
                        code_metadatas = []
                        
                        for i, code_block in enumerate(code_blocks):
                            code_urls.append(result_url)
                            code_chunk_numbers.append(i + 1)
                            
                            # Format code with language
                            if code_block['language']:
                                formatted_code = f"```{code_block['language']}\n{code_block['code']}\n```"
                            else:
                                formatted_code = f"```\n{code_block['code']}\n```"
                            
                            code_examples.append(formatted_code)
                            
                            # Generate summary
                            summary = await crawling_service.generate_code_example_summary(
                                code_block['code'],
                                code_block['context_before'],
                                code_block['context_after']
                            )
                            code_summaries.append(summary)
                            
                            # Generate embedding
                            embedding_text = f"{summary}\n\n{formatted_code}"
                            embedding = await embedding_service.create_embedding(embedding_text)
                            code_embeddings.append(embedding)
                            
                            # Metadata
                            code_metadatas.append({
                                'language': code_block['language'],
                                'char_count': len(code_block['code']),
                                'summary': summary
                            })
                        
                        # Store code examples
                        code_result = await database_service.add_code_examples(
                            urls=code_urls,
                            chunk_numbers=code_chunk_numbers,
                            code_examples=code_examples,
                            summaries=code_summaries,
                            embeddings=code_embeddings,
                            metadatas=code_metadatas
                        )
                        
                        total_code_examples += code_result.get('count', 0)
                
                processed_urls.append(result_url)
                
            except Exception as e:
                logger.error(f"Error processing {result.get('url', 'unknown URL')}: {e}")
                continue
        
        return json.dumps({
            "success": True,
            "crawl_type": crawl_type,
            "urls_processed": len(processed_urls),
            "total_chunks_created": total_chunks_created,
            "total_code_examples": total_code_examples,
            "sources_updated": list(source_ids),
            "message": f"Successfully crawled {len(processed_urls)} URLs using {crawl_type} strategy"
        })
        
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e),
            "url": url
        })