"""
MCP server for web crawling with Crawl4AI.

This server provides tools to crawl websites using Crawl4AI, automatically detecting
the appropriate crawl method based on URL type (sitemap, txt file, or regular webpage).
"""

import asyncio
import json
import os

# Remove unused time import
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Any, AsyncIterator, Dict, List, Optional
from urllib.parse import urlparse
from xml.etree import ElementTree

import requests
from crawl4ai import AsyncWebCrawler, BrowserConfig
from fastmcp import FastMCP
from fastmcp.context import Context
from supabase import Client

# Try to import sentence_transformers for reranking (optional)
try:
    from sentence_transformers import CrossEncoder
except ImportError:
    CrossEncoder = None

# Import our provider system
from providers import ProviderManager, get_provider_manager
from utils import (
    add_code_examples_to_supabase,
    add_documents_to_supabase, 
    extract_code_blocks,
    extract_source_summary,
    generate_code_example_summary,
    get_supabase_client,
)
from utils import search_code_examples as search_code_examples_util
from utils import (
    search_documents,
    update_source_info,
)


@dataclass
class Crawl4AIContext:
    """Context for the Crawl4AI MCP server."""

    crawler: AsyncWebCrawler
    supabase_client: Client
    ai_provider: ProviderManager  # Changed to ProviderManager
    reranking_model: Optional[Any] = None  # Use Any instead of string annotation


@asynccontextmanager
async def crawl4ai_lifespan(server: FastMCP) -> AsyncIterator[Crawl4AIContext]:
    """
    Lifespan context manager for the Crawl4AI MCP server.
    
    Args:
        server: The FastMCP server instance
        
    Yields:
        Crawl4AIContext: The context containing the Crawl4AI crawler, Supabase client, and AI provider
    """
    # Create browser configuration
    browser_config = BrowserConfig(headless=True, verbose=False)
    
    # Initialize the crawler
    crawler = AsyncWebCrawler(config=browser_config)
    # Use context manager directly instead of dunder method
    await crawler.start()
    
    # Initialize Supabase client
    supabase_client = get_supabase_client()
    
    # Initialize AI provider manager
    ai_provider = get_provider_manager()
    provider_info = ai_provider.provider_info
    print(
        f"Initialized AI providers: {provider_info['embedding_provider']} "
        f"(embeddings) + {provider_info['llm_provider']} (LLM)"
    )
    print(
        f"Models: {provider_info['embedding_model']} (embeddings) + "
        f"{provider_info['llm_model']} (completions)"
    )
    
    # Initialize cross-encoder model for reranking if enabled
    reranking_model = None
    if os.getenv("USE_RERANKING", "false") == "true" and CrossEncoder is not None:
        try:
            reranking_model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
        except Exception as error:
            print(f"Failed to load reranking model: {error}")
            reranking_model = None
    elif os.getenv("USE_RERANKING", "false") == "true":
        print(
            "Reranking requested but sentence_transformers not installed. "
            "Install with: pip install sentence-transformers"
        )
    
    try:
        yield Crawl4AIContext(
            crawler=crawler,
            supabase_client=supabase_client,
            ai_provider=ai_provider,
            reranking_model=reranking_model,
        )
    finally:
        # Clean up the crawler
        await crawler.close()


# Initialize FastMCP server
mcp = FastMCP(
    "mcp-crawl4ai-rag",
    description="MCP server for RAG and web crawling with Crawl4AI",
    lifespan=crawl4ai_lifespan,
    host=os.getenv("HOST", "0.0.0.0"),
    port=os.getenv("PORT", "8051"),
)


