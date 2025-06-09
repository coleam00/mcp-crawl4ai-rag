"""Tool for crawling a single web page."""

import json
from urllib.parse import urlparse

from mcp.server.fastmcp import Context

from crawl4ai_mcp.mcp_server import mcp
from crawl4ai_mcp.services.database import DatabaseService
from crawl4ai_mcp.services.embeddings import EmbeddingService
from crawl4ai_mcp.services.crawling import CrawlingService
from crawl4ai_mcp.utilities.metadata import create_chunk_metadata
from crawl4ai_mcp.utilities.text_processing import TextProcessor
from crawl4ai_mcp.models import CrawlContext


@mcp.tool()
async def crawl_single_page(ctx: Context, url: str) -> str:
    """
    Crawl a single web page and store its content in Supabase.
    
    This tool is ideal for quickly retrieving content from a specific URL without following links.
    The content is stored in Supabase for later retrieval and querying.
    
    Args:
        ctx: The MCP server provided context
        url: URL of the web page to crawl
    
    Returns:
        Summary of the crawling operation and storage in Supabase
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
        
        # Crawl the single page
        results = await crawling_service.crawl_batch([url], max_concurrent=1)
        
        if not results:
            return json.dumps({
                "success": False,
                "error": "Failed to crawl the URL"
            })
        
        result = results[0]
        markdown_content = result['markdown']
        
        # Extract source_id
        source_id = urlparse(url).netloc
        
        # Update source info FIRST (before inserting documents)
        total_word_count = len(markdown_content.split())
        source_summary = await crawling_service.extract_source_summary(
            source_id, markdown_content[:10000]
        )
        
        await database_service.update_source_info(
            source_id=source_id,
            summary=source_summary,
            word_count=total_word_count
        )
        
        # Chunk the content
        chunks = text_processor.smart_chunk_markdown(
            markdown_content, 
            chunk_size=settings.default_chunk_size
        )
        
        # Prepare data for storage
        urls = []
        chunk_numbers = []
        contents = []
        embeddings = []
        metadatas = []
        url_to_full_document = {url: markdown_content}
        
        # Process each chunk
        for i, chunk in enumerate(chunks):
            urls.append(url)
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
                url=url,
                chunk_index=i,
                crawl_type="single_page",
                section_info=section_info
            )
            metadatas.append(metadata)
        
        
        # Add documents to database
        await database_service.add_documents(
            urls=urls,
            chunk_numbers=chunk_numbers,
            contents=contents,
            embeddings=embeddings,
            metadatas=metadatas,
            url_to_full_document=url_to_full_document
        )
        
        # Extract and store code examples if enabled
        code_count = 0
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
                    code_urls.append(url)
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
                
                code_count = code_result.get('count', 0)
        
        return json.dumps({
            "success": True,
            "url": url,
            "chunks_created": len(chunks),
            "code_examples_created": code_count,
            "total_word_count": total_word_count,
            "source_id": source_id,
            "message": f"Successfully crawled and stored content from {url}"
        })
        
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e),
            "url": url
        })