"""
Configuration management for the Crawl4AI MCP server.

This module handles environment variable loading and provides
default values with proper type conversion.
"""
import os
from typing import Optional
from pathlib import Path


class Config:
    """Configuration class for the Crawl4AI MCP server."""
    
    def __init__(self):
        """Initialize configuration with environment detection."""
        self._load_environment()
    
    def _load_environment(self):
        """Load environment variables with proper detection."""
        # Only load .env if we're not in a container or specific environment
        if not self._is_containerized() and not os.getenv('NO_DOTENV'):
            self._load_dotenv_file()
    
    def _is_containerized(self) -> bool:
        """Detect if running in a containerized environment."""
        return (
            os.path.exists('/.dockerenv') or
            os.getenv('CONTAINER') == 'true' or
            os.getenv('KUBERNETES_SERVICE_HOST') is not None
        )
    
    def _load_dotenv_file(self):
        """Load .env file if it exists."""
        try:
            from dotenv import load_dotenv
            project_root = Path(__file__).resolve().parent.parent
            dotenv_path = project_root / '.env'
            if dotenv_path.exists():
                load_dotenv(dotenv_path, override=True)
        except ImportError:
            # dotenv not available, continue with system environment
            pass
        except Exception:
            # Any other error, continue with system environment
            pass
    
    # Server Configuration
    @property
    def HOST(self) -> str:
        """Server host address."""
        return os.getenv("HOST", self.DEFAULT_HOST)
    
    @property
    def PORT(self) -> str:
        """Server port (returned as string for compatibility)."""
        return os.getenv("PORT", self.DEFAULT_PORT)
    
    @property
    def DEFAULT_HOST(self) -> str:
        """Default server host."""
        return os.getenv("DEFAULT_HOST", "0.0.0.0")
    
    @property
    def DEFAULT_PORT(self) -> str:
        """Default server port."""
        return os.getenv("DEFAULT_PORT", "8051")
    
    @property
    def TRANSPORT(self) -> str:
        """Transport protocol."""
        return os.getenv("TRANSPORT", "sse")
    
    # Model Configuration
    @property
    def RERANKING_MODEL(self) -> str:
        """Reranking model name."""
        return os.getenv("RERANKING_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")
    
    @property
    def CHAT_MODEL(self) -> str:
        """Primary chat model."""
        return os.getenv("CHAT_MODEL", "gpt-4o-mini")
    
    @property
    def EMBEDDING_MODEL(self) -> str:
        """Primary embedding model."""
        return os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    
    # Timeout Configuration
    @property
    def OLLAMA_CHECK_TIMEOUT(self) -> int:
        """Timeout for Ollama health checks in seconds."""
        return int(os.getenv("OLLAMA_CHECK_TIMEOUT", "5"))
    
    @property
    def REPO_ANALYSIS_TIMEOUT(self) -> int:
        """Timeout for repository analysis in seconds."""
        return int(os.getenv("REPO_ANALYSIS_TIMEOUT", "1800"))
    
    @property
    def REQUEST_TIMEOUT(self) -> int:
        """Request timeout in seconds."""
        return int(os.getenv("REQUEST_TIMEOUT", "30"))
    
    # Database Configuration
    @property
    def SUPABASE_URL(self) -> Optional[str]:
        """Supabase project URL."""
        return os.getenv("SUPABASE_URL")
    
    @property
    def SUPABASE_SERVICE_KEY(self) -> Optional[str]:
        """Supabase service key."""
        return os.getenv("SUPABASE_SERVICE_KEY")
    
    @property
    def NEO4J_URI(self) -> Optional[str]:
        """Neo4j connection URI."""
        return os.getenv("NEO4J_URI")
    
    @property
    def NEO4J_USER(self) -> Optional[str]:
        """Neo4j username."""
        return os.getenv("NEO4J_USER")
    
    @property
    def NEO4J_PASSWORD(self) -> Optional[str]:
        """Neo4j password."""
        return os.getenv("NEO4J_PASSWORD")
    
    # Feature Flags
    @property
    def USE_KNOWLEDGE_GRAPH(self) -> bool:
        """Whether knowledge graph functionality is enabled."""
        return os.getenv("USE_KNOWLEDGE_GRAPH", "false").lower() == "true"
    
    @property
    def USE_RERANKING(self) -> bool:
        """Whether reranking is enabled."""
        return os.getenv("USE_RERANKING", "false").lower() == "true"
    
    @property
    def USE_HYBRID_SEARCH(self) -> bool:
        """Whether hybrid search is enabled."""
        return os.getenv("USE_HYBRID_SEARCH", "false").lower() == "true"
    
    @property
    def USE_AGENTIC_RAG(self) -> bool:
        """Whether agentic RAG is enabled."""
        return os.getenv("USE_AGENTIC_RAG", "false").lower() == "true"
    
    @property
    def USE_CHAT_MODEL_FALLBACK(self) -> bool:
        """Whether chat model fallback is enabled."""
        return os.getenv("USE_CHAT_MODEL_FALLBACK", "false").lower() == "true"
    
    @property
    def USE_EMBEDDING_MODEL_FALLBACK(self) -> bool:
        """Whether embedding model fallback is enabled."""
        return os.getenv("USE_EMBEDDING_MODEL_FALLBACK", "false").lower() == "true"
    
    # Performance Configuration
    @property
    def MAX_CRAWL_DEPTH(self) -> int:
        """Maximum crawl depth."""
        return int(os.getenv("MAX_CRAWL_DEPTH", "3"))
    
    @property
    def MAX_CONCURRENT_CRAWLS(self) -> int:
        """Maximum concurrent crawl operations."""
        return int(os.getenv("MAX_CONCURRENT_CRAWLS", "10"))
    
    @property
    def CHUNK_SIZE(self) -> int:
        """Chunk size for text processing."""
        return int(os.getenv("CHUNK_SIZE", "5000"))
    
    @property
    def DEFAULT_MATCH_COUNT(self) -> int:
        """Default number of matches to return."""
        return int(os.getenv("DEFAULT_MATCH_COUNT", "5"))
    
    @property
    def MAX_WORKERS_SUMMARY(self) -> int:
        """Maximum workers for summary generation."""
        return int(os.getenv("MAX_WORKERS_SUMMARY", "10"))
    
    @property
    def MAX_WORKERS_SOURCE_SUMMARY(self) -> int:
        """Maximum workers for source summary generation."""
        return int(os.getenv("MAX_WORKERS_SOURCE_SUMMARY", "5"))
    
    # Rate Limiting
    @property
    def MAX_CONCURRENT_REQUESTS(self) -> int:
        """Maximum concurrent requests."""
        return int(os.getenv("MAX_CONCURRENT_REQUESTS", "5"))
    
    @property
    def RATE_LIMIT_DELAY(self) -> float:
        """Rate limit delay in seconds."""
        return float(os.getenv("RATE_LIMIT_DELAY", "0.5"))
    
    @property
    def CIRCUIT_BREAKER_THRESHOLD(self) -> int:
        """Circuit breaker threshold."""
        return int(os.getenv("CIRCUIT_BREAKER_THRESHOLD", "3"))
    
    @property
    def CLIENT_CACHE_TTL(self) -> int:
        """Client cache TTL in seconds."""
        return int(os.getenv("CLIENT_CACHE_TTL", "3600"))
    
    # API Configuration
    @property
    def EMBEDDING_MODEL_API_BASE(self) -> Optional[str]:
        """Embedding model API base URL."""
        return os.getenv("EMBEDDING_MODEL_API_BASE")


# Global configuration instance
config = Config()