def rerank_results(
    model: Optional[Any],  # Use Any instead of string annotation
    query: str,
    results: List[Dict[str, Any]],
    content_key: str = "content",
) -> List[Dict[str, Any]]:
    """
    Rerank search results using a cross-encoder model.
    
    Args:
        model: The cross-encoder model to use for reranking
        query: The search query
        results: List of search results
        content_key: The key in each result dict that contains the text content
        
    Returns:
        Reranked list of results
    """
    if not model or not results:
        return results
    
    try:
        # Extract content from results
        texts = [result.get(content_key, "") for result in results]
        
        # Create pairs of [query, document] for the cross-encoder
        pairs = [[query, text] for text in texts]
        
        # Get relevance scores from the cross-encoder
        scores = model.predict(pairs)
        
        # Add scores to results and sort by score (descending)
        for i, result in enumerate(results):
            result["rerank_score"] = float(scores[i])
        
        # Sort by rerank score
        reranked = sorted(results, key=lambda x: x.get("rerank_score", 0), reverse=True)
        
        return reranked
    # Use more specific exception handling where possible
    except Exception as error:
        print(f"Error during reranking: {error}")
        return results


def is_sitemap(url: str) -> bool:
    """
    Check if a URL is a sitemap.
    
    Args:
        url: URL to check
        
    Returns:
        True if the URL is a sitemap, False otherwise
    """
    return url.endswith("sitemap.xml") or "sitemap" in urlparse(url).path


def is_txt(url: str) -> bool:
    """
    Check if a URL is a text file.
    
    Args:
        url: URL to check
        
    Returns:
        True if the URL is a text file, False otherwise
    """
    return url.endswith(".txt")


def parse_sitemap(sitemap_url: str) -> List[str]:
    """
    Parse a sitemap and extract URLs.
    
    Args:
        sitemap_url: URL of the sitemap
        
    Returns:
        List of URLs found in the sitemap
    """
    resp = requests.get(sitemap_url)
    urls = []

    if resp.status_code == 200:
        try:
            tree = ElementTree.fromstring(resp.content)
            # Filter out None values from the list comprehension
            urls = [loc.text for loc in tree.findall(".//{*}loc") if loc.text is not None]
        except Exception as error:
            print(f"Error parsing sitemap XML: {error}")

    return urls


def smart_chunk_markdown(text: str, chunk_size: int = 5000) -> List[str]:
    """Split text into chunks, respecting code blocks and paragraphs."""
    chunks = []
    start = 0
    text_length = len(text)

    while start < text_length:
        # Calculate end position
        end = start + chunk_size

        # If we're at the end of the text, just take what's left
        if end >= text_length:
            chunks.append(text[start:].strip())
            break

        # Try to find a code block boundary first (```)
        chunk = text[start:end]
        code_block = chunk.rfind("```")
        if code_block != -1 and code_block > chunk_size * 0.3:
            end = start + code_block

        # If no code block, try to break at a paragraph
        elif "\n\n" in chunk:
            # Find the last paragraph break
            last_break = chunk.rfind("\n\n")
            if last_break > chunk_size * 0.3:  # Only break if we're past 30% of chunk_size
                end = start + last_break

        # If no paragraph break, try to break at a sentence
        elif ". " in chunk:
            # Find the last sentence break
            last_period = chunk.rfind(". ")
            if last_period > chunk_size * 0.3:  # Only break if we're past 30% of chunk_size
                end = start + last_period + 1

        # Extract chunk and clean it up
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        # Move start position for next chunk
        start = end

    return chunks


def extract_section_info(chunk: str) -> Dict[str, Any]:
    """Extract section information from a markdown chunk."""
    # Extract title from first heading
    lines = chunk.split("\n")
    title = ""
    for line in lines:
        line = line.strip()
        if line.startswith("#"):
            title = line.lstrip("#").strip()
            break

    # Extract section type based on content
    section_type = "content"
    if "```" in chunk:
        section_type = "code"
    elif any(keyword in chunk.lower() for keyword in ["table", "|"]):
        section_type = "table"

    return {"title": title, "section_type": section_type}


async def process_code_example(args):
    """Process a code example and generate summary."""
    code, context_before, context_after = args
    summary = await generate_code_example_summary(code, context_before, context_after)
    return summary


