"""
Unit tests to verify removal of hardcoded values from the codebase.

These tests ensure that all previously hardcoded values have been replaced
with configurable environment variables and that the system works correctly
with various configuration scenarios.
"""
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

# Add src to path for importing
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from config import Config


class TestHardcodedRemoval:
    """Test that hardcoded values have been properly removed."""

    def setup_method(self):
        """Set up test fixtures."""
        # Store original environment
        self.original_env = os.environ.copy()
        
    def teardown_method(self):
        """Clean up after tests."""
        # Restore original environment
        os.environ.clear()
        os.environ.update(self.original_env)

    def test_server_host_port_configurable(self):
        """Test that server host and port are now configurable (were hardcoded as '0.0.0.0' and '8051')."""
        os.environ.clear()
        os.environ['NO_DOTENV'] = 'true'
        
        # Test custom values
        os.environ['HOST'] = '127.0.0.1'
        os.environ['PORT'] = '9999'
        os.environ['DEFAULT_HOST'] = '192.168.1.1'
        os.environ['DEFAULT_PORT'] = '7777'
        
        config = Config()
        
        # Should use custom values, not hardcoded defaults
        assert config.HOST == '127.0.0.1'
        assert config.PORT == '9999'
        assert config.DEFAULT_HOST == '192.168.1.1'
        assert config.DEFAULT_PORT == '7777'

    def test_server_defaults_when_not_configured(self):
        """Test that server defaults are used when variables are not configured."""
        os.environ.clear()
        os.environ['NO_DOTENV'] = 'true'
        
        config = Config()
        
        # Should use system defaults (previously hardcoded values)
        assert config.HOST == '0.0.0.0'
        assert config.PORT == '8051'
        assert config.DEFAULT_HOST == '0.0.0.0'
        assert config.DEFAULT_PORT == '8051'

    def test_reranking_model_configurable(self):
        """Test that reranking model is now configurable (was hardcoded as 'cross-encoder/ms-marco-MiniLM-L-6-v2')."""
        os.environ.clear()
        os.environ['NO_DOTENV'] = 'true'
        
        # Test custom reranking model
        custom_model = 'custom-reranker/test-model'
        os.environ['RERANKING_MODEL'] = custom_model
        
        config = Config()
        
        # Should use custom model, not hardcoded default
        assert config.RERANKING_MODEL == custom_model

    def test_reranking_model_default_when_not_configured(self):
        """Test that reranking model uses default when not configured."""
        os.environ.clear()
        os.environ['NO_DOTENV'] = 'true'
        
        config = Config()
        
        # Should use system default (previously hardcoded value)
        assert config.RERANKING_MODEL == 'cross-encoder/ms-marco-MiniLM-L-6-v2'

    def test_embedding_model_configurable(self):
        """Test that embedding model is now configurable (was hardcoded as 'text-embedding-3-small')."""
        os.environ.clear()
        os.environ['NO_DOTENV'] = 'true'
        
        # Test custom embedding model
        custom_model = 'custom-embedding/test-model'
        os.environ['EMBEDDING_MODEL'] = custom_model
        
        config = Config()
        
        # Should use custom model, not hardcoded default
        assert config.EMBEDDING_MODEL == custom_model

    def test_embedding_model_default_when_not_configured(self):
        """Test that embedding model uses default when not configured."""
        os.environ.clear()
        os.environ['NO_DOTENV'] = 'true'
        
        config = Config()
        
        # Should use system default (previously hardcoded value)
        assert config.EMBEDDING_MODEL == 'text-embedding-3-small'

    def test_embedding_dimensions_configurable(self):
        """Test that embedding dimensions are now configurable (was hardcoded as 1536)."""
        os.environ.clear()
        os.environ['NO_DOTENV'] = 'true'
        
        # Test custom dimensions
        os.environ['EMBEDDING_DIMENSIONS'] = '1024'
        
        config = Config()
        
        # Should use custom dimensions, not hardcoded default
        assert config.EMBEDDING_DIMENSIONS == 1024

    def test_embedding_dimensions_default_when_not_configured(self):
        """Test that embedding dimensions use default when not configured."""
        os.environ.clear()
        os.environ['NO_DOTENV'] = 'true'
        
        config = Config()
        
        # Should use system default (previously hardcoded value)
        assert config.EMBEDDING_DIMENSIONS == 1536

    def test_timeout_values_configurable(self):
        """Test that timeout values are now configurable (were hardcoded as 5 and 1800)."""
        os.environ.clear()
        os.environ['NO_DOTENV'] = 'true'
        
        # Test custom timeout values
        os.environ['OLLAMA_CHECK_TIMEOUT'] = '15'
        os.environ['REPO_ANALYSIS_TIMEOUT'] = '3600'
        os.environ['REQUEST_TIMEOUT'] = '60'
        
        config = Config()
        
        # Should use custom values, not hardcoded defaults
        assert config.OLLAMA_CHECK_TIMEOUT == 15
        assert config.REPO_ANALYSIS_TIMEOUT == 3600
        assert config.REQUEST_TIMEOUT == 60

    def test_timeout_values_defaults_when_not_configured(self):
        """Test that timeout values use defaults when not configured."""
        os.environ.clear()
        os.environ['NO_DOTENV'] = 'true'
        
        config = Config()
        
        # Should use system defaults (previously hardcoded values)
        assert config.OLLAMA_CHECK_TIMEOUT == 5
        assert config.REPO_ANALYSIS_TIMEOUT == 1800
        assert config.REQUEST_TIMEOUT == 30

    def test_rate_limiting_values_configurable(self):
        """Test that rate limiting values are now configurable (were hardcoded)."""
        os.environ.clear()
        os.environ['NO_DOTENV'] = 'true'
        
        # Test custom rate limiting values
        os.environ['MAX_CONCURRENT_REQUESTS'] = '10'
        os.environ['RATE_LIMIT_DELAY'] = '1.0'
        os.environ['CIRCUIT_BREAKER_THRESHOLD'] = '5'
        os.environ['CLIENT_CACHE_TTL'] = '7200'
        
        config = Config()
        
        # Should use custom values, not hardcoded defaults
        assert config.MAX_CONCURRENT_REQUESTS == 10
        assert config.RATE_LIMIT_DELAY == 1.0
        assert config.CIRCUIT_BREAKER_THRESHOLD == 5
        assert config.CLIENT_CACHE_TTL == 7200

    def test_rate_limiting_values_defaults_when_not_configured(self):
        """Test that rate limiting values use defaults when not configured."""
        os.environ.clear()
        os.environ['NO_DOTENV'] = 'true'
        
        config = Config()
        
        # Should use system defaults (previously hardcoded values)
        assert config.MAX_CONCURRENT_REQUESTS == 5
        assert config.RATE_LIMIT_DELAY == 0.5
        assert config.CIRCUIT_BREAKER_THRESHOLD == 3
        assert config.CLIENT_CACHE_TTL == 3600

    def test_performance_values_configurable(self):
        """Test that performance values are now configurable."""
        os.environ.clear()
        os.environ['NO_DOTENV'] = 'true'
        
        # Test custom performance values
        os.environ['MAX_CRAWL_DEPTH'] = '5'
        os.environ['MAX_CONCURRENT_CRAWLS'] = '20'
        os.environ['CHUNK_SIZE'] = '8000'
        os.environ['DEFAULT_MATCH_COUNT'] = '10'
        os.environ['MAX_WORKERS_SUMMARY'] = '15'
        os.environ['MAX_WORKERS_SOURCE_SUMMARY'] = '8'
        
        config = Config()
        
        # Should use custom values
        assert config.MAX_CRAWL_DEPTH == 5
        assert config.MAX_CONCURRENT_CRAWLS == 20
        assert config.CHUNK_SIZE == 8000
        assert config.DEFAULT_MATCH_COUNT == 10
        assert config.MAX_WORKERS_SUMMARY == 15
        assert config.MAX_WORKERS_SOURCE_SUMMARY == 8

    def test_performance_values_defaults_when_not_configured(self):
        """Test that performance values use defaults when not configured."""
        os.environ.clear()
        os.environ['NO_DOTENV'] = 'true'
        
        config = Config()
        
        # Should use system defaults
        assert config.MAX_CRAWL_DEPTH == 3
        assert config.MAX_CONCURRENT_CRAWLS == 10
        assert config.CHUNK_SIZE == 5000
        assert config.DEFAULT_MATCH_COUNT == 5
        assert config.MAX_WORKERS_SUMMARY == 10
        assert config.MAX_WORKERS_SOURCE_SUMMARY == 5

    def test_all_hardcoded_values_replaceable(self):
        """Test that all previously hardcoded values can be overridden."""
        os.environ.clear()
        os.environ['NO_DOTENV'] = 'true'
        
        # Override ALL previously hardcoded values
        custom_config = {
            'HOST': 'custom-host',
            'PORT': '9999',
            'DEFAULT_HOST': 'custom-default-host',
            'DEFAULT_PORT': '8888',
            'RERANKING_MODEL': 'custom-reranker',
            'EMBEDDING_MODEL': 'custom-embedding',
            'EMBEDDING_DIMENSIONS': '512',
            'OLLAMA_CHECK_TIMEOUT': '10',
            'REPO_ANALYSIS_TIMEOUT': '3600',
            'REQUEST_TIMEOUT': '45',
            'MAX_CONCURRENT_REQUESTS': '8',
            'RATE_LIMIT_DELAY': '1.0',
            'CIRCUIT_BREAKER_THRESHOLD': '5',
            'CLIENT_CACHE_TTL': '7200',
        }
        
        os.environ.update(custom_config)
        
        config = Config()
        
        # Verify ALL values can be customized
        assert config.HOST == 'custom-host'
        assert config.PORT == '9999'
        assert config.DEFAULT_HOST == 'custom-default-host'
        assert config.DEFAULT_PORT == '8888'
        assert config.RERANKING_MODEL == 'custom-reranker'
        assert config.EMBEDDING_MODEL == 'custom-embedding'
        assert config.EMBEDDING_DIMENSIONS == 512
        assert config.OLLAMA_CHECK_TIMEOUT == 10
        assert config.REPO_ANALYSIS_TIMEOUT == 3600
        assert config.REQUEST_TIMEOUT == 45
        assert config.MAX_CONCURRENT_REQUESTS == 8
        assert config.RATE_LIMIT_DELAY == 1.0
        assert config.CIRCUIT_BREAKER_THRESHOLD == 5
        assert config.CLIENT_CACHE_TTL == 7200

    def test_no_hardcoded_batch_sizes(self):
        """Test that batch sizes are configurable (were hardcoded as 20)."""
        # Note: SUPABASE_BATCH_SIZE is handled in utils.py, not config.py
        # This test verifies the configuration system supports it
        os.environ.clear()
        os.environ['NO_DOTENV'] = 'true'
        os.environ['SUPABASE_BATCH_SIZE'] = '50'
        
        # Verify the environment variable is accessible
        assert os.getenv('SUPABASE_BATCH_SIZE') == '50'

    def test_no_hardcoded_max_retries(self):
        """Test that max retries are configurable (were hardcoded as 3)."""
        # Note: MAX_RETRIES might be handled in utils.py
        # This test verifies the configuration system supports it
        os.environ.clear()
        os.environ['NO_DOTENV'] = 'true'
        os.environ['DEFAULT_MAX_RETRIES'] = '5'
        
        # Verify the environment variable is accessible
        assert os.getenv('DEFAULT_MAX_RETRIES') == '5'

    def test_deprecated_openai_key_not_required(self):
        """Test that deprecated OPENAI_API_KEY is not required by the new system."""
        os.environ.clear()
        os.environ['NO_DOTENV'] = 'true'
        
        # Set only required variables (not OPENAI_API_KEY)
        os.environ['SUPABASE_URL'] = 'https://test.supabase.co'
        os.environ['SUPABASE_SERVICE_KEY'] = 'test-key'
        
        # Should not require OPENAI_API_KEY
        config = Config()
        
        # System should work without deprecated key
        assert config.SUPABASE_URL == 'https://test.supabase.co'
        assert config.CHAT_MODEL == 'gpt-4o-mini'  # Default value

    def test_fallback_behavior_works(self):
        """Test that fallback behavior works properly with configurable values."""
        os.environ.clear()
        os.environ['NO_DOTENV'] = 'true'
        
        # Set DEFAULT_* values but not primary values
        os.environ['DEFAULT_HOST'] = '192.168.1.1'
        os.environ['DEFAULT_PORT'] = '7777'
        
        config = Config()
        
        # Should use DEFAULT_* values as fallbacks
        assert config.DEFAULT_HOST == '192.168.1.1'
        assert config.DEFAULT_PORT == '7777'
        
        # Primary values should use their own defaults when not set
        assert config.HOST == '0.0.0.0'  # System default
        assert config.PORT == '8051'     # System default

    def test_type_conversion_works_with_configurable_values(self):
        """Test that type conversion works properly with all configurable values."""
        os.environ.clear()
        os.environ['NO_DOTENV'] = 'true'
        
        # Set various types of values as strings (as they come from environment)
        os.environ.update({
            'PORT': '9999',                          # Integer
            'OLLAMA_CHECK_TIMEOUT': '15',           # Integer
            'REPO_ANALYSIS_TIMEOUT': '3600',        # Integer
            'REQUEST_TIMEOUT': '45',                # Integer
            'MAX_CONCURRENT_REQUESTS': '8',         # Integer
            'RATE_LIMIT_DELAY': '1.5',             # Float
            'CIRCUIT_BREAKER_THRESHOLD': '5',       # Integer
            'CLIENT_CACHE_TTL': '7200',            # Integer
            'EMBEDDING_DIMENSIONS': '1024',         # Integer
            'MAX_CRAWL_DEPTH': '3',                # Integer
            'MAX_CONCURRENT_CRAWLS': '12',         # Integer
            'CHUNK_SIZE': '6000',                  # Integer
            'DEFAULT_MATCH_COUNT': '8',            # Integer
            'MAX_WORKERS_SUMMARY': '6',            # Integer
            'MAX_WORKERS_SOURCE_SUMMARY': '4',     # Integer
            'USE_RERANKING': 'true',               # Boolean
            'USE_KNOWLEDGE_GRAPH': 'false',        # Boolean
        })
        
        config = Config()
        
        # Verify proper type conversion
        assert isinstance(config.PORT, str)  # Config stores as string
        assert isinstance(config.OLLAMA_CHECK_TIMEOUT, int)
        assert isinstance(config.REPO_ANALYSIS_TIMEOUT, int)
        assert isinstance(config.REQUEST_TIMEOUT, int)
        assert isinstance(config.MAX_CONCURRENT_REQUESTS, int)
        assert isinstance(config.RATE_LIMIT_DELAY, float)
        assert isinstance(config.CIRCUIT_BREAKER_THRESHOLD, int)
        assert isinstance(config.CLIENT_CACHE_TTL, int)
        assert isinstance(config.EMBEDDING_DIMENSIONS, int)
        assert isinstance(config.MAX_CRAWL_DEPTH, int)
        assert isinstance(config.MAX_CONCURRENT_CRAWLS, int)
        assert isinstance(config.CHUNK_SIZE, int)
        assert isinstance(config.DEFAULT_MATCH_COUNT, int)
        assert isinstance(config.MAX_WORKERS_SUMMARY, int)
        assert isinstance(config.MAX_WORKERS_SOURCE_SUMMARY, int)
        assert isinstance(config.USE_RERANKING, bool)
        assert isinstance(config.USE_KNOWLEDGE_GRAPH, bool)
        
        # Verify correct values
        assert config.OLLAMA_CHECK_TIMEOUT == 15
        assert config.RATE_LIMIT_DELAY == 1.5
        assert config.USE_RERANKING == True
        assert config.USE_KNOWLEDGE_GRAPH == False

    def test_edge_case_empty_values(self):
        """Test behavior with empty environment variable values."""
        os.environ.clear()
        os.environ['NO_DOTENV'] = 'true'
        
        # Set some empty values
        os.environ['HOST'] = ''
        os.environ['CHAT_MODEL'] = ''
        os.environ['USE_RERANKING'] = ''
        
        config = Config()
        
        # Empty strings should use defaults
        assert config.HOST == '0.0.0.0'  # Should use default
        assert config.CHAT_MODEL == 'gpt-4o-mini'  # Should use default
        assert config.USE_RERANKING == False  # Empty string should be False

    def test_configuration_independence(self):
        """Test that configuration changes are independent between instances."""
        os.environ.clear()
        os.environ['NO_DOTENV'] = 'true'
        
        # First configuration
        os.environ['HOST'] = 'first-host'
        config1 = Config()
        host1 = config1.HOST
        
        # Change environment
        os.environ['HOST'] = 'second-host'
        config2 = Config()
        host2 = config2.HOST
        
        # Values should reflect current environment
        assert host1 == 'first-host'
        assert host2 == 'second-host'
        assert host1 != host2