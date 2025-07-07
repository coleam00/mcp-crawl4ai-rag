# Docker Compose Setup Planning Document
## Crawl4AI RAG MCP Server with Neo4j Integration

### 🎯 Project Objective
Configure a complete Docker Compose environment that allows running `docker compose up` from the project root to have a fully functional MCP server connected to Neo4j (local container) and Supabase (remote service).

### 📋 Requirements Overview

1. **MCP Server Container**
   - Built from existing Dockerfile
   - Connected to Neo4j container
   - Connected to remote Supabase service
   - All environment variables configured in docker-compose.yml

2. **Neo4j Container**
   - Local Neo4j instance for knowledge graph functionality
   - Accessible by MCP server
   - Persistent data storage
   - Pre-configured authentication

3. **Network Configuration**
   - Internal network for MCP ↔ Neo4j communication
   - External connectivity for Supabase API calls

### 🏗️ Architecture Design

```
┌─────────────────────────────────────────────┐
│            Docker Compose Network            │
│                                             │
│  ┌─────────────────┐    ┌────────────────┐ │
│  │   MCP Server    │    │     Neo4j      │ │
│  │  (Port 8051)    │◄──►│  (Port 7687)   │ │
│  │                 │    │                 │ │
│  └────────┬────────┘    └────────────────┘ │
│           │                                 │
└───────────┼─────────────────────────────────┘
            │
            ▼
    ┌────────────────┐
    │    Supabase    │
    │ (Remote Cloud) │
    └────────────────┘
```

### 📁 File Structure

```
crawl4ai-mcp/
├── docker-compose.yml          # Main orchestration file
├── .env.example               # Example environment variables
├── .env                       # Actual environment variables (git-ignored)
├── Dockerfile                 # Existing MCP server Dockerfile
├── neo4j/
│   ├── data/                  # Neo4j data persistence (git-ignored)
│   ├── logs/                  # Neo4j logs (git-ignored)
│   └── conf/                  # Neo4j configuration
└── README.md                  # Updated with Docker Compose instructions
```

### 🔧 Implementation Steps

#### Step 1: Create Docker Compose Configuration
- Define services: mcp-server and neo4j
- Configure networks and volumes
- Set up environment variables
- Configure health checks

#### Step 2: Update MCP Server Configuration
- Modify Neo4j URI to use container hostname
- Ensure proper error handling for container startup
- Add wait-for-it logic for Neo4j readiness

#### Step 3: Configure Neo4j Service
- Use official Neo4j Docker image
- Set up authentication
- Configure persistent volumes
- Set memory limits and performance tuning

#### Step 4: Environment Variable Management
- Consolidate all variables in docker-compose.yml
- Use .env file for sensitive data
- Provide clear .env.example template

#### Step 5: Network Configuration
- Create custom bridge network
- Configure service discovery
- Set up proper container naming

### 🔐 Environment Variables Schema

```yaml
# MCP Server Configuration
HOST: "0.0.0.0"
PORT: "8051"
TRANSPORT: "sse"

# OpenAI Configuration
OPENAI_API_KEY: "${OPENAI_API_KEY}"
MODEL_CHOICE: "gpt-4-mini"

# RAG Strategies
USE_CONTEXTUAL_EMBEDDINGS: "false"
USE_HYBRID_SEARCH: "false"
USE_AGENTIC_RAG: "false"
USE_RERANKING: "false"
USE_KNOWLEDGE_GRAPH: "true"

# Supabase Configuration (Remote)
SUPABASE_URL: "${SUPABASE_URL}"
SUPABASE_SERVICE_KEY: "${SUPABASE_SERVICE_KEY}"

# Neo4j Configuration (Local Container)
NEO4J_URI: "bolt://neo4j:7687"  # Using container name
NEO4J_USER: "neo4j"
NEO4J_PASSWORD: "${NEO4J_PASSWORD}"
```

### 📝 Docker Compose Structure

```yaml
version: '3.8'

services:
  mcp-server:
    build: .
    ports:
      - "8051:8051"
    environment:
      # All environment variables here
    depends_on:
      neo4j:
        condition: service_healthy
    networks:
      - crawl4ai-network

  neo4j:
    image: neo4j:5-community
    ports:
      - "7474:7474"  # Browser
      - "7687:7687"  # Bolt
    volumes:
      - ./neo4j/data:/data
      - ./neo4j/logs:/logs
    environment:
      - NEO4J_AUTH=neo4j/${NEO4J_PASSWORD}
    healthcheck:
      test: ["CMD-SHELL", "neo4j status"]
      interval: 10s
      timeout: 10s
      retries: 5
    networks:
      - crawl4ai-network

networks:
  crawl4ai-network:
    driver: bridge
```

### ⚡ Startup Sequence

1. **Neo4j Initialization**
   - Container starts
   - Health check passes
   - Ready to accept connections

2. **MCP Server Startup**
   - Waits for Neo4j health check
   - Initializes connections
   - Starts listening on port 8051

### 🚀 Usage Instructions

1. **Initial Setup**
   ```bash
   # Copy environment template
   cp .env.example .env
   
   # Edit .env with your credentials
   nano .env
   
   # Create Neo4j directories
   mkdir -p neo4j/data neo4j/logs
   ```

2. **Start Services**
   ```bash
   # Build and start all services
   docker compose up --build
   
   # Or run in detached mode
   docker compose up -d --build
   ```

3. **Verify Services**
   ```bash
   # Check service status
   docker compose ps
   
   # View logs
   docker compose logs -f
   
   # Test MCP server
   curl http://localhost:8051/health
   ```

### 🔍 Testing Plan

1. **Container Health**
   - Neo4j responds on port 7687
   - MCP server responds on port 8051
   - Logs show successful initialization

2. **Integration Tests**
   - MCP can connect to Neo4j
   - MCP can connect to Supabase
   - Knowledge graph tools are available

3. **Functional Tests**
   - Parse a GitHub repository
   - Check AI script hallucinations
   - Query knowledge graph

### 🐛 Troubleshooting Guide

1. **Neo4j Connection Issues**
   - Check if Neo4j is fully started
   - Verify credentials in .env
   - Check network connectivity

2. **MCP Server Startup Failures**
   - Review logs: `docker compose logs mcp-server`
   - Verify all required env vars are set
   - Check Dockerfile build output

3. **Supabase Connection Issues**
   - Verify API credentials
   - Check network connectivity
   - Test with curl from container

### 📊 Performance Considerations

1. **Neo4j Tuning**
   - Set appropriate memory limits
   - Configure page cache
   - Optimize for graph operations

2. **MCP Server Optimization**
   - Configure concurrent workers
   - Set appropriate timeouts
   - Monitor memory usage

### 🔄 Maintenance Tasks

1. **Backup Neo4j Data**
   ```bash
   docker compose exec neo4j neo4j-admin dump --to=/data/backup.dump
   ```

2. **Update Services**
   ```bash
   docker compose pull
   docker compose up -d --build
   ```

3. **Clean Up**
   ```bash
   docker compose down -v  # Remove volumes too
   ```

### 📚 Next Steps

1. Implement docker-compose.yml based on this plan
2. Update Dockerfile if needed for better container compatibility
3. Create helper scripts for common operations
4. Add monitoring and logging configuration
5. Document production deployment considerations

### 🎉 Success Criteria

- Single command startup: `docker compose up`
- All services healthy and connected
- MCP server accessible at http://localhost:8051
- Neo4j browser accessible at http://localhost:7474
- Knowledge graph tools fully functional
- Proper error handling and logging