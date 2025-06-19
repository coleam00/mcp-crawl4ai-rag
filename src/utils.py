"""
Utility functions for the Crawl4AI MCP server.
"""

import asyncio
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from supabase import Client

from providers import get_provider_manager

# Global variable to store AI provider
ai_provider = None


def get_ai_provider():
    """Get or create AI provider instance."""
    global ai_provider
    if ai_provider is None:
        ai_provider = get_provider_manager()
    return ai_provider


def get_supabase_client() -> Client:
    """Initialize and return Supabase client."""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_ANON_KEY")

    if not url or not key:
        raise ValueError("SUPABASE_URL and SUPABASE_ANON_KEY environment variables are required")

    return Client(url, key)


async def create_embeddings_batch(texts: List[str]) -> List[List[float]]:
    """
    Create embeddings for a batch of texts using the configured AI provider.

    Args:
        texts: List of texts to create embeddings for

    Returns:
        List of embeddings (each embedding is a list of floats)
    """
    if not texts:
        return []

    try:
        provider = get_ai_provider()
        response = await provider.create_embeddings(texts)
        return response.embeddings

    except Exception as error:
        print(f"Error creating embeddings: {error}")
        # Return zero embeddings as fallback
        return [[0.0] * 1536 for _ in texts]


async def create_embedding(text: str) -> List[float]:
    """
    Create embedding for a single text using the configured AI provider.

    Args:
        text: Text to create embedding for

    Returns:
        Embedding as a list of floats
    """
    if not text:
        return [0.0] * 1536

    try:
        embeddings = await create_embeddings_batch([text])
        return embeddings[0] if embeddings else [0.0] * 1536

    except Exception as error:
        print(f"Error creating embedding: {error}")
        return [0.0] * 1536


async def generate_contextual_embedding(full_document: str, chunk: str) -> Tuple[str, bool]:
    """
    Generate contextual embedding for a chunk within a document.

    Args:
        full_document: The full document content
        chunk: The chunk to generate contextual information for

    Returns:
        Tuple containing:
        - The contextual text that situates the chunk within the document
        - Boolean indicating if contextual embedding was performed
    """
    try:
        # Create the prompt for generating contextual information
        prompt = f"""<document> 
{full_document[:25000]} 
</document>
Here is the chunk we want to situate within the whole document 
<chunk> 
{chunk}
</chunk> 
Please give a short succinct context to situate this chunk within the overall
document for the purposes of improving search retrieval of the chunk.
Answer only with the succinct context and nothing else."""

        messages = [
            {
                "role": "system",
                "content": "You are a helpful assistant that provides concise contextual information.",
            },
            {"role": "user", "content": prompt},
        ]

        # Call the AI provider to generate contextual information
        provider = get_ai_provider()
        response = await provider.create_completion(
            messages=messages, temperature=0.3, max_tokens=200
        )

        # Extract the generated context
        context = response.content.strip()

        # Combine the context with the original chunk
        contextual_text = f"{context}\n---\n{chunk}"

        return contextual_text, True

    except Exception as error:
        print(f"Error generating contextual embedding: {error}. " "Using original chunk instead.")
        return chunk, False


async def process_chunk_with_context(args):
    """
    Process a single chunk with contextual embedding.
    This function is designed to be used with asyncio.gather.

    Args:
        args: Tuple containing (url, content, full_document)

    Returns:
        Tuple containing:
        - The contextual text that situates the chunk within the document
        - Boolean indicating if contextual embedding was performed
    """
    _, content, full_document = args
    return await generate_contextual_embedding(full_document, content)