@mcp.tool()
async def crawl_single_page(ctx: Context, url: str) -> str:
    """
    Crawl a single page and extract its content.
    
    Args:
        url: The URL to crawl
    
    Returns:
        Summary of the crawled page with metadata
    """
    # Reduce local variables by organizing them better
    try:
        # Extract the Crawl4AI context
        crawl_ctx = ctx.session

        # Check if this is a sitemap
        if is_sitemap(url):
            print(f"Processing sitemap: {url}")
            urls = parse_sitemap(url)
            if urls:
                print(f"Found {len(urls)} URLs in sitemap")

                # Store the sitemap information
                # Get the source_id from the URL
                source_id = urlparse(url).netloc

                # Add sitemap info to Supabase
            contents = []
            metadatas = []
                chunk_numbers = []
                urls_list = []

                for sitemap_url in urls:
                    doc_url = sitemap_url
                    doc_content = f"Sitemap entry: {doc_url}"
                    doc_metadata = {
                        "title": f"Sitemap Entry: {doc_url}",
                        "url": doc_url,
                        "source": url,
                        "type": "sitemap_entry",
                    }

                    urls_list.append(doc_url)
                    contents.append(doc_content)
                    metadatas.append(doc_metadata)
                    chunk_numbers.append(0)  # Sitemap entries are single chunks

                # Add to Supabase
                await add_documents_to_supabase(
                    crawl_ctx.supabase_client,
                    urls_list,
                    chunk_numbers,
                    contents,
                    metadatas,
                    {url: url},  # url_to_full_document mapping
                )

                return f"Successfully processed sitemap with {len(urls)} URLs"

            return "No URLs found in sitemap"

        # Handle regular page crawling
        result = await crawl_ctx.crawler.arun(url=url)

        if result.success:
            # Store the crawled content
            content = result.cleaned_html or result.html or ""
            markdown_content = result.markdown or ""

            if not content and not markdown_content:
                return "No content extracted from the page"

            # Use markdown content if available, otherwise use cleaned HTML
            main_content = markdown_content or content

            # Generate chunks
            chunks = smart_chunk_markdown(main_content)

            # Create metadata
            base_metadata = {
                "title": result.metadata.get("title", ""),
                "description": result.metadata.get("description", ""),
                            "url": url,
                "timestamp": datetime.now().isoformat(),
                "source": urlparse(url).netloc,
            }

            # Add current task info to metadata if available
            try:
                # Safe handling of asyncio.current_task() which can return None
                current_task = asyncio.current_task()
                if current_task and hasattr(current_task, "get_coro"):
                    coro = current_task.get_coro()
                    if coro and hasattr(coro, "__name__"):
                        base_metadata["crawl_time"] = str(coro.__name__)
        else:
                        base_metadata["crawl_time"] = "unknown"
                else:
                    base_metadata["crawl_time"] = "no_task"
            except AttributeError:
                base_metadata["crawl_time"] = "error"

            # Prepare data for batch insertion
            urls_list = [url] * len(chunks)
            chunk_numbers = list(range(1, len(chunks) + 1))
            metadatas = []
            for i, chunk in enumerate(chunks):
                metadata = base_metadata.copy()
                metadata.update(extract_section_info(chunk))
                metadata["chunk_number"] = i + 1
                metadatas.append(metadata)

            # Add to Supabase
            await add_documents_to_supabase(
                crawl_ctx.supabase_client,
                urls_list,
                chunk_numbers,
                chunks,
                metadatas,
                {url: main_content},  # url_to_full_document mapping
            )

            # Extract and process code examples
            code_examples = extract_code_blocks(main_content)
            if code_examples:
                print(f"Found {len(code_examples)} code examples")

                # Generate summaries for code examples
                code_args = [
                    (example["code"], example["context_before"], example["context_after"])
                    for example in code_examples
                ]

                summaries = await asyncio.gather(
                    *[process_code_example(args) for args in code_args]
                )

                # Prepare code examples for insertion
                code_urls = [url] * len(code_examples)
                code_chunk_numbers = list(range(1, len(code_examples) + 1))
                code_metadatas = []
                for i, example in enumerate(code_examples):
                    code_metadata = base_metadata.copy()
                    code_metadata.update(
                        {
                            "language": example.get("language", ""),
                            "start_line": example.get("start_line", 0),
                            "end_line": example.get("end_line", 0),
                            "chunk_number": i + 1,
                        }
                    )

                    code_metadatas.append(code_metadata)

                # Add code examples to Supabase
                await add_code_examples_to_supabase(
                    crawl_ctx.supabase_client,
                    code_urls,
                    code_chunk_numbers,
                    [example["code"] for example in code_examples],
                    summaries,
                    code_metadatas,
                )

            # Calculate total word count
            total_words = sum(len(chunk.split()) for chunk in chunks)

            # Update source info
            source_id = urlparse(url).netloc
            source_summary = await extract_source_summary(source_id, main_content[:5000])
            update_source_info(crawl_ctx.supabase_client, source_id, source_summary, total_words)

            return (
                f"Successfully crawled and processed {url}. "
                f"Extracted {len(chunks)} chunks and {len(code_examples)} code examples."
            )

        return f"Failed to crawl {url}: {result.error_message}"

    except Exception as error:
        return f"Error crawling {url}: {str(error)}"


