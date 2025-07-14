# 🐛 Performance Issue: MCP Server Timeout/Disconnect Due to Slow Startup

## Problem Description

The MCP server has extremely slow startup times (5-10 seconds) causing timeout and disconnect issues in various MCP clients, particularly Cursor IDE. This is a widespread issue affecting many users.

## Related Issues & Community Reports

This problem has been reported multiple times across different platforms:

- **Cursor Forum**: [MCP Server constantly restarting](https://thinktank.ottomator.ai/t/mcp-server-constantly-restarting/6169) - Users report servers showing "list offering action" then disconnecting
- **Cline Issues**: [MCP Timeout Issues - Can this be extended?](https://github.com/cline/cline/issues/1306) - "Request timed out" errors with MCP servers
- **Cursor Forum**: [MCP Server built in Cursor won't run with Claude Desktop](https://forum.cursor.com/t/mcp-server-built-in-cursor-wont-run-with-claude-desktop/78885) - Server exits early during initialization
- **Zapier Community**: [MCP zapier-mcp: Server disconnected](https://community.zapier.com/ai-actions-zapier-mcp-126/mcp-zapier-mcp-server-disconnected-48627) - Timeout during authentication

## Root Cause Analysis

The issue stems from loading heavy components during server startup:

1. **PyTorch CrossEncoder** (`sentence_transformers`) - Used for reranking
2. **Neo4j Knowledge Graph** components - Used for hallucination detection  
3. **AST parsing libraries** - Used for repository analysis

These components take 5-10 seconds to initialize, causing:
- MCP client timeouts
- "Server disconnected" errors
- "Client closed" issues in Cursor
- Restart loops in various IDEs

## Current Behavior

```bash
# Server startup sequence (SLOW)
1. Initialize AsyncWebCrawler ✓ (fast)
2. Initialize Supabase client ✓ (fast)
3. Load sentence_transformers CrossEncoder ❌ (5+ seconds)
4. Initialize Neo4j KnowledgeGraphValidator ❌ (3+ seconds)
5. Load AST parsing components ❌ (2+ seconds)
# Total: 10+ seconds → TIMEOUT
```

## Proposed Solution: Lazy Loading

Implement lazy loading for heavy components that are only loaded when actually needed:

### Components to Make Lazy:
1. **Reranking Model** - Only load when `perform_rag_query()` is called
2. **Knowledge Graph Validator** - Only load when `check_ai_script_hallucinations()` is called  
3. **Repository Extractor** - Only load when `parse_github_repository()` is called

### Expected Results:
- **Startup time**: 10+ seconds → <1 second
- **Memory usage**: Reduced initial footprint
- **User experience**: Instant server availability
- **Compatibility**: Works with all MCP clients (Cursor, Claude Desktop, etc.)

## Implementation Plan

1. Create lazy loading wrapper functions for heavy components
2. Modify `crawl4ai_lifespan()` to only initialize essential components
3. Update tool functions to use lazy-loaded components
4. Add proper error handling for component initialization

## Testing Strategy

- Test with Docker rebuild
- Verify startup time improvement
- Test all tool functions work correctly
- Validate memory usage optimization
- Test with multiple MCP clients

## Impact

This fix will resolve timeout/disconnect issues for:
- Cursor IDE users
- Claude Desktop users  
- Other MCP client implementations
- Docker-based deployments

The lazy loading approach is a common pattern for performance optimization and will significantly improve the developer experience.

---

**Environment:**
- Python 3.x
- Docker deployment
- FastAPI with MCP integration
- Various MCP clients (Cursor, Claude Desktop, etc.)

**Priority:** High - This affects core functionality and user adoption 