async def add_documents_to_supabase(
    client: Client,
    urls: List[str],
    chunk_numbers: List[int],
    contents: List[str],
    metadatas: List[Dict[str, Any]],
    url_to_full_document: Dict[str, str],
    batch_size: int = 20,
) -> None:
    """
    Add documents to the Supabase crawled_pages table in batches.
    Deletes existing records with the same URLs before inserting to prevent duplicates.

    Args:
        client: Supabase client
        urls: List of URLs
        chunk_numbers: List of chunk numbers
        contents: List of document contents
        metadatas: List of document metadata
        url_to_full_document: Dictionary mapping URLs to their full document content
        batch_size: Size of each batch for insertion
    """
    # Get unique URLs to delete existing records
    unique_urls = list(set(urls))

    # Delete existing records for these URLs in a single operation
    try:
        if unique_urls:
            # Use the .in_() filter to delete all records with matching URLs
            client.table("crawled_pages").delete().in_("url", unique_urls).execute()
    except Exception as error:
        print(f"Batch delete failed: {error}. Trying one-by-one deletion as fallback.")
        # Fallback: delete records one by one
        for url in unique_urls:
            try:
                client.table("crawled_pages").delete().eq("url", url).execute()
            except Exception as delete_error:
                print(f"Failed to delete records for URL {url}: {delete_error}")

    # Check if contextual embeddings are enabled
    use_contextual_embeddings = os.getenv("USE_CONTEXTUAL_EMBEDDINGS", "false") == "true"

    # Process all chunks for contextual embeddings if enabled
    if use_contextual_embeddings:
        print("Generating contextual embeddings...")

        # Create a list of arguments for processing
        process_args = []
        for i, content in enumerate(contents):
            url = urls[i]
            full_document = url_to_full_document.get(url, content)
            process_args.append((url, content, full_document))

        # Process contextual embeddings with asyncio
        contextual_results = await asyncio.gather(
            *[process_chunk_with_context(args) for args in process_args]
        )

        # Update contents with contextual information
        for i, (contextual_text, success) in enumerate(contextual_results):
            if success:
                contents[i] = contextual_text

    # Generate embeddings for all content
    embeddings = await create_embeddings_batch(contents)

    # Prepare documents for insertion
    documents = []

    for i in range(len(urls)):
        source_id = urlparse(urls[i]).netloc

        doc = {
            "url": urls[i],
            "chunk_number": chunk_numbers[i],
            "content": contents[i],
            "embedding": embeddings[i],
            "metadata": metadatas[i],
            "source_id": source_id,
            "title": metadatas[i].get("title", ""),
            "word_count": len(contents[i].split()),
        }
        documents.append(doc)

    # Insert documents in batches
    for i in range(0, len(documents), batch_size):
        batch = documents[i : i + batch_size]
        try:
            client.table("crawled_pages").insert(batch).execute()
            print(
                f"Successfully inserted batch {i//batch_size + 1} " f"with {len(batch)} documents"
            )
        except Exception as error:
            print(f"Failed to insert batch {i//batch_size + 1}: {error}")
            # Try inserting documents one by one as fallback
            successful_insertions = 0
            for doc in batch:
                try:
                    client.table("crawled_pages").insert(doc).execute()
                    successful_insertions += 1
                except Exception as doc_error:
                    print(f"Failed to insert document {doc['url']}: {doc_error}")

            print(
                f"Successfully inserted {successful_insertions}/{len(batch)} "
                f"documents individually in batch {i//batch_size + 1}"
            )


