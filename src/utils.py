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
import asyncio
import threading
import random
from functools import wraps
from datetime import datetime, timedelta

# Global client cache and rate limiting
_client_cache = {}
_client_cache_lock = threading.Lock()
_request_semaphore = None
_last_request_time = {}
_consecutive_errors = {}
_circuit_breaker_until = {}

# Configuration
MAX_CONCURRENT_REQUESTS = int(os.getenv("MAX_CONCURRENT_REQUESTS", "5"))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))
RATE_LIMIT_DELAY = float(os.getenv("RATE_LIMIT_DELAY", "0.5"))
CIRCUIT_BREAKER_THRESHOLD = int(os.getenv("CIRCUIT_BREAKER_THRESHOLD", "3"))
CLIENT_CACHE_TTL = int(os.getenv("CLIENT_CACHE_TTL", "3600"))  # 1 hour
SUPABASE_BATCH_SIZE = int(os.getenv("SUPABASE_BATCH_SIZE", "20"))
SUPABASE_MAX_RETRIES = int(os.getenv("SUPABASE_MAX_RETRIES", "3"))

def get_global_semaphore():
    """Get or create global request semaphore."""
    global _request_semaphore
    if _request_semaphore is None:
        _request_semaphore = threading.Semaphore(MAX_CONCURRENT_REQUESTS)
    return _request_semaphore

def rate_limit_delay(endpoint_key: str):
    """Implement rate limiting with minimum delay between requests."""
    global _last_request_time
    
    current_time = time.time()
    last_time = _last_request_time.get(endpoint_key, 0)
    
    time_diff = current_time - last_time
    if time_diff < RATE_LIMIT_DELAY:
        delay = RATE_LIMIT_DELAY - time_diff
        print(f"⏱️  Rate limiting: sleeping {delay:.2f}s for {endpoint_key}")
        time.sleep(delay)
    
    _last_request_time[endpoint_key] = time.time()

def is_circuit_breaker_open(endpoint_key: str) -> bool:
    """Check if circuit breaker is open for given endpoint."""
    global _circuit_breaker_until
    
    if endpoint_key in _circuit_breaker_until:
        if datetime.now() < _circuit_breaker_until[endpoint_key]:
            return True
        else:
            # Circuit breaker timeout expired, reset
            del _circuit_breaker_until[endpoint_key]
            _consecutive_errors[endpoint_key] = 0
    
    return False

def record_error(endpoint_key: str, error: Exception):
    """Record error and potentially trigger circuit breaker."""
    global _consecutive_errors, _circuit_breaker_until
    
    if is_retryable_error(error):
        _consecutive_errors[endpoint_key] = _consecutive_errors.get(endpoint_key, 0) + 1
        
        if _consecutive_errors[endpoint_key] >= CIRCUIT_BREAKER_THRESHOLD:
            # Open circuit breaker for 5 minutes
            _circuit_breaker_until[endpoint_key] = datetime.now() + timedelta(minutes=5)
            print(f"🚨 Circuit breaker opened for {endpoint_key} after {_consecutive_errors[endpoint_key]} consecutive errors")

def record_success(endpoint_key: str):
    """Record successful request and reset error counter."""
    global _consecutive_errors
    _consecutive_errors[endpoint_key] = 0

def get_cached_client(client_key: str, create_func) -> any:
    """Get or create cached client with TTL."""
    global _client_cache
    
    with _client_cache_lock:
        current_time = time.time()
        
        # Check if we have a valid cached client
        if client_key in _client_cache:
            client_data = _client_cache[client_key]
            if current_time - client_data['created_at'] < CLIENT_CACHE_TTL:
                print(f"♻️  Using cached client for {client_key}")
                return client_data['client']
            else:
                print(f"⏰ Cache expired for {client_key}, creating new client")
                del _client_cache[client_key]
        
        # Create new client
        print(f"🔧 Creating new client for {client_key}")
        client = create_func()
        _client_cache[client_key] = {
            'client': client,
            'created_at': current_time
        }
        
        return client