# Split the large smart_crawl_url function into smaller parts
def _prepare_crawl_metadata(url: str) -> Dict[str, Any]:
    """Prepare base metadata for crawling."""
    return {
        "timestamp": datetime.now().isoformat(),
        "source": urlparse(url).netloc,
    }


def _add_task_info_to_metadata(metadata: Dict[str, Any]) -> None:
    """Add current task info to metadata if available."""
    try:
        # Safe handling of asyncio.current_task() which can return None
        current_task = asyncio.current_task()
        if current_task and hasattr(current_task, "get_coro"):
            coro = current_task.get_coro()
            if coro and hasattr(coro, "__name__"):
                metadata["crawl_time"] = str(coro.__name__)
            else:
                metadata["crawl_time"] = "unknown"
        else:
            metadata["crawl_time"] = "no_task"
    except AttributeError:
        metadata["crawl_time"] = "error"


async def _process_crawl_results(
    crawl_ctx, results: List[Dict[str, Any]], chunk_size: int
) -> tuple:
    """Process crawl results and prepare for database insertion."""
    # Initialize collections
    all_urls = []
    all_contents = []
    all_metadatas = []
    all_chunk_numbers = []
        url_to_full_document = {}

    # Process each result
    for result_data in results:
        url = result_data["url"]
        content = result_data.get("content", "")
        metadata = result_data.get("metadata", {})

        if not content:
            continue

        # Store full document for contextual embeddings
        url_to_full_document[url] = content

        # Generate chunks
        chunks = smart_chunk_markdown(content, chunk_size)

        # Add to collections
        all_urls.extend([url] * len(chunks))
        all_contents.extend(chunks)
        all_chunk_numbers.extend(list(range(1, len(chunks) + 1)))

        # Create metadata for each chunk
        for i, chunk in enumerate(chunks):
            chunk_metadata = metadata.copy()
            chunk_metadata.update(extract_section_info(chunk))
            chunk_metadata["chunk_number"] = i + 1
            all_metadatas.append(chunk_metadata)

    return all_urls, all_contents, all_metadatas, all_chunk_numbers, url_to_full_document


async def _process_code_examples(crawl_ctx, results: List[Dict[str, Any]]) -> int:
    """Process code examples from crawl results."""
    total_code_examples = 0
    all_code_data = []

    # Extract code examples from all results
    for result_data in results:
        url = result_data["url"]
        content = result_data.get("content", "")
        metadata = result_data.get("metadata", {})

        if not content:
            continue

        # Extract code examples
        code_examples = extract_code_blocks(content)
            if code_examples:
            # Generate summaries for code examples
            code_args = [
                (example["code"], example["context_before"], example["context_after"])
                for example in code_examples
            ]

            summaries = await asyncio.gather(*[process_code_example(args) for args in code_args])

            # Prepare data for this URL
            for i, (example, summary) in enumerate(zip(code_examples, summaries)):
                code_metadata = metadata.copy()
                code_metadata.update(
                    {
                        "language": example.get("language", ""),
                        "start_line": example.get("start_line", 0),
                        "end_line": example.get("end_line", 0),
                        "chunk_number": i + 1,
                    }
                )

                all_code_data.append(
                    {
            "url": url,
                        "code": example["code"],
                        "summary": summary,
                        "metadata": code_metadata,
                        "chunk_number": i + 1,
                    }
                )

            total_code_examples += len(code_examples)

    # Batch insert all code examples
    if all_code_data:
        await add_code_examples_to_supabase(
            crawl_ctx.supabase_client,
            [item["url"] for item in all_code_data],
            [item["chunk_number"] for item in all_code_data],
            [item["code"] for item in all_code_data],
            [item["summary"] for item in all_code_data],
            [item["metadata"] for item in all_code_data],
        )

    return total_code_examples


