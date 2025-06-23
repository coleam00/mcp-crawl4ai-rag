# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Running the MCP Server

**Using uv (recommended for development):**
```bash
uv run src/crawl4ai_mcp.py
```

**Using Docker:**
```bash
# Build the image
docker build -t mcp/crawl4ai-rag --build-arg PORT=8051 .

# Run the container
docker run --env-file .env -p 8051:8051 mcp/crawl4ai-rag
```

**Using Docker Compose (with Ollama for Local Embeddings):**
```bash
# Start all services including Ollama
docker-compose up -d

# Check logs
docker-compose logs -f

# Stop all services
docker-compose down
```

### Environment Setup

**With uv:**
```bash
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e .
crawl4ai-setup
```

**Environment Configuration:**
- Copy `.env.example` to `.env` and configure required variables
- **Core Required Variables:**
  - `SUPABASE_URL` - Supabase project URL
  - `SUPABASE_SERVICE_KEY` - Supabase service role key
  - `CHAT_MODEL_API_KEY` - Primary chat model API key
  - `EMBEDDING_MODEL_API_KEY` - Embedding model API key
- **Optional Variables:**
  - `CHAT_MODEL_FALLBACK_API_KEY` - Fallback chat model for reliability
  - `CHAT_MODEL_FALLBACK` - Fallback model name (e.g., gpt-3.5-turbo)
  - Neo4j variables (`NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`) for knowledge graph functionality
  - Transport configuration (`TRANSPORT=sse` or `stdio`)
  - Performance tuning variables (workers, batch sizes)

**Local Ollama Configuration:**
For running with local Qwen3-Embedding models via Ollama:
```bash
# Required environment variables for Ollama
EMBEDDING_MODEL_API_BASE=http://localhost:11434/v1  # Use http://ollama:11434/v1 in Docker
EMBEDDING_MODEL_API_KEY=ollama  # Required but ignored
EMBEDDING_MODEL=dengcao/Qwen3-Embedding-0.6B:Q8_0  # Primary: compact & efficient
EMBEDDING_DIMENSIONS=1024  # Native dimensions for 0.6B model (no truncation)

# Alternative: High-capacity model
# EMBEDDING_MODEL=dengcao/Qwen3-Embedding-8B:Q4_K_M  # 4.7GB, up to 4096D

# Optional: Local chat model
CHAT_MODEL_API_BASE=http://localhost:11434/v1
CHAT_MODEL_API_KEY=ollama
CHAT_MODEL=qwen3:latest

# Concurrency settings (optimized for local processing)
MAX_WORKERS_SUMMARY=1        # Prevents API overload
MAX_WORKERS_CONTEXT=1        # Reduces 503 errors
MAX_WORKERS_SOURCE_SUMMARY=1
SUPABASE_BATCH_SIZE=2        # Smaller batches for stability
```

### Database Setup

Execute `crawled_pages_1024d.sql` in Supabase SQL Editor to create required tables and functions. This is the updated schema for 1024-dimensional embeddings.

**Database Schema (updated for 1024D embeddings):**
- Tables use `vector(1024)` for optimal compatibility with Qwen3-Embedding-0.6B
- HNSW indexes configured for 1024-dimensional vectors
- PostgreSQL supports up to 2000 dimensions, so 1024D is well within limits

## Code Architecture

### MCP Server Structure

The server is built using FastMCP with an async context manager pattern:

- **`src/crawl4ai_mcp.py`** - Main MCP server with 8 tools (5 core + 3 conditional)
- **`src/utils.py`** - Utility functions for embeddings, Supabase operations, and content processing
- **`knowledge_graphs/`** - Neo4j knowledge graph components for AI hallucination detection

### Core Components

**Lifespan Management (`crawl4ai_lifespan`):**
- Initializes AsyncWebCrawler, Supabase client, optional reranking model
- Conditionally initializes Neo4j components when `USE_KNOWLEDGE_GRAPH=true`
- Handles cleanup of all resources

**Tool Categories:**
1. **Core Tools** (always available): `crawl_single_page`, `smart_crawl_url`, `get_available_sources`, `perform_rag_query`
2. **Agentic RAG** (when `USE_AGENTIC_RAG=true`): `search_code_examples`
3. **Knowledge Graph** (when `USE_KNOWLEDGE_GRAPH=true`): `parse_github_repository`, `check_ai_script_hallucinations`, `query_knowledge_graph`