def get_chat_client_with_fallback() -> Tuple[openai.OpenAI, str, bool]:
    """
    Get a chat client with automatic fallback support using cached clients.
    
    Uses singleton pattern with TTL cache to reuse OpenAI client instances
    and reduce connection overhead that causes 503 errors.
    
    Returns:
        Tuple containing:
        - OpenAI client instance (cached)
        - Model name being used
        - Boolean indicating if fallback was used (True = fallback, False = primary)
    """
    # Primary model configuration
    primary_model = os.getenv("CHAT_MODEL")
    primary_api_base = os.getenv("CHAT_MODEL_API_BASE")
    primary_api_key = os.getenv("CHAT_MODEL_API_KEY")
    
    # Fallback model configuration
    fallback_model = os.getenv("CHAT_MODEL_FALLBACK")
    fallback_api_base = os.getenv("CHAT_MODEL_FALLBACK_API_BASE")
    fallback_api_key = os.getenv("CHAT_MODEL_FALLBACK_API_KEY")
    
    # Validate primary configuration
    if not primary_model or not primary_api_key:
        raise ValueError("CHAT_MODEL and CHAT_MODEL_API_KEY must be set")
    
    # Try primary model first (with caching)
    primary_key = f"chat_primary_{primary_model}_{primary_api_base or 'default'}"
    
    def create_primary_client():
        print(f"Attempting to use primary chat model: {primary_model}")
        client_args = {"api_key": primary_api_key, "timeout": REQUEST_TIMEOUT}
        if primary_api_base:
            client_args["base_url"] = primary_api_base
        return openai.OpenAI(**client_args)
    
    try:
        client = get_cached_client(primary_key, create_primary_client)
        print(f"✅ Primary chat model {primary_model} client ready")
        return client, primary_model, False
        
    except Exception as e:
        print(f"❌ Primary chat model client creation failed: {e}")
        record_error(primary_key, e)
    
    # Primary model failed, try fallback
    if fallback_model and fallback_api_key:
        fallback_key = f"chat_fallback_{fallback_model}_{fallback_api_base or 'default'}"
        
        def create_fallback_client():
            print(f"🔄 Attempting fallback to: {fallback_model}")
            client_args = {"api_key": fallback_api_key, "timeout": REQUEST_TIMEOUT}
            if fallback_api_base:
                client_args["base_url"] = fallback_api_base
            return openai.OpenAI(**client_args)
        
        try:
            client = get_cached_client(fallback_key, create_fallback_client)
            print(f"✅ Fallback chat model {fallback_model} client ready")
            return client, fallback_model, True
            
        except Exception as e:
            print(f"❌ Fallback chat model client creation failed: {e}")
            record_error(fallback_key, e)
    else:
        print("⚠️  No fallback chat model configured")
    
    # Both primary and fallback failed
    raise Exception(f"Both primary ({primary_model}) and fallback ({fallback_model}) chat models failed")


def is_retryable_error(error: Exception) -> bool:
    """
    Determine if an error is retryable (temporary) or should trigger fallback.
    
    Args:
        error: Exception that occurred during API call
        
    Returns:
        True if error is retryable, False if should trigger fallback
    """
    error_str = str(error).lower()
    
    # HTTP status codes that indicate temporary server issues
    retryable_codes = ['503', '429', '500', '502', '504']
    retryable_messages = [
        'service unavailable',
        'rate limit',
        'timeout',
        'connection error',
        'no available server',
        'server error'
    ]
    
    # Check for specific HTTP status codes
    for code in retryable_codes:
        if code in error_str:
            return True
    
    # Check for specific error messages
    for message in retryable_messages:
        if message in error_str:
            return True
    
    return False