@mcp.tool()
async def smart_crawl_url(
    ctx: Context,
    url: str,
    max_depth: int = 3,
    max_concurrent: int = 10,
    chunk_size: int = 5000,
) -> str:
    """
    Intelligently crawl a URL and its related pages.
    
    Args:
        url: The starting URL to crawl
        max_depth: Maximum depth for recursive crawling (default: 3)
        max_concurrent: Maximum number of concurrent requests (default: 10)
        chunk_size: Size of text chunks for processing (default: 5000)
    
    Returns:
        Summary of the crawling results
    """
    try:
        # Extract the Crawl4AI context
        crawl_ctx = ctx.session

        # Check if this is a sitemap
        if is_sitemap(url):
            print(f"Processing sitemap: {url}")
            urls = parse_sitemap(url)
            if urls:
                print(f"Found {len(urls)} URLs in sitemap. Crawling up to {len(urls)} pages...")

                # Crawl the URLs from the sitemap
                results = await crawl_batch(
                    crawl_ctx.crawler, urls[:50], max_concurrent
                )  # Limit to 50 for performance

                # Process the results
                (
                    all_urls,
                    all_contents,
                    all_metadatas,
                    all_chunk_numbers,
                    url_to_full_document,
                ) = await _process_crawl_results(crawl_ctx, results, chunk_size)

                # Batch insert all documents
                if all_contents:
                    await add_documents_to_supabase(
                        crawl_ctx.supabase_client,
                        all_urls,
                        all_chunk_numbers,
                        all_contents,
                        all_metadatas,
                        url_to_full_document,
                    )

                # Process code examples
                total_code_examples = await _process_code_examples(crawl_ctx, results)

                # Update source info
                source_id = urlparse(url).netloc
                total_content = " ".join(all_contents)
                source_summary = await extract_source_summary(source_id, total_content[:5000])
                total_words = sum(len(content.split()) for content in all_contents)
                update_source_info(
                    crawl_ctx.supabase_client, source_id, source_summary, total_words
                )

                return (
                    f"Successfully processed sitemap with {len(results)} pages. "
                    f"Extracted {len(all_contents)} chunks and {total_code_examples} code examples."
                )

            return "No URLs found in sitemap"

        # Check if this is a markdown file
        if url.endswith(".md"):
            print(f"Processing markdown file: {url}")
            results = await crawl_markdown_file(crawl_ctx.crawler, url)
        else:
            # Handle regular website crawling
            start_urls = [url]
            results = await crawl_recursive_internal_links(
                crawl_ctx.crawler, start_urls, max_depth, max_concurrent
            )

        if not results:
            return f"No content found at {url}"

        # Process the results
        (
            all_urls,
            all_contents,
            all_metadatas,
            all_chunk_numbers,
            url_to_full_document,
        ) = await _process_crawl_results(crawl_ctx, results, chunk_size)

        # Batch insert all documents
        if all_contents:
            await add_documents_to_supabase(
                crawl_ctx.supabase_client,
                all_urls,
                all_chunk_numbers,
                all_contents,
                all_metadatas,
                url_to_full_document,
            )

        # Process code examples
        total_code_examples = await _process_code_examples(crawl_ctx, results)

        # Update source info
        source_id = urlparse(url).netloc
        total_content = " ".join(all_contents)
        source_summary = await extract_source_summary(source_id, total_content[:5000])
        total_words = sum(len(content.split()) for content in all_contents)
        update_source_info(crawl_ctx.supabase_client, source_id, source_summary, total_words)

        return (
            f"Successfully crawled {len(results)} pages from {url}. "
            f"Extracted {len(all_contents)} chunks and {total_code_examples} code examples."
        )

    except Exception as error:
        return f"Error during smart crawl: {str(error)}"


