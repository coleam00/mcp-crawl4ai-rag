# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **Crawl4AI RAG MCP Server** that provides web crawling and RAG capabilities for AI agents and coding assistants. It implements the Model Context Protocol (MCP) with integration to Crawl4AI, Supabase for vector storage, and Neo4j for knowledge graph functionality.

## Core Architecture

### Main Components
- **MCP Server** (`src/crawl4ai_mcp.py`): FastMCP-based server providing web crawling and RAG tools
- **Utilities** (`src/utils.py`): Supabase client, document embedding, and search functions
- **Knowledge Graph Tools** (`knowledge_graphs/`): Neo4j-based AI hallucination detection and repository analysis

### Key Technologies
- **FastMCP**: Server framework for Model Context Protocol
- **Crawl4AI**: Web crawling with intelligent content detection
- **Supabase**: Vector database for RAG functionality using pgvector
- **Neo4j**: Knowledge graph for code structure analysis and hallucination detection
- **OpenAI**: Embeddings (text-embedding-3-small) and LLM for contextual processing

## Development Commands

### Setup and Installation
```bash
# Install dependencies
uv pip install -e .
crawl4ai-setup

# Using Docker Compose (Recommended)
docker compose up --build

# Using Docker (standalone)
docker build -t mcp/crawl4ai-rag --build-arg PORT=8051 .
```

### Running the Server
```bash
# Docker Compose (with Neo4j)
docker compose up --build
./quick-start.sh  # Quick start script

# Direct Python execution
uv run src/crawl4ai_mcp.py

# Docker execution (standalone)
docker run --env-file .env -p 8051:8051 mcp/crawl4ai-rag
```

### Common Docker Compose Commands
```bash
# View logs
docker compose logs -f

# Check service status  
docker compose ps

# Stop services
docker compose down

# Clean up (removes data)
docker compose down -v

# Restart specific service
docker compose restart mcp-server
```

### Database Setup
- Execute `crawled_pages.sql` in Supabase to create necessary tables and functions
- Neo4j setup required for knowledge graph features (see README.md)

## Configuration

### Environment Variables
Key variables are defined in `.env.example`. Notable settings:
- `TRANSPORT`: "sse" or "stdio" for MCP transport
- `USE_KNOWLEDGE_GRAPH`: Enable Neo4j-based hallucination detection
- RAG strategy toggles: `USE_CONTEXTUAL_EMBEDDINGS`, `USE_HYBRID_SEARCH`, `USE_AGENTIC_RAG`, `USE_RERANKING`

### Docker Compose Setup
The repository includes an implementation plan for Docker Compose orchestration with Neo4j container integration. The planned architecture includes:
- MCP server container connected to Neo4j container
- Persistent Neo4j data storage
- Service health checks and dependency management

## MCP Tools Provided

### Core Tools
- `crawl_single_page`: Crawl and store single webpage
- `smart_crawl_url`: Intelligent full-website crawling (sitemaps, recursive)
- `get_available_sources`: List available data sources
- `perform_rag_query`: Semantic search with source filtering

### Conditional Tools
- `search_code_examples`: Code-specific search (requires `USE_AGENTIC_RAG=true`)
- `parse_github_repository`: GitHub repo analysis into Neo4j
- `check_ai_script_hallucinations`: Validate AI-generated code
- `query_knowledge_graph`: Neo4j graph exploration

## Code Structure Patterns

### MCP Tool Implementation
Tools are implemented using `@mcp.tool()` decorator with FastMCP framework. Each tool includes:
- Detailed docstring with parameter descriptions
- Type hints for all parameters
- Error handling for external service failures

### Knowledge Graph Schema
Neo4j stores code structure as nodes (Repository, File, Class, Method, Function) with relationships (CONTAINS, DEFINES, HAS_METHOD, HAS_ATTRIBUTE).

### RAG Pipeline
1. Content crawling with intelligent chunking by headers
2. Contextual embedding enhancement (optional)
3. Vector storage in Supabase with pgvector
4. Hybrid search combining vector + keyword search
5. Cross-encoder reranking for relevance

## External Dependencies

### Required Services
- **Supabase**: Vector database with pgvector extension
- **OpenAI API**: For embeddings and LLM processing
- **Neo4j**: Knowledge graph database (optional, for hallucination detection)

### Python Dependencies
Key packages from `pyproject.toml`:
- `crawl4ai==0.6.2`: Web crawling engine
- `mcp==1.7.1`: Model Context Protocol implementation
- `supabase==2.15.1`: Database client
- `neo4j>=5.28.1`: Graph database client
- `sentence-transformers>=4.1.0`: Cross-encoder reranking

## Testing Knowledge Graph Features

To test hallucination detection:
```bash
python knowledge_graphs/ai_hallucination_detector.py [script_path]
```

The system validates AI-generated Python code against indexed repository structures to detect non-existent methods, classes, or incorrect usage patterns.