def make_chat_completion_with_fallback(messages: list, **kwargs) -> any:
    """
    Make a chat completion with automatic fallback, rate limiting, and circuit breaker.
    
    This function implements a robust system that:
    1. Uses cached clients to reduce connection overhead
    2. Implements rate limiting to prevent API overload
    3. Circuit breaker to avoid repeated failures
    4. Exponential backoff with jitter for retries
    5. Seamless fallback on API failures
    
    Args:
        messages: List of message dictionaries for chat completion
        **kwargs: Additional arguments to pass to chat completion (temperature, max_tokens, etc.)
        
    Returns:
        OpenAI chat completion response
        
    Raises:
        Exception: If both primary and fallback models fail completely
    """
    import time
    import random
    from openai import OpenAI
    # Get semaphore for concurrency control
    semaphore = get_global_semaphore()
    
    # Configuration  
    use_fallback = os.getenv("USE_CHAT_MODEL_FALLBACK", "false").lower() == "true"
    max_retries = 3
    base_delay = 1.0
    max_delay = 15.0
    primary_error = None
    
    # Primary model configuration
    primary_model = os.getenv("CHAT_MODEL")
    primary_api_base = os.getenv("CHAT_MODEL_API_BASE")
    primary_key = f"chat_primary_{primary_model}_{primary_api_base or 'default'}"
    
    # Check circuit breaker for primary
    if is_circuit_breaker_open(primary_key):
        print(f"🚨 Circuit breaker open for primary model {primary_model}, forcing fallback")
        primary_error = Exception("Circuit breaker open")
    else:
        # Try primary model with rate limiting
        with semaphore:
            try:
                rate_limit_delay(primary_key)
                client, model_name, is_fallback = get_chat_client_with_fallback()
                
                if not is_fallback:
                    # Attempt primary model with improved retry logic
                    for attempt in range(max_retries):
                        try:
                            response = client.chat.completions.create(
                                model=model_name,
                                messages=messages,
                                **kwargs
                            )
                            record_success(primary_key)
                            if attempt > 0:
                                print(f"✅ Primary model {model_name} succeeded on attempt {attempt + 1}")
                            return response
                            
                        except Exception as e:
                            if is_retryable_error(e) and attempt < max_retries - 1:
                                # Exponential backoff with jitter
                                jitter = random.uniform(0.5, 1.5)
                                delay = min(base_delay * (2 ** attempt) * jitter, max_delay)
                                print(f"⚠️  Primary model {model_name} failed (attempt {attempt + 1}/{max_retries}): {e}")
                                print(f"🔄 Retrying in {delay:.1f}s...")
                                time.sleep(delay)
                                continue
                            else:
                                print(f"❌ Primary model {model_name} failed definitively: {e}")
                                record_error(primary_key, e)
                                primary_error = e
                                break
                                
            except Exception as e:
                print(f"❌ Primary model client failed: {e}")
                record_error(primary_key, e)
                primary_error = e
    
    # Try fallback if enabled and primary failed
    if use_fallback and primary_error:
        fallback_model = os.getenv("CHAT_MODEL_FALLBACK")
        fallback_api_base = os.getenv("CHAT_MODEL_FALLBACK_API_BASE")
        fallback_key = f"chat_fallback_{fallback_model}_{fallback_api_base or 'default'}"
        
        if is_circuit_breaker_open(fallback_key):
            print(f"🚨 Circuit breaker open for fallback model {fallback_model}")
            raise Exception(f"Both primary and fallback models have circuit breakers open")
        
        # Try fallback with rate limiting
        with semaphore:
            try:
                rate_limit_delay(fallback_key)
                
                # Get fallback client using cache
                def create_fallback_client():
                    fallback_api_key = os.getenv("CHAT_MODEL_FALLBACK_API_KEY")
                    if not fallback_model or not fallback_api_key:
                        raise Exception("Fallback model not configured")
                    
                    client_args = {"api_key": fallback_api_key, "timeout": REQUEST_TIMEOUT}
                    if fallback_api_base:
                        client_args["base_url"] = fallback_api_base
                    return openai.OpenAI(**client_args)
                
                fallback_client = get_cached_client(fallback_key, create_fallback_client)
                print(f"🔄 Using fallback model: {fallback_model}")
                
                # Attempt fallback with retry logic
                for attempt in range(max_retries):
                    try:
                        response = fallback_client.chat.completions.create(
                            model=fallback_model,
                            messages=messages,
                            **kwargs
                        )
                        record_success(fallback_key)
                        print(f"✅ Fallback model {fallback_model} succeeded" + (f" on attempt {attempt + 1}" if attempt > 0 else ""))
                        return response
                        
                    except Exception as e:
                        if is_retryable_error(e) and attempt < max_retries - 1:
                            jitter = random.uniform(0.5, 1.5)
                            delay = min(base_delay * (2 ** attempt) * jitter, max_delay)
                            print(f"⚠️  Fallback model {fallback_model} failed (attempt {attempt + 1}/{max_retries}): {e}")
                            print(f"🔄 Retrying fallback in {delay:.1f}s...")
                            time.sleep(delay)
                            continue
                        else:
                            print(f"❌ Fallback model {fallback_model} failed definitively: {e}")
                            record_error(fallback_key, e)
                            raise e
                            
            except Exception as fallback_error:
                record_error(fallback_key, fallback_error)
                print(f"❌ Fallback model also failed: {fallback_error}")
                raise Exception(f"Both primary and fallback chat models failed. Primary: {primary_error}. Fallback: {fallback_error}")
    
    # No fallback available
    if not use_fallback:
        print("⚠️  Chat model fallback is disabled (USE_CHAT_MODEL_FALLBACK=false)")
    
    if primary_error:
        raise primary_error
    
    raise Exception("Unexpected error in chat completion system")

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
    
    This function now uses the robust fallback system that can switch to a 
    fallback embedding model if the primary fails.
    
    Args:
        texts: List of texts to create embeddings for
        
    Returns:
        List of embeddings (each embedding is a list of floats)
    """
    if not texts:
        return []
    
    # Use the new fallback system
    try:
        return create_embeddings_with_fallback(texts)
    except Exception as e:
        print(f"Both primary and fallback embedding models failed: {e}")
        # Final fallback: return zero embeddings
        embedding_dims = int(os.getenv("EMBEDDING_DIMENSIONS", "1536"))
        print(f"⚠️  Returning zero embeddings as final fallback")
        return [[0.0] * embedding_dims] * len(texts)


def get_embedding_client_with_fallback() -> Tuple[openai.OpenAI, str, int, bool]:
    """
    Get an embedding client with automatic fallback support using cached clients.
    
    Uses singleton pattern with TTL cache to reuse OpenAI client instances
    and reduce connection overhead that causes 503 errors.
    
    Returns:
        Tuple containing:
        - OpenAI client instance (cached)
        - Model name being used
        - Embedding dimensions
        - Boolean indicating if fallback was used (True = fallback, False = primary)
    """
    # Primary model configuration
    primary_model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    primary_api_base = os.getenv("EMBEDDING_MODEL_API_BASE")
    primary_api_key = os.getenv("EMBEDDING_MODEL_API_KEY")
    primary_dims = int(os.getenv("EMBEDDING_DIMENSIONS", "1536"))
    
    # Fallback model configuration
    fallback_model = os.getenv("EMBEDDING_MODEL_FALLBACK")
    fallback_api_base = os.getenv("EMBEDDING_MODEL_FALLBACK_API_BASE")
    fallback_api_key = os.getenv("EMBEDDING_MODEL_FALLBACK_API_KEY")
    fallback_dims = int(os.getenv("EMBEDDING_DIMENSIONS_FALLBACK", "1536"))
    
    # Validate primary configuration
    if not primary_api_key:
        raise ValueError("EMBEDDING_MODEL_API_KEY must be set")
    
    # Try primary model first (with caching)
    primary_key = f"embedding_primary_{primary_model}_{primary_api_base or 'default'}"
    
    def create_primary_embedding_client():
        print(f"Attempting to use primary embedding model: {primary_model}")
        client_args = {"api_key": primary_api_key, "timeout": REQUEST_TIMEOUT}
        if primary_api_base:
            client_args["base_url"] = primary_api_base
        return openai.OpenAI(**client_args)
    
    try:
        client = get_cached_client(primary_key, create_primary_embedding_client)
        print(f"✅ Primary embedding model {primary_model} client ready")
        return client, primary_model, primary_dims, False
        
    except Exception as e:
        print(f"❌ Primary embedding model client creation failed: {e}")
        record_error(primary_key, e)
    
    # Primary model failed, try fallback
    if fallback_model and fallback_api_key:
        fallback_key = f"embedding_fallback_{fallback_model}_{fallback_api_base or 'default'}"
        
        def create_fallback_embedding_client():
            print(f"🔄 Attempting embedding fallback to: {fallback_model}")
            client_args = {"api_key": fallback_api_key, "timeout": REQUEST_TIMEOUT}
            if fallback_api_base:
                client_args["base_url"] = fallback_api_base
            return openai.OpenAI(**client_args)
        
        try:
            client = get_cached_client(fallback_key, create_fallback_embedding_client)
            print(f"✅ Fallback embedding model {fallback_model} client ready")
            return client, fallback_model, fallback_dims, True
            
        except Exception as e:
            print(f"❌ Fallback embedding model client creation failed: {e}")
            record_error(fallback_key, e)
    else:
        print("⚠️  No fallback embedding model configured")
    
    # Both primary and fallback failed
    raise Exception(f"Both primary ({primary_model}) and fallback ({fallback_model}) embedding models failed")


def handle_dimension_mismatch(embeddings: List[List[float]], target_dims: int) -> List[List[float]]:
    """
    Handle dimension mismatches between different embedding models.
    
    Args:
        embeddings: List of embedding vectors
        target_dims: Target dimension count
        
    Returns:
        List of embeddings adjusted to target dimensions
    """
    if not embeddings or not embeddings[0]:
        return embeddings
    
    current_dims = len(embeddings[0])
    
    if current_dims == target_dims:
        return embeddings
    elif current_dims > target_dims:
        # Truncate to target dimensions (keep most informative dimensions)
        print(f"📏 Truncating embeddings: {current_dims}D → {target_dims}D")
        return [embedding[:target_dims] for embedding in embeddings]
    else:
        # Pad with zeros to reach target dimensions
        print(f"📏 Padding embeddings: {current_dims}D → {target_dims}D")
        padding_size = target_dims - current_dims
        return [embedding + [0.0] * padding_size for embedding in embeddings]


def create_embeddings_with_fallback(texts: List[str]) -> List[List[float]]:
    """
    Create embeddings with rate limiting, circuit breaker, and automatic fallback.
    
    This function implements a robust system that:
    1. Uses cached clients to reduce connection overhead
    2. Implements rate limiting to prevent API overload
    3. Circuit breaker to avoid repeated failures
    4. Handles dimension mismatches between models
    5. Exponential backoff with jitter for retries
    
    Args:
        texts: List of texts to create embeddings for
        
    Returns:
        List of embeddings (each embedding is a list of floats)
    """
    if not texts:
        return []
    
    # Get semaphore for concurrency control
    semaphore = get_global_semaphore()
    
    # Configuration
    use_fallback = os.getenv("USE_EMBEDDING_MODEL_FALLBACK", "false").lower() == "true"
    max_retries = 3
    base_delay = 1.0
    max_delay = 15.0
    target_dims = int(os.getenv("EMBEDDING_DIMENSIONS", "1536"))
    primary_error = None
    
    # Primary model configuration
    primary_model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    primary_api_base = os.getenv("EMBEDDING_MODEL_API_BASE")
    primary_key = f"embedding_primary_{primary_model}_{primary_api_base or 'default'}"
    
    # Check circuit breaker for primary
    if is_circuit_breaker_open(primary_key):
        print(f"🚨 Circuit breaker open for primary embedding model {primary_model}, forcing fallback")
        primary_error = Exception("Circuit breaker open")
    else:
        # Try primary model with rate limiting
        with semaphore:
            try:
                rate_limit_delay(primary_key)
                client, model_name, model_dims, is_fallback = get_embedding_client_with_fallback()
                
                if not is_fallback:
                    # Attempt primary model with improved retry logic
                    for attempt in range(max_retries):
                        try:
                            # Process texts for Qwen3-Embedding compatibility
                            processed_texts = texts
                            is_ollama = primary_api_base and "11434" in primary_api_base
                            if is_ollama and "qwen3-embedding" in model_name.lower():
                                processed_texts = [text + "<|endoftext|>" for text in texts]
                                print(f"Added <|endoftext|> token to {len(texts)} texts for Qwen3-Embedding compatibility")
                            
                            # Create embedding request
                            response = client.embeddings.create(
                                model=model_name,
                                input=processed_texts
                            )
                            
                            embeddings = [item.embedding for item in response.data]
                            embeddings = handle_dimension_mismatch(embeddings, target_dims)
                            
                            record_success(primary_key)
                            if attempt > 0:
                                print(f"✅ Primary embedding model {model_name} succeeded on attempt {attempt + 1}")
                            return embeddings
                            
                        except Exception as e:
                            if is_retryable_error(e) and attempt < max_retries - 1:
                                # Exponential backoff with jitter
                                jitter = random.uniform(0.5, 1.5)
                                delay = min(base_delay * (2 ** attempt) * jitter, max_delay)
                                print(f"⚠️  Primary embedding model {model_name} failed (attempt {attempt + 1}/{max_retries}): {e}")
                                print(f"🔄 Retrying in {delay:.1f}s...")
                                time.sleep(delay)
                                continue
                            else:
                                print(f"❌ Primary embedding model {model_name} failed definitively: {e}")
                                record_error(primary_key, e)
                                primary_error = e
                                break
                                
            except Exception as e:
                print(f"❌ Primary embedding model client failed: {e}")
                record_error(primary_key, e)
                primary_error = e
    
    # Try fallback if enabled and primary failed
    if use_fallback and primary_error:
        fallback_model = os.getenv("EMBEDDING_MODEL_FALLBACK")
        fallback_api_base = os.getenv("EMBEDDING_MODEL_FALLBACK_API_BASE")
        fallback_key = f"embedding_fallback_{fallback_model}_{fallback_api_base or 'default'}"
        
        if is_circuit_breaker_open(fallback_key):
            print(f"🚨 Circuit breaker open for fallback embedding model {fallback_model}")
            raise Exception(f"Both primary and fallback embedding models have circuit breakers open")
        
        # Try fallback with rate limiting
        with semaphore:
            try:
                rate_limit_delay(fallback_key)
                
                # Get fallback client using cache
                def create_fallback_embedding_client():
                    fallback_api_key = os.getenv("EMBEDDING_MODEL_FALLBACK_API_KEY")
                    if not fallback_model or not fallback_api_key:
                        raise Exception("Fallback embedding model not configured")
                    
                    client_args = {"api_key": fallback_api_key, "timeout": REQUEST_TIMEOUT}
                    if fallback_api_base:
                        client_args["base_url"] = fallback_api_base
                    return openai.OpenAI(**client_args)
                
                fallback_client = get_cached_client(fallback_key, create_fallback_embedding_client)
                print(f"🔄 Using fallback embedding model: {fallback_model}")
                
                # Attempt fallback with retry logic
                for attempt in range(max_retries):
                    try:
                        response = fallback_client.embeddings.create(
                            model=fallback_model,
                            input=texts
                        )
                        
                        embeddings = [item.embedding for item in response.data]
                        embeddings = handle_dimension_mismatch(embeddings, target_dims)
                        
                        record_success(fallback_key)
                        print(f"✅ Fallback embedding model {fallback_model} succeeded" + (f" on attempt {attempt + 1}" if attempt > 0 else ""))
                        return embeddings
                        
                    except Exception as e:
                        if is_retryable_error(e) and attempt < max_retries - 1:
                            jitter = random.uniform(0.5, 1.5)
                            delay = min(base_delay * (2 ** attempt) * jitter, max_delay)
                            print(f"⚠️  Fallback embedding model {fallback_model} failed (attempt {attempt + 1}/{max_retries}): {e}")
                            print(f"🔄 Retrying fallback in {delay:.1f}s...")
                            time.sleep(delay)
                            continue
                        else:
                            print(f"❌ Fallback embedding model {fallback_model} failed definitively: {e}")
                            record_error(fallback_key, e)
                            raise e
                            
            except Exception as fallback_error:
                record_error(fallback_key, fallback_error)
                print(f"❌ Fallback embedding model also failed: {fallback_error}")
                raise Exception(f"Both primary and fallback embedding models failed. Primary: {primary_error}. Fallback: {fallback_error}")
    
    # No fallback available
    if not use_fallback:
        print("⚠️  Embedding model fallback is disabled (USE_EMBEDDING_MODEL_FALLBACK=false)")
    
    if primary_error:
        raise primary_error
        
    raise Exception("Unexpected error in embedding fallback system")


def create_embedding(text: str) -> List[float]:
    """
    Create an embedding for a single text using OpenAI's API.
    
    Args:
        text: Text to create an embedding for
        
    Returns:
        List of floats representing the embedding
    """
    embedding_dims = int(os.getenv("EMBEDDING_DIMENSIONS", "1536"))
    try:
        embeddings = create_embeddings_batch([text])
        return embeddings[0] if embeddings else [0.0] * embedding_dims
    except Exception as e:
        print(f"Error creating embedding: {e}")
        # Return empty embedding if there's an error
        return [0.0] * embedding_dims

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
    try:
        # Create the prompt for generating contextual information
        prompt = f"""<document>\n{full_document}\n</document>\n<chunk>\n{chunk}\n</chunk> \nPlease give a short succinct context to situate this chunk within the whole document for the purposes of improving search retrieval of the chunk. Answer only with the succinct context and nothing else."""

        # Use robust chat completion with automatic fallback
        response = make_chat_completion_with_fallback(
            messages=[
                {"role": "system", "content": "You are a helpful assistant that provides concise contextual information."},
                {"role": "user", "content": prompt}
            ]
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
    batch_size: int = None
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
    if batch_size is None:
        batch_size = SUPABASE_BATCH_SIZE
    
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
    
    # Check if contextual embeddings are enabled
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
        
        # Apply contextual embedding to each chunk if enabled
        if use_contextual_embeddings:
            # Prepare arguments for parallel processing
            process_args = []
            for j, content in enumerate(batch_contents):
                url = batch_urls[j]
                full_document = url_to_full_document.get(url, "")
                process_args.append((url, content, full_document))
            
            # Process in parallel using ThreadPoolExecutor with conservative worker count
            contextual_contents = []
            max_context_workers = int(os.getenv("MAX_WORKERS_CONTEXT", "1"))
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_context_workers) as executor:
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
        max_retries = SUPABASE_MAX_RETRIES
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


def extract_code_blocks(markdown_content: str) -> List[Dict[str, Any]]:
    """
    Extract code blocks from markdown content along with context.
    
    Args:
        markdown_content: The markdown content to extract code blocks from
        
    Returns:
        List of dictionaries containing code blocks and their context
    """
    min_length = int(os.getenv("MIN_CODE_BLOCK_LENGTH", "1000"))
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
    # Create the prompt
    prompt = f"""<context_before>\n{context_before}\n</context_before>\n<code_example>\n{code}\n</code_example>\n<context_after>\n{context_after}\n</context_after>\n\nPlease provide a concise summary of what this code example demonstrates.\n"""
    
    try:
        # Use the new fallback system
        response = make_chat_completion_with_fallback(
            messages=[
                {"role": "system", "content": "You are a helpful assistant that provides concise code example summaries."},
                {"role": "user", "content": prompt}
            ]
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
    batch_size: int = None
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
    if batch_size is None:
        batch_size = SUPABASE_BATCH_SIZE
    
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
        max_retries = SUPABASE_MAX_RETRIES
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
    
    # Limit content length to avoid token limits
    truncated_content = content[:25000] if len(content) > 25000 else content
    
    prompt = f"""<library_or_tool_content>\n{truncated_content}\n</library_or_tool_content>\n\nPlease provide a concise summary of the above library, tool, or framework.\n"""
    
    try:
        # Use robust chat completion with automatic fallback
        response = make_chat_completion_with_fallback(
            messages=[
                {"role": "system", "content": "You are a helpful assistant that provides concise library/tool/framework summaries."},
                {"role": "user", "content": prompt}
            ]
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