@mcp.tool()
async def get_available_sources(ctx: Context) -> str:
    """
    Get a list of all available sources in the knowledge base.

    Returns:
        JSON string containing available sources with their metadata
    """
    try:
        # Extract the Crawl4AI context
        crawl_ctx = ctx.session

        # Query unique sources from crawled_pages
        response = crawl_ctx.supabase_client.table("crawled_pages").select("source_id").execute()

        if response.data:
            # Get unique source IDs
            unique_sources = {item["source_id"] for item in response.data}

            # Get detailed info for each source
            sources_info = []
            for source_id in unique_sources:
                # Get source info from source_info table
                source_response = (
                    crawl_ctx.supabase_client.table("source_info")
                    .select("*")
                    .eq("source_id", source_id)
                    .execute()
                )

                # Get page count and total word count for this source
                pages_response = (
                    crawl_ctx.supabase_client.table("crawled_pages")
                    .select("url, word_count", count="exact")
                    .eq("source_id", source_id)
                    .execute()
                )

                source_info = {
                    "source_id": source_id,
                    "page_count": len(set(item["url"] for item in pages_response.data)),
                    "total_chunks": pages_response.count,
                    "total_words": sum(item.get("word_count", 0) for item in pages_response.data),
                }

                # Add summary if available
                if source_response.data:
                    source_info["summary"] = source_response.data[0].get(
                        "summary", "No summary available"
                    )
                    source_info["last_updated"] = source_response.data[0].get(
                        "updated_at", "Unknown"
                    )
                else:
                    source_info["summary"] = "No summary available"
                    source_info["last_updated"] = "Unknown"

                sources_info.append(source_info)

            # Sort by page count (most pages first)
            sources_info.sort(key=lambda x: x["page_count"], reverse=True)

            return json.dumps(sources_info, indent=2)

        return json.dumps({"message": "No sources found in the knowledge base"})

    except Exception as error:
        return json.dumps({"error": f"Failed to get available sources: {str(error)}"})