### RAG Strategy Implementation

The server supports 5 configurable RAG strategies via environment flags:

1. **Contextual Embeddings** (`USE_CONTEXTUAL_EMBEDDINGS`) - LLM-enhanced chunk context before embedding
2. **Hybrid Search** (`USE_HYBRID_SEARCH`) - Combines vector and keyword search with intelligent result merging
3. **Agentic RAG** (`USE_AGENTIC_RAG`) - Extracts and indexes code examples separately with summaries
4. **Reranking** (`USE_RERANKING`) - Cross-encoder reranking for improved result relevance
5. **Knowledge Graph** (`USE_KNOWLEDGE_GRAPH`) - Neo4j-based code structure analysis for hallucination detection

### Content Processing Pipeline

**Document Processing:**
1. Crawl with Crawl4AI (supports sitemaps, text files, recursive crawling)
2. Smart chunking by code blocks, paragraphs, then sentences (`smart_chunk_markdown`)
3. Optional contextual embedding enhancement
4. Batch embedding creation and Supabase storage
5. Source summary generation and metadata extraction

**Code Example Processing (when enabled):**
1. Extract code blocks >1000 chars with surrounding context
2. Generate summaries via LLM
3. Store in separate `code_examples` table with combined embeddings

### Knowledge Graph Architecture

**Components:**
- **`parse_repo_into_neo4j.py`** - Repository analysis and Neo4j storage
- **`ai_script_analyzer.py`** - AST-based Python script analysis  
- **`knowledge_graph_validator.py`** - Validates code against knowledge graph
- **`hallucination_reporter.py`** - Generates detailed hallucination reports

**Schema:**
- Nodes: Repository, File, Class, Method, Function, Attribute
- Relationships: CONTAINS, DEFINES, HAS_METHOD, HAS_ATTRIBUTE

### Error Handling Patterns

The codebase implements comprehensive error handling:
- Exponential backoff retry logic for API calls and database operations
- Graceful degradation (e.g., fallback to individual operations when batch fails)
- Validation functions with detailed error messages
- Resource cleanup in lifespan context managers

### Transport Support

Supports both SSE and stdio transports via `TRANSPORT` environment variable, enabling integration with various MCP clients.

## Configuration Files

- **`pyproject.toml`** - Python dependencies and project metadata
- **`.env`** - Environment variables for API keys, database URLs, and feature flags
- **`crawled_pages_1024d.sql`** - Supabase database schema and functions (1024D embeddings)
- **`Dockerfile`** - Container configuration for deployment
- **`docker-compose.yml`** - Multi-service orchestration including Ollama for local embeddings
- **`batch_crawler/`** - Batch processing scripts for multiple URLs

## Local Embedding Models (Ollama)

The project supports running locally with Qwen3-Embedding models via Ollama for enhanced privacy and cost efficiency:

### Available Models
- **`dengcao/Qwen3-Embedding-0.6B:Q8_0`** - **Recommended** compact model (639MB, 0.6B parameters)
  - Native 1024D output (no truncation needed)
  - Optimal for most use cases with excellent performance/efficiency ratio
- **`dengcao/Qwen3-Embedding-8B:Q4_K_M`** - High-capacity model (4.7GB, 8B parameters)
  - Up to 4096D output (typically truncated to 1024D)
  - Better for specialized domains requiring maximum accuracy

### Features
- **Multi-language Support**: 100+ languages including programming languages
- **Large Context**: 32k token context length
- **Optimized Dimensions**: Native 1024D (0.6B) or up to 4096D (8B) with MRL support
- **Local Processing**: No API costs, enhanced privacy, GDPR compliant
- **OpenAI Compatibility**: Drop-in replacement using OpenAI client libraries
- **Efficient Processing**: 87% smaller model size with comparable quality

### Setup with Docker Compose
```bash
# Start Ollama and MCP server
docker-compose up -d

# Models are automatically pulled on first startup (0.6B prioritized)
# Or manually pull models:
docker-compose exec ollama ollama pull dengcao/Qwen3-Embedding-0.6B:Q8_0
docker-compose exec ollama ollama pull dengcao/Qwen3-Embedding-8B:Q4_K_M

# Using published image (faster startup)
docker-compose -f docker-compose.published.yml up -d
```

