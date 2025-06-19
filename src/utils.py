"""
Utility functions for the Crawl4AI MCP server.
"""
import os
import concurrent.futures
from typing import List, Dict, Any, Optional, Tuple
import json
from supabase import create_client, Client
from urllib.parse import urlparse
import openai
import re
import time

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
    rate_limit_count = 0
    for retry in range(max_retries):
        try:
            print(f"[Embedding] Batch request, attempt {retry+1}/{max_retries}")
            response = openai.embeddings.create(
                model="text-embedding-3-small",
                input=texts
            )
            print("[Embedding] Batch request successful.")
            return [item.embedding for item in response.data]
        except Exception as e:
            error_str = str(e)
            is_rate_limit = False
            wait_time = retry_delay
            if '429' in error_str or 'rate limit' in error_str.lower():
                rate_limit_count += 1
                is_rate_limit = True
                import re
                match = re.search(r'Please try again in (\d+)ms', error_str)
                if match:
                    wait_time = int(match.group(1)) / 1000.0
                else:
                    wait_time = retry_delay
                wait_time = min(wait_time, 10)  # 최대 10초까지만 대기
                print(f"[Embedding] Rate limit hit. Waiting {wait_time} seconds before retry... (rate_limit_count={rate_limit_count})")
                time.sleep(wait_time)
                retry_delay *= 2
                if rate_limit_count >= 3:
                    print("[Embedding] Too many rate limits. Aborting batch embedding.")
                    break
            elif retry < max_retries - 1:
                print(f"[Embedding] Error creating batch embeddings (attempt {retry + 1}/{max_retries}): {e}")
                print(f"[Embedding] Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
                retry_delay *= 2
            else:
                print(f"[Embedding] Failed to create batch embeddings after {max_retries} attempts: {e}")
                print("[Embedding] Attempting to create embeddings individually...")
                embeddings = []
                successful_count = 0
                for i, text in enumerate(texts):
                    single_rate_limit_count = 0
                    for single_retry in range(max_retries):
                        try:
                            print(f"[Embedding] Single request for text {i}, attempt {single_retry+1}/{max_retries}")
                            individual_response = openai.embeddings.create(
                                model="text-embedding-3-small",
                                input=[text]
                            )
                            embeddings.append(individual_response.data[0].embedding)
                            successful_count += 1
                            print(f"[Embedding] Single request for text {i} successful.")
                            break
                        except Exception as individual_error:
                            error_str2 = str(individual_error)
                            if '429' in error_str2 or 'rate limit' in error_str2.lower():
                                single_rate_limit_count += 1
                                match2 = re.search(r'Please try again in (\d+)ms', error_str2)
                                wait_time2 = int(match2.group(1)) / 1000.0 if match2 else retry_delay
                                wait_time2 = min(wait_time2, 10)
                                print(f"[Embedding] Rate limit hit (single). Waiting {wait_time2} seconds before retry... (single_rate_limit_count={single_rate_limit_count})")
                                time.sleep(wait_time2)
                                if single_rate_limit_count >= 3:
                                    print(f"[Embedding] Too many rate limits for text {i}. Skipping.")
                                    embeddings.append([0.0] * 1536)
                                    break
                            elif single_retry < max_retries - 1:
                                print(f"[Embedding] Failed to create embedding for text {i} (attempt {single_retry + 1}/{max_retries}): {individual_error}")
                                print(f"[Embedding] Retrying in {retry_delay} seconds...")
                                time.sleep(retry_delay)
                            else:
                                print(f"[Embedding] Failed to create embedding for text {i}: {individual_error}")
                                embeddings.append([0.0] * 1536)
                print(f"[Embedding] Successfully created {successful_count}/{len(texts)} embeddings individually")
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
    max_retries = 3
    retry_delay = 1.0
    rate_limit_count = 0
    for retry in range(max_retries):
        try:
            print(f"[Contextual Embedding] Request, attempt {retry+1}/{max_retries}")
            prompt = f"""<document> \n{full_document[:25000]} \n</document>\nHere is the chunk we want to situate within the whole document \n<chunk> \n{chunk}\n</chunk> \nPlease give a short succinct context to situate this chunk within the overall document for the purposes of improving search retrieval of the chunk. Answer only with the succinct context and nothing else."""
            response = openai.chat.completions.create(
                model=model_choice,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that provides concise contextual information."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=200
            )
            context = response.choices[0].message.content.strip()
            contextual_text = f"{context}\n---\n{chunk}"
            print("[Contextual Embedding] Success.")
            return contextual_text, True
        except Exception as e:
            error_str = str(e)
            is_rate_limit = False
            wait_time = retry_delay
            if '429' in error_str or 'rate limit' in error_str.lower():
                rate_limit_count += 1
                is_rate_limit = True
                import re
                match = re.search(r'Please try again in (\d+)ms', error_str)
                if match:
                    wait_time = int(match.group(1)) / 1000.0
                else:
                    wait_time = retry_delay
                wait_time = min(wait_time, 10)
                print(f"[Contextual Embedding] Rate limit hit. Waiting {wait_time} seconds before retry... (rate_limit_count={rate_limit_count})")
                time.sleep(wait_time)
                retry_delay *= 2
                if rate_limit_count >= 3:
                    print("[Contextual Embedding] Too many rate limits. Aborting contextual embedding.")
                    break
            elif retry < max_retries - 1:
                print(f"[Contextual Embedding] Error (attempt {retry + 1}/{max_retries}): {e}")
                print(f"[Contextual Embedding] Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
                retry_delay *= 2
            else:
                print(f"[Contextual Embedding] Error: {e}. Using original chunk instead.")
                return chunk, False
    print("[Contextual Embedding] Failed. Using original chunk.")
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
            
            # Extract source_id from URL
            parsed_url = urlparse(batch_urls[j])
            source_id = parsed_url.netloc or parsed_url.path
            
            # Prepare data for insertion
            data = {
                "url": batch_urls[j],
                "chunk_number": batch_chunk_numbers[j],
                "content": contextual_contents[j],  # Store original content
                "metadata": {
                    "chunk_size": chunk_size,
                    **batch_metadatas[j]
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
            if first_line and not ' ' in first_line and len(first_line) < 20:
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
    prompt = f"""<context_before>\n{context_before[-500:] if len(context_before) > 500 else context_before}\n</context_before>\n\n<code_example>\n{code[:1500] if len(code) > 1500 else code}\n</code_example>\n\n<context_after>\n{context_after[:500] if len(context_after) > 500 else context_after}\n</context_after>\n\nBased on the code example and its surrounding context, provide a concise summary (2-3 sentences) that describes what this code example demonstrates and its purpose. Focus on the practical application and key concepts illustrated.\n"""
    max_retries = 3
    retry_delay = 1.0
    rate_limit_count = 0
    for retry in range(max_retries):
        try:
            print(f"[Code Example Summary] Request, attempt {retry+1}/{max_retries}")
            response = openai.chat.completions.create(
                model=model_choice,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that provides concise code example summaries."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=100
            )
            print("[Code Example Summary] Success.")
            return response.choices[0].message.content.strip()
        except Exception as e:
            error_str = str(e)
            is_rate_limit = False
            wait_time = retry_delay
            if '429' in error_str or 'rate limit' in error_str.lower():
                rate_limit_count += 1
                is_rate_limit = True
                import re
                match = re.search(r'Please try again in (\d+)ms', error_str)
                if match:
                    wait_time = int(match.group(1)) / 1000.0
                else:
                    wait_time = retry_delay
                wait_time = min(wait_time, 10)
                print(f"[Code Example Summary] Rate limit hit. Waiting {wait_time} seconds before retry... (rate_limit_count={rate_limit_count})")
                time.sleep(wait_time)
                retry_delay *= 2
                if rate_limit_count >= 3:
                    print("[Code Example Summary] Too many rate limits. Aborting code example summary.")
                    break
            elif retry < max_retries - 1:
                print(f"[Code Example Summary] Error (attempt {retry + 1}/{max_retries}): {e}")
                print(f"[Code Example Summary] Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
                retry_delay *= 2
            else:
                print(f"[Code Example Summary] Error: {e}")
                return "Code example for demonstration purposes."
    print("[Code Example Summary] Failed. Returning default summary.")
    return "Code example for demonstration purposes."


def add_code_examples_to_supabase(
    client: Client,
    urls: List[str],
    chunk_numbers: List[int],
    code_examples: List[str],
    summaries: List[str],
    metadatas: List[Dict[str, Any]],
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
                print(f"Warning: Zero or invalid embedding detected, creating new one...")
                # Try to create a single embedding as fallback
                single_embedding = create_embedding(batch_texts[len(valid_embeddings)])
                valid_embeddings.append(single_embedding)
        
        # Prepare batch data
        batch_data = []
        for j, embedding in enumerate(valid_embeddings):
            idx = i + j
            
            # Extract source_id from URL
            parsed_url = urlparse(urls[idx])
            source_id = parsed_url.netloc or parsed_url.path
            
            batch_data.append({
                'url': urls[idx],
                'chunk_number': chunk_numbers[idx],
                'content': code_examples[idx],
                'summary': summaries[idx],
                'metadata': metadatas[idx],  # Store as JSON object, not string
                'source_id': source_id,
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
    default_summary = f"Content from {source_id}"
    if not content or len(content.strip()) == 0:
        return default_summary
    model_choice = os.getenv("MODEL_CHOICE")
    truncated_content = content[:25000] if len(content) > 25000 else content
    prompt = f"""<source_content>\n{truncated_content}\n</source_content>\n\nThe above content is from the documentation for '{source_id}'. Please provide a concise summary (3-5 sentences) that describes what this library/tool/framework is about. The summary should help understand what the library/tool/framework accomplishes and the purpose.\n"""
    max_retries = 3
    retry_delay = 1.0
    rate_limit_count = 0
    for retry in range(max_retries):
        try:
            print(f"[Source Summary] Request, attempt {retry+1}/{max_retries}")
            response = openai.chat.completions.create(
                model=model_choice,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that provides concise library/tool/framework summaries."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=150
            )
            summary = response.choices[0].message.content.strip()
            if len(summary) > max_length:
                summary = summary[:max_length] + "..."
            print("[Source Summary] Success.")
            return summary
        except Exception as e:
            error_str = str(e)
            is_rate_limit = False
            wait_time = retry_delay
            if '429' in error_str or 'rate limit' in error_str.lower():
                rate_limit_count += 1
                is_rate_limit = True
                import re
                match = re.search(r'Please try again in (\d+)ms', error_str)
                if match:
                    wait_time = int(match.group(1)) / 1000.0
                else:
                    wait_time = retry_delay
                wait_time = min(wait_time, 10)
                print(f"[Source Summary] Rate limit hit. Waiting {wait_time} seconds before retry... (rate_limit_count={rate_limit_count})")
                time.sleep(wait_time)
                retry_delay *= 2
                if rate_limit_count >= 3:
                    print(f"[Source Summary] Too many rate limits. Aborting source summary for {source_id}.")
                    break
            elif retry < max_retries - 1:
                print(f"[Source Summary] Error (attempt {retry + 1}/{max_retries}): {e}")
                print(f"[Source Summary] Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
                retry_delay *= 2
            else:
                print(f"[Source Summary] Error generating summary with LLM for {source_id}: {e}. Using default summary.")
                return default_summary
    print(f"[Source Summary] Failed for {source_id}. Using default summary.")
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