def search_documents(
    client: Client,
    query: str,
    match_count: int = 10,
    filter_metadata: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Search documents in the Supabase vector database.

    Args:
        client: Supabase client
        query: Search query
        match_count: Number of matches to return
        filter_metadata: Optional metadata filters

    Returns:
        List of matching documents
    """
    # Note: This function remains synchronous for now, but embedding creation is async
    # For now, we'll use a workaround until we can refactor the entire codebase to be async
    try:
        # Create embedding for the query
        if hasattr(asyncio, "get_running_loop"):
            # We're in an async context, create a new event loop in a thread
            import threading

            result: List[Optional[List[float]]] = [None]
            exception: List[Optional[Exception]] = [None]

            def run_in_thread():
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    result[0] = loop.run_until_complete(create_embedding(query))
                except Exception as error:
                    exception[0] = error
                finally:
                    loop.close()

            thread = threading.Thread(target=run_in_thread)
            thread.start()
            thread.join()

            if exception[0]:
                raise exception[0]

            query_embedding = result[0]
        else:
            raise RuntimeError("No event loop found")

    except Exception as error:
        print(f"Error creating query embedding: {error}")
        return []

    try:
        # Use Supabase's match_documents function for vector similarity search
        rpc_params = {
            "query_embedding": query_embedding,
            "match_count": match_count,
        }

        # Add filter metadata if provided
        if filter_metadata:
            rpc_params["filter_metadata"] = filter_metadata

        response = client.rpc("match_documents", rpc_params).execute()

        return response.data if response.data else []

    except Exception as error:
        print(f"Error searching documents: {error}")
        return []


def extract_code_blocks(markdown_content: str, min_length: int = 1000) -> List[Dict[str, Any]]:
    """
    Extract code blocks from markdown content.

    Args:
        markdown_content: The markdown content to parse
        min_length: Minimum length of code blocks to extract

    Returns:
        List of dictionaries containing code block information
    """
    code_blocks = []
    lines = markdown_content.split("\n")
    in_code_block = False
    current_block = []
    language = ""
    start_line = 0

    for i, line in enumerate(lines):
        if line.strip().startswith("```"):
            if not in_code_block:
                # Starting a code block
                in_code_block = True
                current_block = []
                language = line.strip()[3:].strip()  # Extract language
                start_line = i + 1
            else:
                # Ending a code block
                in_code_block = False
                code_content = "\n".join(current_block)

                # Only include blocks that meet minimum length requirement
                if len(code_content) >= min_length:
                    # Get context before and after the code block
                    context_start = max(0, start_line - 5)
                    context_end = min(len(lines), i + 5)

                    context_before = "\n".join(lines[context_start : start_line - 1])
                    context_after = "\n".join(lines[i + 1 : context_end])

        code_blocks.append(
            {
                "code": code_content,
                "language": language,
                "start_line": start_line,
                "end_line": i,
                "context_before": context_before,
                "context_after": context_after,
            }
        )
        current_block = []
        language = ""
        if in_code_block:
            current_block.append(line)

    return code_blocks


async def generate_code_example_summary(code: str, context_before: str, context_after: str) -> str:
    """
    Generate a summary for a code example using AI.

    Args:
        code: The code content
        context_before: Context before the code block
        context_after: Context after the code block

    Returns:
        AI-generated summary of the code example
    """
    try:
        prompt = f"""Please analyze this code example and provide a concise summary:

Context before:
{context_before}

Code:
{code}

Context after:
{context_after}

Provide a brief summary that explains:
1. What this code does
2. Key concepts or patterns demonstrated
3. Any notable features or techniques used

Keep the summary concise but informative."""

        messages = [
            {
                "role": "system",
                "content": "You are a helpful programming assistant that explains code clearly and concisely.",
            },
            {"role": "user", "content": prompt},
        ]

        provider = get_ai_provider()
        response = await provider.create_completion(
            messages=messages, temperature=0.3, max_tokens=300
        )

        return response.content.strip()

    except Exception as error:
        print(f"Error generating code summary: {error}")
        return f"Code example in {code[:50]}..." if code else "Code example"


async def add_code_examples_to_supabase(
    client: Client,
    urls: List[str],
    chunk_numbers: List[int],
    code_examples: List[str],
    summaries: List[str],
    metadatas: List[Dict[str, Any]],
    batch_size: int = 20,
):
    """
    Add code examples to the Supabase code_examples table in batches.
    Deletes existing records with the same URLs before inserting to prevent duplicates.

    Args:
        client: Supabase client
        urls: List of URLs
        chunk_numbers: List of chunk numbers
        code_examples: List of code examples
        summaries: List of code example summaries
        metadatas: List of metadata dictionaries
        batch_size: Size of each batch for insertion
    """
    # Get unique URLs to delete existing records
    unique_urls = list(set(urls))

    # Delete existing records for these URLs
    try:
        if unique_urls:
            client.table("code_examples").delete().in_("url", unique_urls).execute()
    except Exception as error:
        print(f"Batch delete failed: {error}. Trying one-by-one deletion as fallback.")
        for url in unique_urls:
            try:
                client.table("code_examples").delete().eq("url", url).execute()
            except Exception as delete_error:
                print(f"Failed to delete code examples for URL {url}: {delete_error}")

    # Generate embeddings for all summaries
    embeddings = await create_embeddings_batch(summaries)

    # Prepare code examples for insertion
    examples = []

    for i in range(len(urls)):
        source_id = urlparse(urls[i]).netloc

        example = {
            "url": urls[i],
            "chunk_number": chunk_numbers[i],
            "code": code_examples[i],
            "summary": summaries[i],
            "embedding": embeddings[i],
            "metadata": metadatas[i],
            "source_id": source_id,
            "language": metadatas[i].get("language", ""),
        }
        examples.append(example)

    # Insert examples in batches
    for i in range(0, len(examples), batch_size):
        batch = examples[i : i + batch_size]
        try:
            client.table("code_examples").insert(batch).execute()
            print(
                f"Successfully inserted code examples batch "
                f"{i//batch_size + 1} with {len(batch)} examples"
            )
        except Exception as error:
            print(f"Failed to insert code examples batch {i//batch_size + 1}: {error}")
            # Try inserting examples one by one as fallback
            successful_insertions = 0
            for example in batch:
                try:
                    client.table("code_examples").insert(example).execute()
                    successful_insertions += 1
                except Exception as example_error:
                    print(f"Failed to insert code example {example['url']}: {example_error}")

            print(
                f"Successfully inserted {successful_insertions}/{len(batch)} "
                f"code examples individually in batch {i//batch_size + 1}"
            )


def update_source_info(client: Client, source_id: str, summary: str, word_count: int):
    """
    Update or insert source information in the source_info table.

    Args:
        client: Supabase client
        source_id: The source identifier
        summary: Summary of the source
        word_count: Total word count for the source
    """
    try:
        # Check if source already exists
        existing = client.table("source_info").select("id").eq("source_id", source_id).execute()

        source_data = {
            "source_id": source_id,
            "summary": summary,
            "word_count": word_count,
            "updated_at": datetime.now().isoformat(),
        }

        if existing.data:
            # Update existing record
            client.table("source_info").update(source_data).eq("source_id", source_id).execute()
        else:
            # Insert new record
            source_data["created_at"] = datetime.now().isoformat()
            client.table("source_info").insert(source_data).execute()

        print(f"Updated source info for {source_id}")

    except Exception as error:
        print(f"Error updating source info: {error}")


async def extract_source_summary(source_id: str, content: str, max_length: int = 500) -> str:
    """
    Extract a summary for a source using AI.

    Args:
        source_id: The source identifier
        content: Sample content from the source
        max_length: Maximum length of the summary

    Returns:
        AI-generated summary of the source
    """
    try:
        prompt = f"""Please analyze this content from the source "{source_id}" and provide a concise summary:

{content}

Provide a brief summary that explains:
1. What type of content this source contains
2. The main topics or themes covered
3. The target audience or use case

Keep the summary under {max_length} characters and focus on what would be most helpful for someone searching this knowledge base."""

        messages = [
            {
                "role": "system",
                "content": "You are a helpful assistant that creates concise summaries of content sources.",
            },
            {"role": "user", "content": prompt},
        ]

        provider = get_ai_provider()
        response = await provider.create_completion(
            messages=messages, temperature=0.3, max_tokens=150
        )

        summary = response.content.strip()
        return summary[:max_length] if len(summary) > max_length else summary

    except Exception as error:
        print(f"Error generating source summary: {error}")
        return f"Content from {source_id}"


async def search_code_examples(
    client: Client,
    query: str,
    match_count: int = 10,
    filter_metadata: Optional[Dict[str, Any]] = None,
    source_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Search code examples in the Supabase vector database.

    Args:
        client: Supabase client
        query: Search query
        match_count: Number of matches to return
        filter_metadata: Optional metadata filters
        source_id: Optional source ID filter

    Returns:
        List of matching code examples
    """
    try:
        # Create embedding for the query
        query_embedding = await create_embedding(query)

        # Use Supabase's match_code_examples function for vector similarity search
        rpc_params = {
            "query_embedding": query_embedding,
            "match_count": match_count,
        }

        # Add filters if provided
        if filter_metadata:
            rpc_params["filter_metadata"] = filter_metadata

        if source_id:
            rpc_params["source_id"] = source_id

        response = client.rpc("match_code_examples", rpc_params).execute()

        return response.data if response.data else []

    except Exception as error:
        print(f"Error searching code examples: {error}")
        return []
