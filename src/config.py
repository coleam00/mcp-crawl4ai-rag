"""Configuration management using Pydantic settings."""

from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with validation."""
    
    # MCP Server Configuration
    host: str = "0.0.0.0"
    port: int = 8051
    transport: str = "sse"  # Server-Sent Events
    
    # OpenAI Configuration - REQUIRED
    openai_api_key: str
    model_choice: str = "gpt-4o-mini"
    
    # Supabase Configuration - REQUIRED
    supabase_url: str
    supabase_service_key: str
    
    # Feature Flags
    use_contextual_embeddings: bool = False
    use_hybrid_search: bool = False
    use_reranking: bool = False
    use_agentic_rag: bool = False  # For code example extraction
    
    # Crawling Configuration
    default_max_depth: int = 3
    default_max_concurrent: int = 10
    default_chunk_size: int = 5000
    default_overlap: int = 200
    
    # Search Configuration
    default_num_results: int = 5
    default_semantic_threshold: float = 0.5
    default_rerank_threshold: float = 0.3
    
    # Model Configuration
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    cross_encoder_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    
    model_config = SettingsConfigDict(
        env_file=Path(__file__).parent.parent / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    
    def validate_required_fields(self) -> None:
        """Validate that all required fields are set."""
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required")
        if not self.supabase_url:
            raise ValueError("SUPABASE_URL is required")
        if not self.supabase_service_key:
            raise ValueError("SUPABASE_SERVICE_KEY is required")


# Global settings instance
settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get or create the global settings instance."""
    global settings
    if settings is None:
        settings = Settings()  # type: ignore[call-arg]  # BaseSettings loads from env
        settings.validate_required_fields()
    return settings


def reset_settings() -> None:
    """Reset the global settings instance (useful for testing)."""
    global settings
    settings = None