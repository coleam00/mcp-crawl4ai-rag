"""
Utility functions for the Crawl4AI MCP server.
"""
import os
import concurrent.futures
from typing import List, Dict, Any, Optional, Tuple
import json
import re
from supabase import create_client, Client
from urllib.parse import urlparse, urljoin
import openai
import time
from pathlib import Path

# Load OpenAI API key for embeddings
openai.api_key = os.getenv("OPENAI_API_KEY")

def get_supabase_client() -> Client:
    """
    Get a Supabase client with the URL and key from environment variables.
    
    Returns:
        Supabase client instance
    """
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")
    
    if not url or not key:
        raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in environment variables")
    
    return create_client(url, key)

def create_embeddings_batch(texts: List[str]) -> List[List[float]]:
    """
    Create embeddings for multiple texts in a single API call.
    
    Args:
        texts: List of texts to create embeddings for
        
    Returns:
        List of embeddings (each embedding is a list of floats)
    """
    if not texts:
        return []
    
    max_retries = 3
    retry_delay = 1.0  # Start with 1 second delay
    
    for retry in range(max_retries):
        try:
            response = openai.embeddings.create(
                model="text-embedding-3-small", # Hardcoding embedding model for now, will change this later to be more dynamic
                input=texts
            )
            return [item.embedding for item in response.data]
        except Exception as e:
            if retry < max_retries - 1:
                print(f"Error creating batch embeddings (attempt {retry + 1}/{max_retries}): {e}")
                print(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                print(f"Failed to create batch embeddings after {max_retries} attempts: {e}")
                # Try creating embeddings one by one as fallback
                print("Attempting to create embeddings individually...")
                embeddings = []
                successful_count = 0
                
                for i, text in enumerate(texts):
                    try:
                        individual_response = openai.embeddings.create(
                            model="text-embedding-3-small",
                            input=[text]
                        )
                        embeddings.append(individual_response.data[0].embedding)
                        successful_count += 1
                    except Exception as individual_error:
                        print(f"Failed to create embedding for text {i}: {individual_error}")
                        # Add zero embedding as fallback
                        embeddings.append([0.0] * 1536)
                
                print(f"Successfully created {successful_count}/{len(texts)} embeddings individually")
                return embeddings

def create_embedding(text: str) -> List[float]:
    """
    Create an embedding for a single text using OpenAI's API.
    
    Args:
        text: Text to create an embedding for
        
    Returns:
        List of floats representing the embedding
    """
    try:
        embeddings = create_embeddings_batch([text])
        return embeddings[0] if embeddings else [0.0] * 1536
    except Exception as e:
        print(f"Error creating embedding: {e}")
        # Return empty embedding if there's an error
        return [0.0] * 1536

def generate_contextual_embedding(full_document: str, chunk: str) -> Tuple[str, bool]:
    """
    Generate contextual information for a chunk within a document to improve retrieval.
    
    Args:
        full_document: The complete document text
        chunk: The specific chunk of text to generate context for
        
    Returns:
        Tuple containing:
        - The contextual text that situates the chunk within the document
        - Boolean indicating if contextual embedding was performed
    """
    model_choice = os.getenv("MODEL_CHOICE")
    
    try:
        # Create the prompt for generating contextual information
        prompt = f"""<document> 
{full_document[:25000]} 
</document>
Here is the chunk we want to situate within the whole document 
<chunk> 
{chunk}
</chunk> 
Please give a short succinct context to situate this chunk within the overall document for the purposes of improving search retrieval of the chunk. Answer only with the succinct context and nothing else."""

        # Call the OpenAI API to generate contextual information
        response = openai.chat.completions.create(
            model=model_choice,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that provides concise contextual information."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=200
        )
        
        # Extract the generated context
        context = response.choices[0].message.content.strip()
        
        # Combine the context with the original chunk
        contextual_text = f"{context}\n---\n{chunk}"
        
        return contextual_text, True
    
    except Exception as e:
        print(f"Error generating contextual embedding: {e}. Using original chunk instead.")
        return chunk, False

def process_chunk_with_context(args):
    """
    Process a single chunk with contextual embedding.
    This function is designed to be used with concurrent.futures.
    
    Args:
        args: Tuple containing (url, content, full_document)
        
    Returns:
        Tuple containing:
        - The contextual text that situates the chunk within the document
        - Boolean indicating if contextual embedding was performed
    """
    url, content, full_document = args
    return generate_contextual_embedding(full_document, content)

def add_documents_to_supabase(
    client: Client, 
    urls: List[str], 
    chunk_numbers: List[int],
    contents: List[str], 
    metadatas: List[Dict[str, Any]],
    url_to_full_document: Dict[str, str],
    batch_size: int = 20
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
    except Exception as e:
        print(f"Batch delete failed: {e}. Trying one-by-one deletion as fallback.")
        # Fallback: delete records one by one
        for url in unique_urls:
            try:
                client.table("crawled_pages").delete().eq("url", url).execute()
            except Exception as inner_e:
                print(f"Error deleting record for URL {url}: {inner_e}")
                # Continue with the next URL even if one fails
    
    # Check if MODEL_CHOICE is set for contextual embeddings
    use_contextual_embeddings = os.getenv("USE_CONTEXTUAL_EMBEDDINGS", "false") == "true"
    print(f"\n\nUse contextual embeddings: {use_contextual_embeddings}\n\n")
    
    # Process in batches to avoid memory issues
    for i in range(0, len(contents), batch_size):
        batch_end = min(i + batch_size, len(contents))
        
        # Get batch slices
        batch_urls = urls[i:batch_end]
        batch_chunk_numbers = chunk_numbers[i:batch_end]
        batch_contents = contents[i:batch_end]
        batch_metadatas = metadatas[i:batch_end]
        
        # Apply contextual embedding to each chunk if MODEL_CHOICE is set
        if use_contextual_embeddings:
            # Prepare arguments for parallel processing
            process_args = []
            for j, content in enumerate(batch_contents):
                url = batch_urls[j]
                full_document = url_to_full_document.get(url, "")
                process_args.append((url, content, full_document))
            
            # Process in parallel using ThreadPoolExecutor
            contextual_contents = []
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                # Submit all tasks and collect results
                future_to_idx = {executor.submit(process_chunk_with_context, arg): idx 
                                for idx, arg in enumerate(process_args)}
                
                # Process results as they complete
                for future in concurrent.futures.as_completed(future_to_idx):
                    idx = future_to_idx[future]
                    try:
                        result, success = future.result()
                        contextual_contents.append(result)
                        if success:
                            batch_metadatas[idx]["contextual_embedding"] = True
                    except Exception as e:
                        print(f"Error processing chunk {idx}: {e}")
                        # Use original content as fallback
                        contextual_contents.append(batch_contents[idx])
            
            # Sort results back into original order if needed
            if len(contextual_contents) != len(batch_contents):
                print(f"Warning: Expected {len(batch_contents)} results but got {len(contextual_contents)}")
                # Use original contents as fallback
                contextual_contents = batch_contents
        else:
            # If not using contextual embeddings, use original contents
            contextual_contents = batch_contents
        
        # Create embeddings for the entire batch at once
        batch_embeddings = create_embeddings_batch(contextual_contents)
        
        batch_data = []
        for j in range(len(contextual_contents)):
            # Extract metadata fields
            chunk_size = len(contextual_contents[j])
            
            # Use source_id from metadata if available, otherwise extract from URL
            source_id = batch_metadatas[j].get("source_id")
            if not source_id:
                # Fallback to extracting from URL for backward compatibility
                parsed_url = urlparse(batch_urls[j])
                source_id = parsed_url.netloc or parsed_url.path
            
            # Prepare metadata without source_id (since it's a separate field)
            metadata_clean = {k: v for k, v in batch_metadatas[j].items() if k != "source_id"}
            
            # Prepare data for insertion
            data = {
                "url": batch_urls[j],
                "chunk_number": batch_chunk_numbers[j],
                "content": contextual_contents[j],  # Store original content
                "metadata": {
                    "chunk_size": chunk_size,
                    **metadata_clean
                },
                "source_id": source_id,  # Add source_id field
                "embedding": batch_embeddings[j]  # Use embedding from contextual content
            }
            
            batch_data.append(data)
        
        # Insert batch into Supabase with retry logic
        max_retries = 3
        retry_delay = 1.0  # Start with 1 second delay
        
        for retry in range(max_retries):
            try:
                client.table("crawled_pages").insert(batch_data).execute()
                # Success - break out of retry loop
                break
            except Exception as e:
                if retry < max_retries - 1:
                    print(f"Error inserting batch into Supabase (attempt {retry + 1}/{max_retries}): {e}")
                    print(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    # Final attempt failed
                    print(f"Failed to insert batch after {max_retries} attempts: {e}")
                    # Optionally, try inserting records one by one as a last resort
                    print("Attempting to insert records individually...")
                    successful_inserts = 0
                    for record in batch_data:
                        try:
                            client.table("crawled_pages").insert(record).execute()
                            successful_inserts += 1
                        except Exception as individual_error:
                            print(f"Failed to insert individual record for URL {record['url']}: {individual_error}")
                    
                    if successful_inserts > 0:
                        print(f"Successfully inserted {successful_inserts}/{len(batch_data)} records individually")

def search_documents(
    client: Client, 
    query: str, 
    match_count: int = 10, 
    filter_metadata: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    Search for documents in Supabase using vector similarity.
    
    Args:
        client: Supabase client
        query: Query text
        match_count: Maximum number of results to return
        filter_metadata: Optional metadata filter
        
    Returns:
        List of matching documents
    """
    # Create embedding for the query
    query_embedding = create_embedding(query)
    
    # Execute the search using the match_crawled_pages function
    try:
        # Only include filter parameter if filter_metadata is provided and not empty
        params = {
            'query_embedding': query_embedding,
            'match_count': match_count
        }
        
        # Only add the filter if it's actually provided and not empty
        if filter_metadata:
            params['filter'] = filter_metadata  # Pass the dictionary directly, not JSON-encoded
        
        result = client.rpc('match_crawled_pages', params).execute()
        
        return result.data
    except Exception as e:
        print(f"Error searching documents: {e}")
        return []


def extract_code_blocks(markdown_content: str, min_length: int = 1000) -> List[Dict[str, Any]]:
    """
    Extract code blocks from markdown content along with context.
    
    Args:
        markdown_content: The markdown content to extract code blocks from
        min_length: Minimum length of code blocks to extract (default: 1000 characters)
        
    Returns:
        List of dictionaries containing code blocks and their context
    """
    code_blocks = []
    
    # Skip if content starts with triple backticks (edge case for files wrapped in backticks)
    content = markdown_content.strip()
    start_offset = 0
    if content.startswith('```'):
        # Skip the first triple backticks
        start_offset = 3
        print("Skipping initial triple backticks")
    
    # Find all occurrences of triple backticks
    backtick_positions = []
    pos = start_offset
    while True:
        pos = markdown_content.find('```', pos)
        if pos == -1:
            break
        backtick_positions.append(pos)
        pos += 3
    
    # Process pairs of backticks
    i = 0
    while i < len(backtick_positions) - 1:
        start_pos = backtick_positions[i]
        end_pos = backtick_positions[i + 1]
        
        # Extract the content between backticks
        code_section = markdown_content[start_pos+3:end_pos]
        
        # Check if there's a language specifier on the first line
        lines = code_section.split('\n', 1)
        if len(lines) > 1:
            # Check if first line is a language specifier (no spaces, common language names)
            first_line = lines[0].strip()
            if first_line and ' ' not in first_line and len(first_line) < 20:
                language = first_line
                code_content = lines[1].strip() if len(lines) > 1 else ""
            else:
                language = ""
                code_content = code_section.strip()
        else:
            language = ""
            code_content = code_section.strip()
        
        # Skip if code block is too short
        if len(code_content) < min_length:
            i += 2  # Move to next pair
            continue
        
        # Extract context before (1000 chars)
        context_start = max(0, start_pos - 1000)
        context_before = markdown_content[context_start:start_pos].strip()
        
        # Extract context after (1000 chars)
        context_end = min(len(markdown_content), end_pos + 3 + 1000)
        context_after = markdown_content[end_pos + 3:context_end].strip()
        
        code_blocks.append({
            'code': code_content,
            'language': language,
            'context_before': context_before,
            'context_after': context_after,
            'full_context': f"{context_before}\n\n{code_content}\n\n{context_after}"
        })
        
        # Move to next pair (skip the closing backtick we just processed)
        i += 2
    
    return code_blocks


def generate_code_example_summary(code: str, context_before: str, context_after: str) -> str:
    """
    Generate a summary for a code example using its surrounding context.
    
    Args:
        code: The code example
        context_before: Context before the code
        context_after: Context after the code
        
    Returns:
        A summary of what the code example demonstrates
    """
    model_choice = os.getenv("MODEL_CHOICE")
    
    # Create the prompt
    prompt = f"""<context_before>
{context_before[-500:] if len(context_before) > 500 else context_before}
</context_before>

<code_example>
{code[:1500] if len(code) > 1500 else code}
</code_example>

<context_after>
{context_after[:500] if len(context_after) > 500 else context_after}
</context_after>

Based on the code example and its surrounding context, provide a concise summary (2-3 sentences) that describes what this code example demonstrates and its purpose. Focus on the practical application and key concepts illustrated.
"""
    
    try:
        response = openai.chat.completions.create(
            model=model_choice,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that provides concise code example summaries."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=100
        )
        
        return response.choices[0].message.content.strip()
    
    except Exception as e:
        print(f"Error generating code example summary: {e}")
        return "Code example for demonstration purposes."


def add_code_examples_to_supabase(
    client: Client,
    urls: List[str],
    chunk_numbers: List[int],
    code_examples: List[str],
    summaries: List[str],
    metadatas: List[Dict[str, Any]],
    source_id: str = None,
    batch_size: int = 20
):
    """
    Add code examples to the Supabase code_examples table in batches.
    
    Args:
        client: Supabase client
        urls: List of URLs
        chunk_numbers: List of chunk numbers
        code_examples: List of code example contents
        summaries: List of code example summaries
        metadatas: List of metadata dictionaries
        source_id: Source ID for all code examples (optional, will extract from URL if not provided)
        batch_size: Size of each batch for insertion
    """
    if not urls:
        return
        
    # Delete existing records for these URLs
    unique_urls = list(set(urls))
    for url in unique_urls:
        try:
            client.table('code_examples').delete().eq('url', url).execute()
        except Exception as e:
            print(f"Error deleting existing code examples for {url}: {e}")
    
    # Process in batches
    total_items = len(urls)
    for i in range(0, total_items, batch_size):
        batch_end = min(i + batch_size, total_items)
        batch_texts = []
        
        # Create combined texts for embedding (code + summary)
        for j in range(i, batch_end):
            combined_text = f"{code_examples[j]}\n\nSummary: {summaries[j]}"
            batch_texts.append(combined_text)
        
        # Create embeddings for the batch
        embeddings = create_embeddings_batch(batch_texts)
        
        # Check if embeddings are valid (not all zeros)
        valid_embeddings = []
        for embedding in embeddings:
            if embedding and not all(v == 0.0 for v in embedding):
                valid_embeddings.append(embedding)
            else:
                print("Warning: Zero or invalid embedding detected, creating new one...")
                # Try to create a single embedding as fallback
                single_embedding = create_embedding(batch_texts[len(valid_embeddings)])
                valid_embeddings.append(single_embedding)
        
        # Prepare batch data
        batch_data = []
        for j, embedding in enumerate(valid_embeddings):
            idx = i + j
            
            # Use provided source_id or extract from URL
            if source_id:
                code_source_id = source_id
            else:
                parsed_url = urlparse(urls[idx])
                code_source_id = parsed_url.netloc or parsed_url.path
            
            batch_data.append({
                'url': urls[idx],
                'chunk_number': chunk_numbers[idx],
                'content': code_examples[idx],
                'summary': summaries[idx],
                'metadata': metadatas[idx],  # Store as JSON object, not string
                'source_id': code_source_id,
                'embedding': embedding
            })
        
        # Insert batch into Supabase with retry logic
        max_retries = 3
        retry_delay = 1.0  # Start with 1 second delay
        
        for retry in range(max_retries):
            try:
                client.table('code_examples').insert(batch_data).execute()
                # Success - break out of retry loop
                break
            except Exception as e:
                if retry < max_retries - 1:
                    print(f"Error inserting batch into Supabase (attempt {retry + 1}/{max_retries}): {e}")
                    print(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    # Final attempt failed
                    print(f"Failed to insert batch after {max_retries} attempts: {e}")
                    # Optionally, try inserting records one by one as a last resort
                    print("Attempting to insert records individually...")
                    successful_inserts = 0
                    for record in batch_data:
                        try:
                            client.table('code_examples').insert(record).execute()
                            successful_inserts += 1
                        except Exception as individual_error:
                            print(f"Failed to insert individual record for URL {record['url']}: {individual_error}")
                    
                    if successful_inserts > 0:
                        print(f"Successfully inserted {successful_inserts}/{len(batch_data)} records individually")
        print(f"Inserted batch {i//batch_size + 1} of {(total_items + batch_size - 1)//batch_size} code examples")


def update_source_info(client: Client, source_id: str, summary: str, word_count: int):
    """
    Update or insert source information in the sources table.
    
    Args:
        client: Supabase client
        source_id: The source ID (domain)
        summary: Summary of the source
        word_count: Total word count for the source
    """
    try:
        # Try to update existing source
        result = client.table('sources').update({
            'summary': summary,
            'total_word_count': word_count,
            'updated_at': 'now()'
        }).eq('source_id', source_id).execute()
        
        # If no rows were updated, insert new source
        if not result.data:
            client.table('sources').insert({
                'source_id': source_id,
                'summary': summary,
                'total_word_count': word_count
            }).execute()
            print(f"Created new source: {source_id}")
        else:
            print(f"Updated source: {source_id}")
            
    except Exception as e:
        print(f"Error updating source {source_id}: {e}")


def extract_source_summary(source_id: str, content: str, max_length: int = 500) -> str:
    """
    Extract a summary for a source from its content using an LLM.
    
    This function uses the OpenAI API to generate a concise summary of the source content.
    
    Args:
        source_id: The source ID (domain)
        content: The content to extract a summary from
        max_length: Maximum length of the summary
        
    Returns:
        A summary string
    """
    # Default summary if we can't extract anything meaningful
    default_summary = f"Content from {source_id}"
    
    if not content or len(content.strip()) == 0:
        return default_summary
    
    # Get the model choice from environment variables
    model_choice = os.getenv("MODEL_CHOICE")
    
    # Limit content length to avoid token limits
    truncated_content = content[:25000] if len(content) > 25000 else content
    
    # Create the prompt for generating the summary
    prompt = f"""<source_content>
{truncated_content}
</source_content>

The above content is from the documentation for '{source_id}'. Please provide a concise summary (3-5 sentences) that describes what this library/tool/framework is about. The summary should help understand what the library/tool/framework accomplishes and the purpose.
"""
    
    try:
        # Call the OpenAI API to generate the summary
        response = openai.chat.completions.create(
            model=model_choice,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that provides concise library/tool/framework summaries."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=150
        )
        
        # Extract the generated summary
        summary = response.choices[0].message.content.strip()
        
        # Ensure the summary is not too long
        if len(summary) > max_length:
            summary = summary[:max_length] + "..."
            
        return summary
    
    except Exception as e:
        print(f"Error generating summary with LLM for {source_id}: {e}. Using default summary.")
        return default_summary


def search_code_examples(
    client: Client, 
    query: str, 
    match_count: int = 10, 
    filter_metadata: Optional[Dict[str, Any]] = None,
    source_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Search for code examples in Supabase using vector similarity.
    
    Args:
        client: Supabase client
        query: Query text
        match_count: Maximum number of results to return
        filter_metadata: Optional metadata filter
        source_id: Optional source ID to filter results
        
    Returns:
        List of matching code examples
    """
    # Create a more descriptive query for better embedding match
    # Since code examples are embedded with their summaries, we should make the query more descriptive
    enhanced_query = f"Code example for {query}\n\nSummary: Example code showing {query}"
    
    # Create embedding for the enhanced query
    query_embedding = create_embedding(enhanced_query)
    
    # Execute the search using the match_code_examples function
    try:
        # Only include filter parameter if filter_metadata is provided and not empty
        params = {
            'query_embedding': query_embedding,
            'match_count': match_count
        }
        
        # Only add the filter if it's actually provided and not empty
        if filter_metadata:
            params['filter'] = filter_metadata
            
        # Add source filter if provided
        if source_id:
            params['source_filter'] = source_id
        
        result = client.rpc('match_code_examples', params).execute()
        
        return result.data
    except Exception as e:
        print(f"Error searching code examples: {e}")
        return []


# ==============================================================================
# TEXT PROCESSING FUNCTIONS
# ==============================================================================

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
        code_block = chunk.rfind('```')
        if code_block != -1 and code_block > chunk_size * 0.3:
            end = start + code_block

        # If no code block, try to break at a paragraph
        elif '\n\n' in chunk:
            # Find the last paragraph break
            last_break = chunk.rfind('\n\n')
            if last_break > chunk_size * 0.3:  # Only break if we're past 30% of chunk_size
                end = start + last_break

        # If no paragraph break, try to break at a sentence
        elif '. ' in chunk:
            # Find the last sentence break
            last_period = chunk.rfind('. ')
            if last_period > chunk_size * 0.3:  # Only break if we're past 30% of chunk_size
                end = start + last_period + 1

        # Extract chunk and clean it up
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        # Move start position for next chunk
        start = end

    return chunks


# ==============================================================================
# DOCUMENTATION PROCESSING FUNCTIONS
# ==============================================================================

def convert_notebook_to_markdown(notebook_path: Path) -> str:
    """
    Convert Jupyter notebook to markdown using only standard Python libraries.
    
    Args:
        notebook_path: Path to the .ipynb file
        
    Returns:
        Markdown content as string
        
    Raises:
        Exception: If notebook cannot be parsed or converted
    """
    
    with open(notebook_path, 'r', encoding='utf-8') as f:
        notebook = json.load(f)
    
    markdown_parts = []
    
    # Add notebook title if available
    if 'metadata' in notebook and 'kernelspec' in notebook['metadata']:
        kernel_name = notebook['metadata']['kernelspec'].get('display_name', 'Notebook')
        markdown_parts.append(f"# {kernel_name}\n")
    
    # Process each cell
    for cell in notebook.get('cells', []):
        cell_type = cell.get('cell_type', '')
        source = cell.get('source', [])
        
        # Join source lines into content
        if isinstance(source, list):
            content = ''.join(source)
        else:
            content = str(source)
        
        if cell_type == 'markdown':
            # Add markdown cell content directly
            markdown_parts.append(content)
            
        elif cell_type == 'code':
            # Add code cell as markdown code block
            if content.strip():
                language = _detect_code_language(notebook)
                markdown_parts.append(f"```{language}\n{content}\n```")
                
                # Optionally include outputs
                outputs = cell.get('outputs', [])
                if outputs:
                    for output in outputs:
                        if output.get('output_type') == 'stream':
                            # Add stream output
                            stream_text = ''.join(output.get('text', []))
                            if stream_text.strip():
                                markdown_parts.append(f"```\n{stream_text}\n```")
                        elif output.get('output_type') in ['execute_result', 'display_data']:
                            # Add text representation of output
                            data = output.get('data', {})
                            if 'text/plain' in data:
                                text_output = ''.join(data['text/plain'])
                                if text_output.strip():
                                    markdown_parts.append(f"```\n{text_output}\n```")
        
        # Add spacing between cells
        markdown_parts.append("\n")
    
    return '\n'.join(markdown_parts)


def _detect_code_language(notebook: dict) -> str:
    """
    Detect the programming language from notebook metadata.
    
    Args:
        notebook: Parsed notebook JSON
        
    Returns:
        Language identifier for code blocks
    """
    if 'metadata' in notebook and 'kernelspec' in notebook['metadata']:
        # First try the explicit language field
        language = notebook['metadata']['kernelspec'].get('language', '')
        if language:
            return language.lower()
        
        # Fall back to kernel name with simple processing
        kernel_name = notebook['metadata']['kernelspec'].get('name', '').lower()
        if kernel_name:
            # Handle special case for R
            if kernel_name == 'ir':
                return 'r'
            
            # Remove version numbers (python3 -> python, python2 -> python)
            clean_name = re.sub(r'\d+$', '', kernel_name)
            return clean_name if clean_name else kernel_name
    
    return 'python'  # Default to Python

def discover_documentation_files(repo_path: Path) -> List[Path]:
    """
    Discover documentation files with practical filtering.
    
    Includes extensions: .md, .rst, .txt, .mdx, .ipynb
    Excludes directories: tests, __pycache__, .git, venv, node_modules, build, dist, examples
    Size limit: Skip files larger than 500KB
    
    Args:
        repo_path: Path to the repository root
        
    Returns:
        List of Path objects for documentation files
    """
    doc_extensions = {'.md', '.mdx', '.rst', '.ipynb', '.txt'}
    exclude_dirs = {
        'tests', 'test', '__pycache__', '.git', 'venv', 'env',
        'node_modules', 'build', 'dist', '.pytest_cache',
        'examples', 'example', 'demo', 'benchmark', '.tox',
        'htmlcov', 'coverage', '.coverage', '.mypy_cache'
    }
    
    doc_files = []
    max_file_size = 500 * 1024  # 500KB limit
    
    try:
        for root, dirs, files in os.walk(repo_path):
            # Filter out excluded directories
            dirs[:] = [d for d in dirs if d not in exclude_dirs and not d.startswith('.')]
            
            for file in files:
                file_path = Path(root) / file
                
                # Check extension
                if file_path.suffix.lower() in doc_extensions:
                    try:
                        # Check file size
                        if file_path.stat().st_size <= max_file_size:
                            doc_files.append(file_path)
                        else:
                            print(
                                f"Skipping large file {file_path.relative_to(repo_path)} "
                                f"({file_path.stat().st_size} bytes > {max_file_size} bytes limit)"
                            )
                    except Exception as e:
                        print(f"Error checking file {file_path}: {e}")
                        continue
    
    except Exception as e:
        print(f"Error discovering documentation files: {e}")
        return []
    
    return doc_files


def process_document_files(doc_files: List[Path], repo_path: Path) -> List[Dict[str, str]]:
    """
    Process documentation files with notebook support.
    
    - Jupyter notebooks: Convert to markdown using built-in JSON parsing
    - Regular files: Read as UTF-8 text
    - Return list of {"url": relative_path, "markdown": content}
    
    Args:
        doc_files: List of documentation file paths
        repo_path: Repository root path
        
    Returns:
        List of dictionaries with url and markdown content
    """
    docs_content = []
    
    for doc_file in doc_files:
        try:
            relative_path = str(doc_file.relative_to(repo_path))
            
            if doc_file.suffix == '.ipynb':
                # Process Jupyter notebook
                try:
                    markdown_content = convert_notebook_to_markdown(doc_file)
                except Exception as e:
                    print(f"Error converting notebook {relative_path}: {e}")
                    continue
            else:
                # Process regular text file
                try:
                    with open(doc_file, 'r', encoding='utf-8') as f:
                        markdown_content = f.read()
                except UnicodeDecodeError:
                    # Try with different encoding
                    try:
                        with open(doc_file, 'r', encoding='latin-1') as f:
                            markdown_content = f.read()
                    except Exception as e:
                        print(f"Error reading file {relative_path} with latin-1 encoding: {e}")
                        continue
                except Exception as e:
                    print(f"Error reading file {relative_path}: {e}")
                    continue
            
            # Only add if we got meaningful content
            if markdown_content.strip():
                docs_content.append({
                    "url": relative_path,
                    "markdown": markdown_content
                })
            
        except Exception as e:
            print(f"Skipping file {doc_file} due to processing error: {e}")
            continue
    
    return docs_content


def create_repository_source_id(repo_url: str) -> str:
    """
    Create repository-level source ID for documentation.
    
    Normalizes both SSH and HTTPS URLs to a consistent format.
    
    Examples:
    - https://github.com/user/repo.git -> github.com/user/repo
    - git@github.com:user/repo.git -> github.com/user/repo
    
    Args:
        repo_url: Repository URL (SSH or HTTPS format)
        
    Returns:
        Repository source ID string in format: domain/user/repo
    """
    try:
        # Handle SSH URLs (git@github.com:user/repo.git)
        if repo_url.startswith('git@'):
            # Extract the part after 'git@' and before ':'
            ssh_parts = repo_url.split('@', 1)[1]  # Remove 'git@'
            if ':' in ssh_parts:
                domain, path = ssh_parts.split(':', 1)
                # Remove .git suffix if present
                path = path.rstrip('.git')
                return f"{domain}/{path}"
        
        # Handle HTTPS/HTTP URLs
        parsed_url = urlparse(repo_url)
        if parsed_url.netloc and parsed_url.path:
            # Remove .git suffix and leading slash if present
            path = parsed_url.path.lstrip('/').rstrip('.git')
            return f"{parsed_url.netloc}/{path}"
            
    except Exception as e:
        print(f"Error creating source ID: {e}")
    
    # Fallback to simple string manipulation
    fallback = repo_url.replace('.git', '').replace('https://', '').replace('http://', '')
    if fallback.startswith('git@'):
        fallback = fallback.replace('git@', '').replace(':', '/')
    return fallback


def create_documentation_url(repo_url: str, doc_path: str) -> str:
    """
    Create URL for individual documentation files (for chunk identification).
    
    Examples:
    - github.com/user/repo/docs/api.md
    - github.com/user/repo/README.md
    
    Args:
        repo_url: Repository URL
        doc_path: Relative path to documentation file
        
    Returns:
        Documentation file URL string
    """
    try:
        parsed_url = urlparse(repo_url)
        # Remove .git suffix if present
        path = parsed_url.path.rstrip('.git')
        return f"{parsed_url.netloc}{path}/{doc_path}"
    except Exception as e:
        print(f"Error creating documentation URL: {e}")
        # Fallback to simple concatenation
        return f"{repo_url.replace('.git', '')}/{doc_path}"


def construct_doc_url(repo_source_id: str, doc_path: str) -> str:
    """
    Construct URL for documentation files using repository source ID.
    
    Args:
        repo_source_id: Repository source ID (e.g., "github.com/user/repo")
        doc_path: Relative path to documentation file
        
    Returns:
        Constructed URL string
    """
    return urljoin(repo_source_id.rstrip('/') + '/', doc_path.lstrip('/'))


def create_documentation_metadata(
    doc_file_info: Dict[str, str], 
    repo_info: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Create enhanced metadata for documentation.
    
    Args:
        doc_file_info: Dictionary with 'url' and 'markdown' keys
        repo_info: Repository information (name, url, etc.)
        
    Returns:
        Enhanced metadata dictionary
    """
    doc_path = doc_file_info["url"]
    content = doc_file_info["markdown"]
    
    # Determine documentation category
    doc_category = "documentation"
    filename = Path(doc_path).name.lower()
    
    if filename in ["readme.md", "readme.rst", "readme.txt"]:
        doc_category = "readme"
    elif "api" in filename or "reference" in filename:
        doc_category = "api"
    elif "tutorial" in filename or "guide" in filename or "getting" in filename:
        doc_category = "tutorial"
    elif "changelog" in filename or "history" in filename or "news" in filename:
        doc_category = "changelog"
    elif "license" in filename:
        doc_category = "license"
    elif "contrib" in filename or "develop" in filename:
        doc_category = "contributing"
    
    # Count code blocks if agentic RAG is enabled
    code_example_count = 0
    if os.getenv("USE_AGENTIC_RAG", "false") == "true":
        code_example_count = len(extract_code_blocks(content, min_length=200))
    
    return {
        "repository_name": repo_info.get("name", "unknown"),
        "repository_url": repo_info.get("url", ""),
        "file_type": Path(doc_path).suffix[1:] if Path(doc_path).suffix else "txt",
        "file_path": doc_path,
        "documentation_category": doc_category,
        "content_length": len(content),
        "code_example_count": code_example_count,
        "processed_at": time.time()
    }


async def process_repository_docs(
    supabase_client: Client,
    repo_path: Path, 
    repo_name: str,
    repo_url: str = ""
) -> Dict[str, Any]:
    """
    Main entry point for documentation processing.
    
    Args:
        supabase_client: Supabase client for storage
        repo_path: Path to cloned repository
        repo_name: Repository name
        repo_url: Repository URL (optional)
        
    Returns:
        Dictionary with processing results:
        {"files_processed": int, "chunks_created": int, "code_examples_extracted": int}
    """
    print(f"Starting documentation processing for repository: {repo_name}")
    
    try:
        # Step 1: Discover documentation files
        print("Discovering documentation files...")
        doc_files = discover_documentation_files(repo_path)
        print(f"Found {len(doc_files)} documentation files")
        
        if not doc_files:
            return {
                "files_processed": 0,
                "chunks_created": 0,
                "code_examples_extracted": 0,
                "message": "No documentation files found"
            }
        
        # Step 2: Process documentation files
        print("Processing documentation content...")
        docs_content = process_document_files(doc_files, repo_path)
        print(f"Successfully processed {len(docs_content)} files")
        
        if not docs_content:
            return {
                "files_processed": 0,
                "chunks_created": 0,
                "code_examples_extracted": 0,
                "message": "No valid documentation content found"
            }
        
        # Step 3: Prepare data for Supabase
        print("Preparing content for Supabase storage...")
        all_urls = []
        all_chunk_numbers = []
        all_contents = []
        all_metadatas = []
        url_to_full_document = {}
        total_code_examples = 0
        
        # Create single repository source ID
        repo_source_id = create_repository_source_id(repo_url)
        
        repo_info = {
            "name": repo_name,
            "url": repo_url
        }
        
        # Collect all content for repository-level summary
        all_repo_content = []
        
        for doc_info in docs_content:
            doc_path = doc_info["url"]
            content = doc_info["markdown"]
            
            # Create individual documentation URL for chunk identification
            doc_url = create_documentation_url(repo_url, doc_path)
            
            # Create metadata
            metadata = create_documentation_metadata(doc_info, repo_info)
            total_code_examples += metadata["code_example_count"]
            
            # Chunk the content
            chunks = smart_chunk_markdown(content)
            
            # Store full document for contextual embeddings (using doc URL)
            url_to_full_document[doc_url] = content
            
            # Collect content for repository summary
            all_repo_content.append(content)
            
            # Add chunked data - ALL chunks use the same repository source ID
            for i, chunk in enumerate(chunks):
                all_urls.append(doc_url)  # Individual doc URL for chunk identification
                all_chunk_numbers.append(i)
                all_contents.append(chunk)
                # Add source_id to metadata for foreign key reference
                metadata_with_source = metadata.copy()
                metadata_with_source["source_id"] = repo_source_id
                all_metadatas.append(metadata_with_source)
        
        # Step 4: Create single repository source record
        print(f"Creating repository source record: {repo_source_id}")
        
        # Combine all documentation content for repository-level summary
        combined_content = "\n\n".join(all_repo_content)
        
        # Extract repository-level summary and word count
        repo_summary = extract_source_summary(repo_source_id, combined_content[:5000])  # Use first 5000 chars
        repo_word_count = len(combined_content.split())
        
        # Create/update single source record for the entire repository
        update_source_info(supabase_client, repo_source_id, repo_summary, repo_word_count)
        
        # Step 5: Store document chunks in Supabase
        print(f"Storing {len(all_contents)} chunks in Supabase...")
        add_documents_to_supabase(
            supabase_client, 
            all_urls, 
            all_chunk_numbers,
            all_contents, 
            all_metadatas,
            url_to_full_document
        )
        
        # Step 6: Process code examples if enabled
        if os.getenv("USE_AGENTIC_RAG", "false") == "true" and total_code_examples > 0:
            print("Processing code examples...")
            try:
                # Extract and store code examples - all using the same repository source ID
                for doc_info in docs_content:
                    content = doc_info["markdown"]
                    
                    code_blocks = extract_code_blocks(content)
                    if code_blocks:
                        summaries = []
                        for block in code_blocks:
                            summary = generate_code_example_summary(
                                block['code'], 
                                block['context_before'], 
                                block['context_after']
                            )
                            summaries.append(summary)
                        
                        # Use the repository source ID for all code examples
                        codes_only = [block['code'] for block in code_blocks]
                        urls = [construct_doc_url(repo_source_id, doc_info['url']) for _ in code_blocks]
                        chunk_numbers = list(range(len(code_blocks)))
                        metadatas = [
                            {
                                "file_path": doc_info['url'],
                                "file_type": doc_info['url'].split('.')[-1] if '.' in doc_info['url'] else 'unknown',
                                "language": block.get('language', ''),
                                "char_count": len(block['code']),
                                "word_count": len(block['code'].split()),
                                "chunk_index": i,
                                "repository_url": repo_url,
                                "repository_name": repo_name,
                                "documentation_category": "code_example"
                            }
                            for i, block in enumerate(code_blocks)
                        ]
                        add_code_examples_to_supabase(supabase_client, urls, chunk_numbers, codes_only, summaries, metadatas, repo_source_id)
                        
            except Exception as e:
                print(f"Error processing code examples: {e}")
                # Continue without failing the entire process
        
        print(f"Documentation processing completed for {repo_name}")
        
        return {
            "files_processed": len(docs_content),
            "chunks_created": len(all_contents),
            "code_examples_extracted": total_code_examples,
            "message": f"Successfully processed {len(docs_content)} documentation files"
        }
        
    except Exception as e:
        print(f"Error processing repository documentation: {e}")
        return {
            "files_processed": 0,
            "chunks_created": 0,
            "code_examples_extracted": 0,
            "error": str(e)
        }