### Manual Ollama Setup
```bash
# Install and start Ollama
curl -fsSL https://ollama.com/install.sh | sh
ollama serve

# Pull embedding models (0.6B recommended)
ollama pull dengcao/Qwen3-Embedding-0.6B:Q8_0
ollama pull dengcao/Qwen3-Embedding-8B:Q4_K_M

# Optional: Pull chat models
ollama pull qwen3:latest
```

### Performance Recommendations
- **Default Choice**: `Qwen3-Embedding-0.6B:Q8_0` with `EMBEDDING_DIMENSIONS=1024`
  - Native output, no truncation overhead
  - 639MB model size, ~2GB RAM usage
  - Optimal performance/efficiency ratio
- **High-Accuracy Scenarios**: `Qwen3-Embedding-8B:Q4_K_M` with `EMBEDDING_DIMENSIONS=1024`
  - 4.7GB model size, ~8GB RAM usage  
  - Better for specialized domains
- **Concurrency Settings**: Use reduced workers to prevent API 503 errors
  - `MAX_WORKERS_SUMMARY=1`
  - `SUPABASE_BATCH_SIZE=2`

## Deployment

### Docker Hub Image
Pre-built images are available on Docker Hub:
```bash
# Pull latest image
docker pull drnit29/mcp-crawl4ai-rag:latest

# Run with environment file
docker run --env-file .env -p 8051:8051 drnit29/mcp-crawl4ai-rag:latest

# Use published Docker Compose configuration
docker-compose -f docker-compose.published.yml up -d
```

### Build and Push Scripts
- **`build-and-push.bat`** - Automated build, test, and Docker Hub upload
- **`build.bat`** - Local build with full service stack
- **`build-ollama.bat`** - Standalone Ollama container build

## Troubleshooting

### HTTP 503 Service Unavailable Errors
When you see repeated 503 errors for chat model requests:
```
HTTP Request: POST https://copilot.quantmind.com.br/chat/completions "HTTP/1.1 503 Service Unavailable"
```

**Solutions:**
1. **Reduce Concurrency** (in `.env`):
   ```bash
   MAX_WORKERS_SUMMARY=1
   MAX_WORKERS_CONTEXT=1  
   MAX_WORKERS_SOURCE_SUMMARY=1
   SUPABASE_BATCH_SIZE=2
   ```

2. **Disable Resource-Intensive Features**:
   ```bash
   USE_CONTEXTUAL_EMBEDDINGS=false
   USE_AGENTIC_RAG=false
   ```

3. **Use Local Chat Model**:
   ```bash
   CHAT_MODEL_API_BASE=http://ollama:11434/v1
   CHAT_MODEL=qwen3:latest
   ```

### Common Issues
- **Git not found in container**: Fixed in latest Docker image
- **Embedding dimension mismatch**: Use 1024D for Qwen3-Embedding-0.6B
- **Memory issues**: 0.6B model requires ~2GB RAM, 8B model requires ~8GB RAM
- **SSL/network errors**: Ensure proper Docker network configuration

## Robust Fallback System

The MCP server includes a comprehensive fallback system for both chat models and embedding models to improve reliability when primary models fail. The system features individual control flags, API-level fallback (not just client creation), and intelligent retry logic.

### Core Features

- **Individual Control**: Separate enable/disable flags for chat and embedding fallbacks
- **API-Level Fallback**: Handles actual API call failures (503, 429, timeout) not just client creation
- **Intelligent Retry**: Exponential backoff with jitter for temporary failures
- **Dimension Handling**: Automatic truncation/padding for different embedding model dimensions
- **Clear Logging**: Detailed status messages for debugging and monitoring

### Configuration

#### Chat Model Fallback

Enable chat model fallback and configure models in your `.env` file:

