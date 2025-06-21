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
- Required: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `CHAT_MODEL_API_KEY`, `EMBEDDING_MODEL_API_KEY`
- Optional: Neo4j variables for knowledge graph functionality

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

Execute `crawled_pages.sql` in Supabase SQL Editor to create required tables and functions.

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
- **`crawled_pages.sql`** - Supabase database schema and functions
- **`Dockerfile`** - Container configuration for deployment
- **`docker-compose.yml`** - Multi-service orchestration including Ollama for local embeddings

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

## Testing

No formal test suite exists. Test the server by:
1. Running with different RAG strategy combinations
2. Crawling various URL types (regular pages, sitemaps, text files)
3. Testing knowledge graph functionality with GitHub repositories
4. Validating MCP tool responses across different clients
5. Health check: `curl http://localhost:8051/health`