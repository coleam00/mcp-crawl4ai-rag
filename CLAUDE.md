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

### Database Setup

Execute `crawled_pages.sql` in Supabase SQL Editor to create required tables and functions.

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

## Testing

No formal test suite exists. Test the server by:
1. Running with different RAG strategy combinations
2. Crawling various URL types (regular pages, sitemaps, text files)
3. Testing knowledge graph functionality with GitHub repositories
4. Validating MCP tool responses across different clients