```bash
# Enable chat model fallback (default: false)
USE_CHAT_MODEL_FALLBACK=true

# Primary Chat Model
CHAT_MODEL=qwen3:latest
CHAT_MODEL_API_KEY=ollama
CHAT_MODEL_API_BASE=http://localhost:11434/v1

# Fallback Chat Model (used when primary fails)
CHAT_MODEL_FALLBACK=gpt-4o-mini
CHAT_MODEL_FALLBACK_API_KEY=your_openai_api_key
CHAT_MODEL_FALLBACK_API_BASE=  # Optional, defaults to OpenAI
```

#### Embedding Model Fallback

Enable embedding model fallback and configure models:

```bash
# Enable embedding model fallback (default: false)
USE_EMBEDDING_MODEL_FALLBACK=true

# Primary Embedding Model
EMBEDDING_MODEL=dengcao/Qwen3-Embedding-0.6B:Q8_0
EMBEDDING_MODEL_API_KEY=ollama
EMBEDDING_MODEL_API_BASE=http://localhost:11434/v1
EMBEDDING_DIMENSIONS=1024

# Fallback Embedding Model (used when primary fails)
EMBEDDING_MODEL_FALLBACK=text-embedding-3-small
EMBEDDING_MODEL_FALLBACK_API_KEY=your_openai_api_key
EMBEDDING_MODEL_FALLBACK_API_BASE=  # Optional, defaults to OpenAI
EMBEDDING_DIMENSIONS_FALLBACK=1536  # Fallback model dimensions
```

### Common Fallback Scenarios

#### Local-to-Cloud Fallback (Recommended)

**Chat Models:**
```bash
USE_CHAT_MODEL_FALLBACK=true

# Primary: Local Ollama (fast, free, private)
CHAT_MODEL=qwen3:latest
CHAT_MODEL_API_BASE=http://localhost:11434/v1
CHAT_MODEL_API_KEY=ollama

# Fallback: OpenAI (reliable, but costs money)
CHAT_MODEL_FALLBACK=gpt-4o-mini
CHAT_MODEL_FALLBACK_API_KEY=sk-...
```

**Embedding Models:**
```bash
USE_EMBEDDING_MODEL_FALLBACK=true

# Primary: Local Qwen3-Embedding (1024D native)
EMBEDDING_MODEL=dengcao/Qwen3-Embedding-0.6B:Q8_0
EMBEDDING_MODEL_API_BASE=http://localhost:11434/v1
EMBEDDING_MODEL_API_KEY=ollama
EMBEDDING_DIMENSIONS=1024

# Fallback: OpenAI (reliable, different dimensions)
EMBEDDING_MODEL_FALLBACK=text-embedding-3-small
EMBEDDING_MODEL_FALLBACK_API_KEY=sk-...
EMBEDDING_DIMENSIONS_FALLBACK=1536
```

#### Cloud-to-Local Fallback

```bash
USE_CHAT_MODEL_FALLBACK=true
USE_EMBEDDING_MODEL_FALLBACK=true

# Primary: OpenAI (best quality)
CHAT_MODEL=gpt-4o
CHAT_MODEL_API_KEY=sk-...
EMBEDDING_MODEL=text-embedding-3-large
EMBEDDING_MODEL_API_KEY=sk-...

# Fallback: Local Ollama (if OpenAI has issues)
CHAT_MODEL_FALLBACK=qwen3:latest
CHAT_MODEL_FALLBACK_API_KEY=ollama
CHAT_MODEL_FALLBACK_API_BASE=http://localhost:11434/v1
EMBEDDING_MODEL_FALLBACK=dengcao/Qwen3-Embedding-0.6B:Q8_0
EMBEDDING_MODEL_FALLBACK_API_KEY=ollama
EMBEDDING_MODEL_FALLBACK_API_BASE=http://localhost:11434/v1
```

### How It Works

#### Chat Model Fallback Process

1. **Primary Attempt**: Try primary chat model with exponential backoff retry
2. **Error Detection**: Detect retryable errors (503, 429, 500, timeout)
3. **Fallback Check**: If enabled (`USE_CHAT_MODEL_FALLBACK=true`), switch to fallback
4. **Fallback Attempt**: Try fallback model with same retry logic
5. **Clear Logging**: Status messages throughout the process

#### Embedding Model Fallback Process