@mcp.tool()
async def perform_rag_query(
    ctx: Context, query: str, source: Optional[str] = None, match_count: int = 5
) -> str:
    """
    Perform a RAG (Retrieval-Augmented Generation) query against the knowledge base.
    
    Args:
        query: The question or query to search for
        source: Optional source filter (e.g., 'docs.python.org')
        match_count: Number of relevant chunks to retrieve (default: 5)
    
    Returns:
        AI-generated response based on retrieved context
    """
    try:
        # Extract the Crawl4AI context
        crawl_ctx = ctx.session

        # Build filter metadata
        filter_metadata = {}
        if source:
            filter_metadata["source"] = source

        # Search for relevant documents
        documents = search_documents(
            crawl_ctx.supabase_client,
            query,
            match_count=match_count * 2,  # Get more initially for reranking
            filter_metadata=filter_metadata if filter_metadata else None,
        )

        if not documents:
            return json.dumps(
                {
                    "answer": "No relevant documents found in the knowledge base.",
                    "sources": [],
                    "query": query,
                }
            )

        # Apply reranking if model is available
        if crawl_ctx.reranking_model:
            print(f"Reranking {len(documents)} documents...")
            documents = rerank_results(crawl_ctx.reranking_model, query, documents, "content")

        # Take the top matches after reranking
        documents = documents[:match_count]

        # Create context from retrieved documents
        context_parts = []
        sources = []

        for i, doc in enumerate(documents, 1):
            content = doc.get("content", "")
            url = doc.get("url", "")
            title = doc.get("title", "")

            context_parts.append(f"Document {i}:\nTitle: {title}\nURL: {url}\nContent: {content}")

            # Add to sources
            source_info = {
                "url": url,
                "title": title,
                "relevance_score": doc.get("similarity", 0),
            }
            if crawl_ctx.reranking_model and "rerank_score" in doc:
                source_info["rerank_score"] = doc["rerank_score"]

            sources.append(source_info)

        context = "\n\n".join(context_parts)

        # Create the prompt for the AI
        system_prompt = """You are a helpful assistant that answers questions based on the provided context documents.

        Guidelines:
        - Answer the question using only the information provided in the context documents
        - If the context doesn't contain enough information to answer the question, say so
        - Cite specific sources when possible by referencing the document titles or URLs
        - Be concise but comprehensive in your response
        - If there are conflicting information in the documents, acknowledge this"""

        user_prompt = f"""Context documents:
        {context}

        Question: {query}

        Please provide a comprehensive answer based on the context documents above."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        # Generate response using AI provider
        response = await crawl_ctx.ai_provider.create_completion(
            messages=messages, temperature=0.3, max_tokens=1000
        )

        return json.dumps(
            {
                "answer": response.content,
                "sources": sources,
                "query": query,
                "total_documents_found": len(documents),
            },
            indent=2,
        )

    except Exception as error:
        return json.dumps({"error": f"Failed to perform RAG query: {str(error)}", "query": query})


@mcp.tool()
async def search_code_examples(
    ctx: Context, query: str, source_id: Optional[str] = None, match_count: int = 5
) -> str:
    """
    Search for code examples in the knowledge base.

    Args:
        query: Search query for code examples
        source_id: Optional source filter (e.g., 'docs.python.org')
        match_count: Number of code examples to return (default: 5)

    Returns:
        JSON string containing matching code examples
    """
    try:
        # Extract the Crawl4AI context
        crawl_ctx = ctx.session

        # Search for code examples
        code_examples = await search_code_examples_util(
            crawl_ctx.supabase_client,
            query,
            match_count=match_count * 2,  # Get more for potential reranking
            source_id=source_id,
        )

        if not code_examples:
            return json.dumps(
                {
                    "message": "No code examples found matching your query.",
                    "query": query,
                    "results": [],
                }
            )

        # Apply reranking if model is available
        if crawl_ctx.reranking_model:
            print(f"Reranking {len(code_examples)} code examples...")
            code_examples = rerank_results(
                crawl_ctx.reranking_model, query, code_examples, "summary"
            )

        # Take the top matches after reranking
        code_examples = code_examples[:match_count]

        # Format results
        results = []
        for example in code_examples:
            result = {
                "url": example.get("url", ""),
                "language": example.get("language", ""),
                "code": example.get("code", ""),
                "summary": example.get("summary", ""),
                "metadata": example.get("metadata", {}),
                "relevance_score": example.get("similarity", 0),
            }

            if crawl_ctx.reranking_model and "rerank_score" in example:
                result["rerank_score"] = example["rerank_score"]

            results.append(result)

        return json.dumps(
            {
            "query": query,
                "total_found": len(results),
                "results": results,
            },
            indent=2,
        )

    except Exception as error:
        return json.dumps(
            {"error": f"Failed to search code examples: {str(error)}", "query": query}
        )


async def crawl_markdown_file(crawler: AsyncWebCrawler, url: str) -> List[Dict[str, Any]]:
    """
    Crawl a markdown file from a URL.
    
    Args:
        crawler: The AsyncWebCrawler instance
        url: URL of the markdown file
        
    Returns:
        List containing the crawled markdown content
    """
    try:
        result = await crawler.arun(url=url)

        if result.success:
            content = result.cleaned_html or result.html or ""
            markdown_content = result.markdown or ""

            # Use markdown content if available, otherwise use cleaned HTML
            main_content = markdown_content or content

            if main_content:
                return [
                    {
                        "url": url,
                        "content": main_content,
                        "metadata": {
                            "title": result.metadata.get("title", ""),
                            "description": result.metadata.get("description", ""),
                            "url": url,
                            "timestamp": datetime.now().isoformat(),
                            "source": urlparse(url).netloc,
                        },
                    }
                ]

        return []

    except Exception as error:
        print(f"Error crawling markdown file {url}: {error}")
        return []


async def crawl_batch(
    crawler: AsyncWebCrawler, urls: List[str], max_concurrent: int = 10
) -> List[Dict[str, Any]]:
    """
    Crawl a batch of URLs concurrently.
    
    Args:
        crawler: The AsyncWebCrawler instance
        urls: List of URLs to crawl
        max_concurrent: Maximum number of concurrent requests
        
    Returns:
        List of crawled results
    """
    # Create semaphore to limit concurrent requests
    semaphore = asyncio.Semaphore(max_concurrent)

    async def crawl_single(url):
        async with semaphore:
            try:
                result = await crawler.arun(url=url)
                if result.success:
                    content = result.cleaned_html or result.html or ""
                    markdown_content = result.markdown or ""
                    main_content = markdown_content or content

                    if main_content:
                        return {
                            "url": url,
                            "content": main_content,
                            "metadata": {
                                "title": result.metadata.get("title", ""),
                                "description": result.metadata.get("description", ""),
                                "url": url,
                                "timestamp": datetime.now().isoformat(),
                                "source": urlparse(url).netloc,
                            },
                        }
                return None
            except Exception as error:
                print(f"Error crawling {url}: {error}")
                return None

    # Execute all crawls concurrently
    tasks = [crawl_single(url) for url in urls]
    task_results = await asyncio.gather(*tasks, return_exceptions=True)

    # Filter out None results and exceptions, ensuring proper typing
    valid_results: List[Dict[str, Any]] = []
    for result in task_results:
        if result is not None and not isinstance(result, Exception) and isinstance(result, dict):
            valid_results.append(result)

    return valid_results


async def crawl_recursive_internal_links(
    crawler: AsyncWebCrawler,
    start_urls: List[str],
    max_depth: int = 3,
    max_concurrent: int = 10,
) -> List[Dict[str, Any]]:
    """
    Crawl internal links recursively up to a specified depth.
    
    Args:
        crawler: The AsyncWebCrawler instance
        start_urls: List of starting URLs
        max_depth: Maximum recursion depth
        max_concurrent: Maximum number of concurrent requests
        
    Returns:
        List of crawled results
    """

    def normalize_url(url):
        """Normalize URL for comparison."""
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")

    visited = set()
    all_results = []

    for start_url in start_urls:
        base_domain = urlparse(start_url).netloc
        to_visit = [(start_url, 0)]  # (url, depth)

        while to_visit:
            current_batch = []
            next_to_visit = []

            # Prepare current batch
            for url, current_depth in to_visit:
                if current_depth <= max_depth:
                    normalized_url = normalize_url(url)
                    if normalized_url not in visited:
                        visited.add(normalized_url)
                        current_batch.append(url)

                        # If we haven't reached max depth, prepare for next level
                        if current_depth < max_depth:
                            next_to_visit.append((url, current_depth))

            # Crawl current batch
            if current_batch:
                batch_results = await crawl_batch(crawler, current_batch, max_concurrent)
                all_results.extend(batch_results)

                # Extract internal links for next level
                for result in batch_results:
                    if result and result.get("content"):
                        # This is a simplified link extraction
                        # In a real implementation, you'd parse the HTML/markdown more thoroughly
                        content = result["content"]
                        # Simple regex to find links (this is very basic)
                        import re

                        links = re.findall(r'href=[\'"]([^\'"]+)[\'"]', content)
                        for link in links:
                            # Make absolute URL
                            if link.startswith("/"):
                                link = f"https://{base_domain}{link}"
                            elif not link.startswith("http"):
                                continue

                            # Check if it's an internal link
                            if urlparse(link).netloc == base_domain:
                                for url, depth in next_to_visit:
                                    if url == result["url"]:
                                        to_visit.append((link, depth + 1))
                                        break

            # Update to_visit for next iteration
            to_visit = []

    return all_results


async def main():
    """Main function to run the MCP server."""
    await mcp.run()


if __name__ == "__main__":
    asyncio.run(main())