1. **Primary Attempt**: Try primary embedding model with retry logic
2. **Dimension Handling**: Process texts (add tokens if needed for Qwen3)
3. **Error Detection**: Handle API failures and dimension mismatches
4. **Fallback Attempt**: Switch to fallback model if enabled
5. **Dimension Adjustment**: Automatically truncate or pad embeddings to match target dimensions

### Error Types Handled

The fallback system automatically handles these error conditions:

- **HTTP 503**: Service Unavailable
- **HTTP 429**: Rate Limit Exceeded  
- **HTTP 500**: Internal Server Error
- **HTTP 502**: Bad Gateway
- **HTTP 504**: Gateway Timeout
- **Connection Errors**: Network timeouts, refused connections
- **Authentication Errors**: Invalid API keys (triggers fallback immediately)

### Logging Examples

```bash
# Normal operation
✅ Primary chat model qwen3:latest succeeded

# Retry with recovery
⚠️  Primary model qwen3:latest failed (attempt 1/3): HTTP 503 Service Unavailable
🔄 Retrying in 1.2s...
✅ Primary model qwen3:latest succeeded on attempt 2

# Fallback activation
❌ Primary model qwen3:latest failed definitively: HTTP 503 Service Unavailable
🔄 Using fallback model: gpt-4o-mini
✅ Fallback model gpt-4o-mini succeeded

# Dimension handling
📏 Truncating embeddings: 1536D → 1024D
```

### Functions Using Fallback System

#### Chat Models
- **`make_chat_completion_with_fallback()`** - Core chat completion with fallback
- **Contextual Embeddings** (`USE_CONTEXTUAL_EMBEDDINGS=true`)
- **Code Example Summaries** (`USE_AGENTIC_RAG=true`)
- **Source Summaries** (automatic during crawling)

#### Embedding Models
- **`create_embeddings_with_fallback()`** - Core embedding creation with fallback
- **Document Chunking and Indexing** (automatic during crawling)
- **RAG Query Processing** (search and retrieval)
- **Code Example Embedding** (`USE_AGENTIC_RAG=true`)

### Testing the Fallback System

Run the comprehensive test suite:

```bash
# Test both chat and embedding fallback systems
python test_fallback.py
```

The test script validates:
- Chat completion fallback with enable/disable flags
- Embedding fallback with dimension handling
- Client creation fallback (legacy system)
- Error handling and retry logic

### Best Practices

#### Configuration
- **Enable for production**: Set both `USE_CHAT_MODEL_FALLBACK=true` and `USE_EMBEDDING_MODEL_FALLBACK=true`
- **Choose complementary models**: Fast local primary + reliable cloud fallback
- **Test both models**: Verify configurations before deployment
- **Monitor costs**: Fallback models may have different pricing

#### Monitoring
- **Watch logs**: Frequent fallback usage indicates primary model issues
- **Set alerts**: Monitor for repeated fallback activation
- **Track performance**: Compare response times between primary and fallback

#### Optimization
- **Adjust retry counts**: Modify `max_retries` in source code if needed
- **Tune dimensions**: Use native dimensions when possible (1024D for Qwen3-0.6B)
- **Batch size**: Reduce `SUPABASE_BATCH_SIZE` if fallback triggers frequently

## Testing

No formal test suite exists. Test the server by:
1. Running with different RAG strategy combinations
2. Crawling various URL types (regular pages, sitemaps, text files)
3. Testing knowledge graph functionality with GitHub repositories
4. Validating MCP tool responses across different clients
5. Health check: `curl http://localhost:8051/health`

## Batch Processing

The `batch_crawler/` directory contains utilities for processing multiple URLs sequentially:

### Available Scripts
- **`batch_crawler_working.py`** - Production-ready batch processor using stdio transport
- **`batch_crawler.py`** - Original version (SSE transport limitations)
- **`test_mcp_connection.py`** - Connection diagnostics and health checks

### Usage
```bash
cd batch_crawler

# Setup (Windows)
setup.bat

# Interactive mode (Windows)
start.bat

# Manual execution
python batch_crawler_working.py urls.txt --output results.json --delay 1.0
```

### Features
- Sequential URL processing with configurable delays
- Automatic retry logic and error handling
- Progress tracking and detailed logging
- JSON output with comprehensive statistics
- Windows automation scripts for easy setup and execution

See `batch_crawler/README.md` for complete documentation.